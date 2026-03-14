"""
coupled_solver.py
─────────────────
Bypass Topology A 결합 솔버.

비결합 근사(bypass_solver.py)와의 차이:
  bypass_solver : air측 hx_load에 YAML T_inlet, m_dot_rated 고정
  coupled_solver: T_load_sec_in (Q_heater 역산), m_dot_load_sec (Mixer 해석해) 동시 결합

DOF 폐쇄 조건:
  - pressure_ratio           고정 → P_high = P_low × r_p
  - T_sec_out_target (YAML)  → outer brentq on x: T_load_sec_out(x) = T_sec_out_target
  - Q_heater (YAML)          → T_load_sec_in (IM-7 h(T) 역산)
  - Mixer 엔탈피 균형        → y (해석적으로 결정, brentq 불필요)

에너지 일관성 보장 (수학적 증명):
  y = (h(T_chuck) − h(T_sec_out_target)) / (h(T_load_sec_in) − h(T_sec_out_target))
  m_dot_load_sec = (1−y)·ṁ_sec
  Q_cold = m_dot_load_sec · (h(T_load_sec_in) − h(T_sec_out_target))
         = m_dot_sec · (h(T_load_sec_in) − h(T_chuck))
         = Q_heater  ← 자동 보장
"""

import importlib
import sys
import os

from scipy.optimize import brentq

sys.path.insert(0, os.path.dirname(__file__))

from load_side_solver import compute_T_load_sec_in
from properties.im7_properties import _IM7


# ─────────────────────────────────────────────
# 결과 폴더명 생성
# ─────────────────────────────────────────────

def make_result_dir(config: dict, x: float, y: float) -> str:
    cycle = config["cycle"].replace("_brayton", "")
    rp    = f"rp{config['pressure_ratio']:.2f}"
    xstr  = f"x{x:.4f}"
    ystr  = f"y{y:.4f}"
    etac  = f"etac{config['comp']['eta_isen']}"
    etat  = f"etat{config['expander']['eta_isen']}"
    return os.path.join("results", f"{cycle}__{rp}__{xstr}__{ystr}__{etac}__{etat}")


# ─────────────────────────────────────────────
# 메인 솔버
# ─────────────────────────────────────────────

