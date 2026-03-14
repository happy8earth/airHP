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
