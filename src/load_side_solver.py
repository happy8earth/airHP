"""
load_side_solver.py
───────────────────
Load측 2차 회로 (IM-7) 솔버.

토폴로지:
  Chuck 출구(T_chuck_sec_out)
    → [Heater +Q_heater] → T_load_sec_in
    → [Splitter]
        ├─(1-y)·ṁ_sec ──→ [hx_load 2차측] → T_load_sec_out ─┐
        └─ y·ṁ_sec (bypass) ────────────── T_load_sec_in ──→ [Mixer] → T_chuck_sec_in

변수 매핑:
  Q_heater  → T_load_sec_in  (IM-7 h(T) 역산)
  x (공기측) → T_load_sec_out (hx_load UA-LMTD, callback)
  y (2차측)  → mdot_load_sec = (1-y)·ṁ_sec  (brentq 역산)

지배 방정식:
  ① h_chuck_sec_out = h(T_chuck_sec_in) + Q_chuck  / m_dot_sec
  ② h_load_sec_in   = h_chuck_sec_out   + Q_heater / m_dot_sec
     → T_chuck_sec_out, T_load_sec_in: h(T) 역산 (brentq)
  ③ T_load_sec_out  = T_load_sec_out_fn(mdot_load_sec)   [hx_load callback]
  ④ Mixer: T_chuck_sec_in = (1-y)·T_load_sec_out + y·T_load_sec_in
  ⑤ mdot_load_sec  = (1-y)·m_dot_sec

자기일관성:
  y → mdot_load_sec → hx_load → T_load_sec_out → y
  → brentq on y: f(y) = (1-y)·T_load_sec_out(y) + y·T_load_sec_in − T_chuck_sec_in = 0

특수 케이스 (Mode2 퇴화):
  |T_load_sec_in − T_chuck_sec_in| < ε → y = 1.0 직접 반환 (분모 0 방지)

m_dot_sec 기본값: config["hx_load"]["hotside"]["m_dot_rated"]  (YAML에 명시 불필요)
Cp: IM-7 물성 모듈 h(T) 직접 사용 (Cp 근사값 불필요)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from scipy.optimize import brentq
from properties.im7_properties import _IM7


# ─────────────────────────────────────────────
# 에너지 밸런스 검증 출력
# ─────────────────────────────────────────────

def print_load_side_energy_balance(result: dict, Q_cold_air: float = None) -> None:
    """
    Load측 (IM-7 2차 회로) 에너지 밸런스 검증 출력.

    Splitter/Mixer 전후의 온도·엔탈피·mdot을 표로 출력하고
    각 노드의 에너지 균형 잔차를 계산합니다.

    Parameters
    ----------
    result       : dict  solve_load_side() 또는 coupled_solver.solve() 반환값
                   필수 키: y, mdot_load_sec, T_chuck_sec_in, T_chuck_sec_out,
                            T_load_sec_in, T_load_sec_out, Q_chuck, Q_heater
    Q_cold_air   : float [W]  공기측 Q_dot (hx_load.Q_dot). 지정 시 IM-7 측과 교차 검증.
    """
    SEP = "─" * 72

    y              = result["y_sec"] if "y_sec" in result else result["y"]
    mdot_load      = result["mdot_load_sec"]
    T_chuck_in     = result["T_chuck_sec_in"]
    T_chuck_out    = result["T_chuck_sec_out"]
    T_load_in      = result["T_load_sec_in"]
    T_load_out     = result["T_load_sec_out"]
    Q_chuck        = result["Q_chuck"]
    Q_heater       = result["Q_heater"]

    # m_dot_sec 역산 (y < 1 인 경우)
    if y < 0.9999:
        m_dot_sec = mdot_load / (1.0 - y)
    else:
        # y ≈ 1 (전량 bypass): mdot_load ≈ 0, m_dot_sec 추정 불가 → Q 값으로 추정
        # Q_chuck = m_dot_sec * (h_chuck_out - h_chuck_in)
        dh_chuck = _IM7.h(T_chuck_out) - _IM7.h(T_chuck_in)
        m_dot_sec = Q_chuck / dh_chuck if abs(dh_chuck) > 1e-9 else float("nan")

    mdot_bypass = y * m_dot_sec

    # 엔탈피 계산
    h_chuck_in  = _IM7.h(T_chuck_in)
    h_chuck_out = _IM7.h(T_chuck_out)
    h_load_in   = _IM7.h(T_load_in)
    h_load_out  = _IM7.h(T_load_out)

    # ── 열량 계산 ──────────────────────────────────────────────────────────
    Q_chuck_check  = m_dot_sec * (h_chuck_out - h_chuck_in)       # Chuck 에너지 흡수
    Q_heater_check = m_dot_sec * (h_load_in  - h_chuck_out)       # Heater 에너지 공급
    Q_hx_im7       = mdot_load * (h_load_in  - h_load_out)        # IM-7 측 HX 방열
    Q_loop_total   = Q_chuck + Q_heater                            # IM-7 루프 총 열 흡수

    # Splitter 에너지 균형
    E_in_split  = m_dot_sec * h_load_in
    E_out_split = mdot_load * h_load_in + mdot_bypass * h_load_in  # 항등식: 항상 0
    split_residual = E_in_split - E_out_split                      # 항상 0

    # Mixer 엔탈피 균형
    E_in_mix_load   = mdot_load   * h_load_out
    E_in_mix_bypass = mdot_bypass * h_load_in
    E_out_mix       = m_dot_sec   * h_chuck_in
    mixer_residual  = (E_in_mix_load + E_in_mix_bypass) - E_out_mix  # [W]

    # IM-7 루프 전체 클로저
    loop_residual  = Q_hx_im7 - Q_loop_total   # 0 이어야 함

    print()
    print(SEP)
    print("  Load측 (IM-7) 에너지 밸런스 검증")
    print(SEP)

    # ── 노드별 상태표 ──────────────────────────────────────────────────────
    print()
    print(f"  {'노드':<22} {'T [degC]':>9} {'h [J/kg]':>12} {'mdot[kg/s]':>11}")
    print(f"  {'─'*22} {'─'*9} {'─'*12} {'─'*10}")

    def row(label, T_K, h_val, mdot):
        print(f"  {label:<22} {T_K-273.15:>9.3f} {h_val:>12.2f} {mdot:>10.5f}")

    row("Chuck 입구 (Mixer 출구)",   T_chuck_in,  h_chuck_in,  m_dot_sec)
    row("Chuck 출구 (Heater 입구)",  T_chuck_out, h_chuck_out, m_dot_sec)
    row("Heater 출구 = Splitter 입구", T_load_in, h_load_in,   m_dot_sec)
    print(f"  {'─'*22} {'─'*9} {'─'*12} {'─'*10}")
    row(f"  └─ hx_load 입구  (1-y)", T_load_in,  h_load_in,  mdot_load)
    row(f"  └─ bypass 입구   (y)",   T_load_in,  h_load_in,  mdot_bypass)
    print(f"  {'─'*22} {'─'*9} {'─'*12} {'─'*10}")
    row(f"  hx_load 출구  → Mixer A", T_load_out, h_load_out, mdot_load)
    row(f"  bypass 출구   → Mixer B", T_load_in,  h_load_in,  mdot_bypass)
    print(f"  {'─'*22} {'─'*9} {'─'*12} {'─'*10}")
    row("Mixer 출구 (Chuck 입구)",    T_chuck_in,  h_chuck_in,  m_dot_sec)

    # ── bypass 분율 ───────────────────────────────────────────────────────
    print()
    print(f"  y (2차측 bypass)    = {y:.5f}")
    print(f"  mdot_sec            = {m_dot_sec:.5f} kg/s")
    print(f"  mdot_load (hx 통과) = {mdot_load:.5f} kg/s")
    print(f"  mdot_bypass         = {mdot_bypass:.5f} kg/s")

    # ── 에너지 균형 ───────────────────────────────────────────────────────
    print()
    print(f"  {'항목':<36} {'값 [W]':>12}  {'잔차 [W]':>10}")
    print(f"  {'─'*36} {'─'*12}  {'─'*10}")
    print(f"  {'Q_chuck  (설정값)':.<36} {Q_chuck:>12.2f}")
    print(f"  {'Q_chuck  (h(T) 계산값)':.<36} {Q_chuck_check:>12.2f}  {Q_chuck_check - Q_chuck:>+10.4f}")
    print(f"  {'Q_heater (설정값)':.<36} {Q_heater:>12.2f}")
    print(f"  {'Q_heater (h(T) 계산값)':.<36} {Q_heater_check:>12.2f}  {Q_heater_check - Q_heater:>+10.4f}")
    print()
    print(f"  {'Q_hx_load (IM-7측)':.<36} {Q_hx_im7:>12.2f}")
    print(f"  {'Q_loop_total (chuck+heater)':.<36} {Q_loop_total:>12.2f}  {loop_residual:>+10.4f}")
    if Q_cold_air is not None:
        hx_cross = Q_cold_air - Q_hx_im7
        print(f"  {'Q_cold (공기측)':.<36} {Q_cold_air:>12.2f}  {hx_cross:>+10.4f}")
    print()
    print(f"  {'Splitter 에너지 잔차 [W]':.<36} {split_residual:>+12.4f}  ← 항등식(항상 0)")
    print(f"  {'Mixer 엔탈피 균형 잔차 [W]':.<36} {mixer_residual:>+12.4f}")
    print()

    # ── 판정 ──────────────────────────────────────────────────────────────
    tol_rel = 1e-3   # 0.1% 상대 허용
    tol_abs = 1.0    # 1 W 절대 허용 (Q≈0 케이스)
    def _ok(err, ref): return abs(err) < max(abs(ref) * tol_rel, tol_abs)
    ok_mixer   = _ok(mixer_residual,              Q_hx_im7)
    ok_loop    = _ok(loop_residual,               Q_loop_total)
    ok_q_check = _ok(Q_chuck_check  - Q_chuck,   Q_chuck)
    ok_qh_check = _ok(Q_heater_check - Q_heater, Q_heater)

    print(f"  [{'OK' if ok_q_check  else 'NG'}] Chuck 에너지 (설정값 vs h(T) 계산)")
    print(f"  [{'OK' if ok_qh_check else 'NG'}] Heater 에너지 (설정값 vs h(T) 계산)")
    print(f"  [{'OK' if ok_mixer    else 'NG'}] Mixer 엔탈피 균형 (잔차 < 0.1%)")
    print(f"  [{'OK' if ok_loop     else 'NG'}] IM-7 루프 열균형 (Q_hx = Q_chuck+Q_heater)")
    if Q_cold_air is not None:
        ok_hx = abs(hx_cross) / max(abs(Q_cold_air), 1.0) < tol_rel
        print(f"  [{'OK' if ok_hx else 'NG'}] HX 열균형 (공기측 vs IM-7측)")
    print(SEP)


# ─────────────────────────────────────────────
# 내부 헬퍼: IM-7 h(T) 역산
# ─────────────────────────────────────────────

def _T_from_h_im7(h_target: float, T_lo: float = 150.0, T_hi: float = 450.0) -> float:
    """IM-7 엔탈피 h_target 를 만족하는 온도 [K] 를 brentq 로 역산."""
    return brentq(lambda T: _IM7.h(T) - h_target, T_lo, T_hi, xtol=0.001, rtol=1e-7)


# ─────────────────────────────────────────────
# 1단계: Q_heater → T_load_sec_in  (h(T) 역산)
# ─────────────────────────────────────────────

def compute_T_load_sec_in(config: dict) -> tuple[float, float]:
    """
    Chuck + Heater 에너지 균형으로 T_load_sec_in 계산.
    IM-7 엔탈피 h(T) 를 직접 사용하여 Cp 근사 오류 없음.

    Parameters
    ----------
    config : dict  (YAML 전체 dict, load_side 섹션 필수)

    Returns
    -------
    (T_chuck_sec_out, T_load_sec_in) : tuple[float, float]  [K]
    """
    ls = config["load_side"]
    T_chuck_sec_in = ls["T_chuck_sec_in"]   # [K]
    Q_chuck        = ls["Q_chuck"]           # [W]
    Q_heater       = ls["Q_heater"]          # [W]
    m_dot_sec      = ls.get("m_dot_sec",
                             config["hx_load"]["hotside"]["m_dot_rated"])  # [kg/s]

    h_chuck_sec_in  = _IM7.h(T_chuck_sec_in)
    h_chuck_sec_out = h_chuck_sec_in  + Q_chuck  / m_dot_sec              # ①
    h_load_sec_in   = h_chuck_sec_out + Q_heater / m_dot_sec              # ②

    T_chuck_sec_out = _T_from_h_im7(h_chuck_sec_out)
    T_load_sec_in   = _T_from_h_im7(h_load_sec_in)

    return T_chuck_sec_out, T_load_sec_in


# ─────────────────────────────────────────────
# 2단계: brentq on y — Mixer 제약식 만족
# ─────────────────────────────────────────────

def solve_y(T_load_sec_in: float,
            T_chuck_sec_in: float,
            m_dot_sec: float,
            T_load_sec_out_fn) -> dict:
    """
    Mixer 제약식을 만족하는 bypass 분율 y 를 brentq 로 역산.

    Parameters
    ----------
    T_load_sec_in     : float   hx_load 2차측 입구온도 [K]
    T_chuck_sec_in    : float   척 2차측 입구온도 (Mixer 출구 목표) [K]
    m_dot_sec         : float   2차측 총 유량 [kg/s]
    T_load_sec_out_fn : callable  (m_dot_load_sec: float) -> T_load_sec_out: float
                        hx_load 2차측 출구온도 계산 함수 (공기측 상태 고정 가정)

    Returns
    -------
    dict with keys:
        y              : float  2차측 bypass 분율 (0 = 전량 통과, 1 = 전량 bypass)
        mdot_load_sec  : float  hx_load 통과 유량 [kg/s]
        T_load_sec_in  : float  [K]
        T_load_sec_out : float  [K]
    """
    # y=1 경계 조건: T_load_sec_in ≤ T_chuck_sec_in 이면 hx_load 통과분 없어야 Mixer 성립.
    # Q_load = 0 이지만 역브레이튼 사이클은 정상 운전 가능한 유효 운전점.
    # m_dot_load_sec=0 으로 hx_load 호출 시 ua_scale_two_side 에서 ZeroDivisionError 발생하므로
    # 수학적 해 y=1, T_load_sec_out=T_load_sec_in 을 직접 반환.
    if T_load_sec_in <= T_chuck_sec_in + 0.01:
        return dict(
            y=1.0,
            mdot_load_sec=0.0,
            T_load_sec_in=T_load_sec_in,
            T_load_sec_out=T_load_sec_in,   # m_dot=0 → UA=0 → T_out=T_in
        )

    def residual(y: float) -> float:
        """Mixer 잔차: (1-y)·T_out(y) + y·T_in − T_chuck_in"""
        m_dot_load_sec = (1.0 - y) * m_dot_sec
        T_out = T_load_sec_out_fn(m_dot_load_sec)
        return (1.0 - y) * T_out + y * T_load_sec_in - T_chuck_sec_in

    r_lo = residual(0.0)       # y=0: 전량 hx_load 통과
    r_hi = residual(0.9999)    # y≈1: 전량 bypass

    if r_lo * r_hi > 0:
        raise ValueError(
            f"load_side_solver: y ∈ [0, 1) 범위에서 Mixer 잔차 부호 변환 없음.\n"
            f"  잔차(y=0): {r_lo:+.2f} K,  잔차(y≈1): {r_hi:+.2f} K\n"
            f"  T_load_sec_in={T_load_sec_in:.2f} K, T_chuck_sec_in={T_chuck_sec_in:.2f} K\n"
            f"  힌트: T_load_sec_out(y=0)={r_lo + T_chuck_sec_in:.2f} K 확인 필요."
        )

    y_sol = brentq(residual, 0.0, 0.9999, xtol=1e-4, rtol=1e-6)
    m_dot_load_sec = (1.0 - y_sol) * m_dot_sec
    T_load_sec_out = T_load_sec_out_fn(m_dot_load_sec)

    return dict(
        y=y_sol,
        mdot_load_sec=m_dot_load_sec,
        T_load_sec_in=T_load_sec_in,
        T_load_sec_out=T_load_sec_out,
    )


# ─────────────────────────────────────────────
# 통합 진입점
# ─────────────────────────────────────────────

def solve_load_side(config: dict, T_load_sec_out_fn) -> dict:
    """
    Load측 전체 솔버 (1단계 + 2단계 통합).

    Parameters
    ----------
    config              : dict      YAML 전체 dict (load_side 섹션 필수)
    T_load_sec_out_fn   : callable  (m_dot_load_sec: float) -> T_load_sec_out: float
        공기측 State5 고정 후 hx_load.run() 을 감싸는 함수.
        bypass_solver 에서 아래와 같이 생성:
            def fn(m_dot_load_sec):
                res = hx_load.run(..., m_dot_hot=m_dot_load_sec, T_sec=T_load_sec_in, ...)
                return res.extra["T_sec_out"]

    Returns
    -------
    dict with keys:
        y               : float  2차측 bypass 분율
        mdot_load_sec   : float  hx_load 통과 유량 [kg/s]
        T_chuck_sec_in  : float  [K]
        T_chuck_sec_out : float  [K]
        T_load_sec_in   : float  [K]
        T_load_sec_out  : float  [K]
        Q_chuck         : float  [W]
        Q_heater        : float  [W]
    """
    ls = config["load_side"]
    m_dot_sec = ls.get("m_dot_sec", config["hx_load"]["hotside"]["m_dot_rated"])

    T_chuck_sec_out, T_load_sec_in = compute_T_load_sec_in(config)

    result = solve_y(
        T_load_sec_in=T_load_sec_in,
        T_chuck_sec_in=ls["T_chuck_sec_in"],
        m_dot_sec=m_dot_sec,
        T_load_sec_out_fn=T_load_sec_out_fn,
    )

    result["T_chuck_sec_in"]  = ls["T_chuck_sec_in"]
    result["T_chuck_sec_out"] = T_chuck_sec_out
    result["Q_chuck"]         = ls["Q_chuck"]
    result["Q_heater"]        = ls["Q_heater"]

    return result