def solve(config: dict) -> dict:
    """
    Parameters
    ----------
    config : dict  (yaml 에서 로드한 설정)
             pressure_ratio                : float  (필수, 고정값)
             hx_load.T_sec_out_target      : float  [K]  DOF 폐쇄 (air측 brentq 기준)
             load_side.Q_heater            : float  [W]  → T_load_sec_in 역산
             load_side.Q_chuck             : float  [W]
             load_side.T_chuck_sec_in      : float  [K]

    Returns
    -------
    dict with keys:
        cycle             : str
        pressure_ratio    : float
        P_high            : float  [Pa]
        x_bypass          : float  [-]  역산된 air측 bypass 분율
        x_max             : float  [-]  사이클 수렴 최대 bypass 분율
        y_sec             : float  [-]  Mixer 해석해 (IM-7 2차측 bypass 분율)
        mdot_load_sec     : float  [kg/s]  hx_load 통과 IM-7 유량
        T_load_sec_in     : float  [K]   hx_load 2차측 입구온도 (Q_heater 역산)
        T_load_sec_out    : float  [K]   hx_load 2차측 출구온도 (= T_sec_out_target)
        T_chuck_sec_in    : float  [K]
        T_chuck_sec_out   : float  [K]
        Q_heater          : float  [W]
        Q_chuck           : float  [W]
        Q_cold            : float  [W]  (= Q_heater + Q_chuck, 수학적 보장)
        states, state_labels, results, T_expander_outlet,
        T_sec_out, W_compressor, W_expander, W_net, COP,
        Q_recuperator, Q_aftercooler, sec_temps, energy_error,
        result_dir        : str
    """
    if config.get("pressure_ratio") is None:
        raise ValueError(
            "coupled_solver: pressure_ratio 는 고정값이어야 합니다 (null 불가)."
        )
    if "load_side" not in config:
        raise ValueError(
            "coupled_solver: config 에 'load_side' 섹션이 없습니다."
        )

    ls             = config["load_side"]
    Q_chuck        = ls["Q_chuck"]
    Q_heater       = ls["Q_heater"]
    T_chuck_sec_in = ls["T_chuck_sec_in"]
    m_dot_sec      = ls.get("m_dot_sec",
                             config["hx_load"]["hotside"]["m_dot_rated"])

    T_sec_out_target = config["hx_load"]["T_sec_out_target"]
    P_high = config["P_low"] * config["pressure_ratio"]

    # ── 1단계: T_load_sec_in 역산 (IM-7 h(T), 반복 없음) ────────────────────
    T_chuck_sec_out, T_load_sec_in = compute_T_load_sec_in(config)

    # ── 2단계: y 해석적 결정 (Mixer 엔탈피 균형) ────────────────────────────
    # (1-y)·h(T_out_target) + y·h(T_in) = h(T_chuck)
    # y = (h(T_chuck) − h(T_out_target)) / (h(T_in) − h(T_out_target))
    h_chuck  = _IM7.h(T_chuck_sec_in)
    h_in     = _IM7.h(T_load_sec_in)
    h_target = _IM7.h(T_sec_out_target)

    dh = h_in - h_target
    if abs(dh) < 1e-6:
        raise ValueError(
            f"coupled_solver: T_load_sec_in ({T_load_sec_in:.2f} K) ≈ T_sec_out_target "
            f"({T_sec_out_target:.2f} K) → 분모 0. Q_heater 또는 T_sec_out_target 확인 필요."
        )

    y_sec = (h_chuck - h_target) / dh

    if not (0.0 <= y_sec <= 1.0):
        raise ValueError(
            f"coupled_solver: y_sec = {y_sec:.4f} ∉ [0, 1].\n"
            f"  T_load_sec_in    = {T_load_sec_in:.2f} K\n"
            f"  T_sec_out_target = {T_sec_out_target:.2f} K\n"
            f"  T_chuck_sec_in   = {T_chuck_sec_in:.2f} K\n"
            f"  → T_sec_out_target < T_chuck_sec_in < T_load_sec_in 이어야 합니다."
        )

    m_dot_load_sec = (1.0 - y_sec) * m_dot_sec   # hx_load 통과 유량 (고정)

    # ── 3단계: outer brentq on x (bypass_solver와 동일 구조) ────────────────
    cycle_module = importlib.import_module(f"cycles.{config['cycle']}")

    def _T_sec_out(x: float) -> float:
        out = cycle_module.run_cycle(
            config, P_high, x,
            T_sec_load=T_load_sec_in,
            m_dot_hot_sec=m_dot_load_sec,
        )
        return out["T_sec_out"]

    def _safe_T_sec_out(x: float):
        try:
            return _T_sec_out(x)
        except (ValueError, RuntimeError):
            return None

    # ── x_max 탐색: 사이클 수렴 상한 (이진 탐색) ────────────────────────────
    x_lo, x_hi = 0.0, 0.98
    if _safe_T_sec_out(x_hi) is None:
        lo_valid, hi_invalid = x_lo, x_hi
        for _ in range(20):
            mid = (lo_valid + hi_invalid) / 2.0
            if _safe_T_sec_out(mid) is None:
                hi_invalid = mid
            else:
                lo_valid = mid
            if hi_invalid - lo_valid < 1e-4:
                break
        x_hi = lo_valid

    x_max = x_hi

    # ── x_lo 탐색: 사이클 수렴 하한 (이진 탐색) ─────────────────────────────
    # near-zero m_dot_load_sec(y≈1) 구간에서 recuperator 발산 → x_lo > 0 가능
    if _safe_T_sec_out(x_lo) is None:
        lo_invalid, hi_valid = x_lo, x_hi
        for _ in range(20):
            mid = (lo_invalid + hi_valid) / 2.0
            if _safe_T_sec_out(mid) is None:
                lo_invalid = mid
            else:
                hi_valid = mid
            if hi_valid - lo_invalid < 1e-3:
                break
        x_lo = hi_valid

    # 잔차 부호 확인
    r_lo = _T_sec_out(x_lo) - T_sec_out_target
    r_hi = _T_sec_out(x_hi) - T_sec_out_target

    if r_lo * r_hi > 0:
        raise ValueError(
            f"coupled_solver: x ∈ [0, {x_max:.4f}] 범위에서 부호 변환 없음.\n"
            f"  T_sec_out(x=0)         = {r_lo + T_sec_out_target:.2f} K\n"
            f"  T_sec_out(x={x_max:.4f}) = {r_hi + T_sec_out_target:.2f} K\n"
            f"  T_sec_out_target       = {T_sec_out_target:.2f} K\n"
            f"  → T_sec_out_target 가 달성 가능 범위 밖에 있습니다.\n"
            f"  달성 가능 범위: {r_lo+T_sec_out_target:.2f} ~ {r_hi+T_sec_out_target:.2f} K"
        )

    x_sol = brentq(lambda x: _T_sec_out(x) - T_sec_out_target,
                   x_lo, x_hi, xtol=1e-4, rtol=1e-6)

    # ── 최종 사이클 계산 ────────────────────────────────────────────────────
    cycle_out = cycle_module.run_cycle(
        config, P_high, x_sol,
        T_sec_load=T_load_sec_in,
        m_dot_hot_sec=m_dot_load_sec,
    )

    states            = cycle_out["states"]
    component_results = cycle_out["component_results"]
    T_expander_outlet = cycle_out["T_expander_outlet"]
    T_sec_out         = cycle_out["T_sec_out"]
    Q_cold            = cycle_out["Q_cold"]
    W_compressor      = cycle_out["W_compressor"]
    W_expander        = cycle_out["W_expander"]
    Q_recuperator     = cycle_out.get("Q_recuperator", 0.0)
    Q_aftercooler     = cycle_out.get("Q_aftercooler", 0.0)
    sec_temps         = cycle_out.get("sec_temps", {})

    W_net = W_compressor - W_expander
    COP   = Q_cold / W_net if W_net > 0 else float("nan")

    energy_residual = sum(r.W_dot + r.Q_dot for r in component_results)
    energy_error    = abs(energy_residual) / abs(Q_cold) if Q_cold != 0.0 else float("nan")

    result_dir = make_result_dir(config, x_sol, y_sec)

    return dict(
        cycle             = config["cycle"],
        pressure_ratio    = config["pressure_ratio"],
        P_high            = P_high,
        x_bypass          = x_sol,
        x_max             = x_max,
        y_sec             = y_sec,
        mdot_load_sec     = m_dot_load_sec,
        T_load_sec_in     = T_load_sec_in,
        T_load_sec_out    = T_sec_out,
        T_sec_out_target  = T_sec_out_target,
        T_chuck_sec_in    = T_chuck_sec_in,
        T_chuck_sec_out   = T_chuck_sec_out,
        Q_heater          = Q_heater,
        Q_chuck           = Q_chuck,
        states            = states,
        state_labels      = cycle_module.STATE_LABELS,
        results           = component_results,
        T_expander_outlet = T_expander_outlet,
        T_sec_out         = T_sec_out,
        W_compressor      = W_compressor,
        W_expander        = W_expander,
        W_net             = W_net,
        COP               = COP,
        Q_cold            = Q_cold,
        Q_recuperator     = Q_recuperator,
        Q_aftercooler     = Q_aftercooler,
        sec_temps         = sec_temps,
        energy_error      = energy_error,
        result_dir        = result_dir,
    )
