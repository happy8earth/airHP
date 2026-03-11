"""
cycles/recuperated_brayton.py
──────────────────────────────
회수(recuperated) 역브레이튼 사이클.

상태점 흐름:
  State 1 → [Compressor]            → State 2
  State 2 → [Hot HX]                → State 3
  State 3 → [Recuperator hot side]  → State 4   (고압 스트림 예냉)
  State 4 → [Turbine]               → State 5
  State 5 → [Recuperator cold side] → State 6   (저압 스트림 예열)
  State 6 → [Cold HX]               → State 1

리큐퍼레이터 순환 의존성 해결:
  T4 = T3 - ε*(T3 - T5(T4))  →  내부 brentq 로 T4 수렴.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scipy.optimize import brentq

from properties import state_from_TP
from components import compressor, turbine
from components import hx_heat_rejection, hx_heat_absorption
import components.hx_recuperator as hx_recuperator


STATE_LABELS = [
    "1 (C-in)",
    "2 (C-out)",
    "3 (HX-out)",
    "4 (T-in)",
    "5 (T-out)",
    "6 (rec-out)",
]


def run_cycle(config: dict, P_high: float) -> dict:
    """
    Parameters
    ----------
    config : dict   YAML 설정
    P_high : float  고압 [Pa]

    Returns
    -------
    dict with keys:
        states            : list[ThermodynamicState]  State1 ~ State6
        T_turbine_outlet  : float  [K]  State5 온도 (외부 brentq 수렴 판정용)
        component_results : list[ComponentResult]
        Q_cold            : float  [W]  냉동 능력 (양수)
        W_compressor      : float  [W]  압축기 동력 (양수)
        W_turbine         : float  [W]  터빈 출력  (양수)
        Q_recuperator     : float  [W]  리큐퍼레이터 열전달량 (양수)
    """
    fluid  = config["fluid"]
    m_dot  = config["mass_flow"]
    eta_c  = config["comp"]["eta_isen"]
    eta_t  = config["turbine"]["eta_isen"]
    eps    = config["hx_recup"]["effectiveness"]
    P_low  = config["P_low"]
    T1     = config["comp"]["T_inlet"]
    T3_set = config["hx_hotside"]["T_outlet"]

    # ── State 1: Compressor inlet ──────────────────────
    state1 = state_from_TP(T1, P_low, fluid, "State1")

    # ── Compressor: 1 → 2 ─────────────────────────────
    comp_res = compressor.run(state1, P_out=P_high, eta_c=eta_c, m_dot=m_dot)
    state2 = comp_res.state_out

    # ── Hot HX: 2 → 3 ─────────────────────────────────
    hothx_res = hx_heat_rejection.run(state2, T_out=T3_set, m_dot=m_dot)
    state3 = hothx_res.state_out

    # ── Inner brentq: find T4 for recuperator balance ──
    #
    #   Residual(T4) = T4 - [T3 - ε*(T3 - T5(T4))]
    #
    #   Sign analysis:
    #     T4 = T3  → residual = ε*(T3 - T5(T3)) > 0
    #     T4 = 100K → residual < 0  (T4 << T4_target)
    #
    def _residual(T4_K: float) -> float:
        _s4 = state_from_TP(T4_K, P_high, fluid)
        _T5 = turbine.run(_s4, P_out=P_low, eta_t=eta_t, m_dot=m_dot).state_out.T
        return T4_K - (state3.T - eps * (state3.T - _T5))

    # 140 K : Air 의 cricondentherm (~132.5K) 상방 → 어떤 압력에서도 기상 보장
    T4_lo, T4_hi = 140.0, state3.T
    if _residual(T4_lo) * _residual(T4_hi) > 0:
        raise ValueError(
            f"Recuperator inner solve: [{T4_lo:.1f}, {T4_hi:.1f}] K 구간에서 "
            f"부호 변환 없음. ε={eps}, P_high={P_high/1e3:.1f} kPa"
        )
    T4_sol = brentq(_residual, T4_lo, T4_hi, xtol=0.01, rtol=1e-6)
    state4 = state_from_TP(T4_sol, P_high, fluid, "State4")

    # ── Turbine: 4 → 5 ────────────────────────────────
    turb_res = turbine.run(state4, P_out=P_low, eta_t=eta_t, m_dot=m_dot)
    state5 = turb_res.state_out

    # ── Recuperator: hot (3→4) and cold (5→6) ─────────
    recup_hot, recup_cold = hx_recuperator.run(
        state3, state5, effectiveness=eps, m_dot=m_dot
    )
    state6 = recup_cold.state_out

    # ── Cold HX: 6 → 1 ────────────────────────────────
    coldhx_res = hx_heat_absorption.run(state6, T_out=T1, m_dot=m_dot)

    states = [state1, state2, state3, state4, state5, state6]
    component_results = [comp_res, hothx_res, recup_hot, turb_res, recup_cold, coldhx_res]

    return dict(
        states            = states,
        T_turbine_outlet  = state5.T,
        component_results = component_results,
        Q_cold            = coldhx_res.Q_dot,        # > 0
        W_compressor      = comp_res.W_dot,           # > 0
        W_turbine         = -turb_res.W_dot,          # > 0
        Q_recuperator     = -recup_hot.Q_dot,         # > 0
    )
