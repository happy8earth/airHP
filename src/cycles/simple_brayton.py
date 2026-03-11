"""
cycles/simple_brayton.py
────────────────────────
단순 역브레이튼 사이클.

상태점 흐름:
  State 1 → [Compressor]  → State 2
  State 2 → [Aftercooler] → State 3
  State 3 → [Expander]    → State 4
  State 4 → [Load HX]     → State 1

T1 (압축기 입구) 는 Load HX 계산 결과로 결정되므로 fixed-point iteration 적용.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from properties import state_from_TP, ComponentResult
from components import compressor, expander
from components import hx_aftercooler, hx_load


STATE_LABELS = [
    "1 (C-in / Load-out)",
    "2 (C-out)",
    "3 (E-in)",
    "4 (E-out / Load-in)",
]


def run_cycle(config: dict, P_high: float) -> dict:
    """
    Parameters
    ----------
    config  : dict   YAML 설정
    P_high  : float  고압 [Pa]

    Returns
    -------
    dict with keys:
        states             : list[ThermodynamicState]  State1 ~ State4
        T_expander_outlet  : float  [K]  State4 온도
        component_results  : list[ComponentResult]
        Q_cold             : float  [W]
        W_compressor       : float  [W]
        W_expander         : float  [W]
        Q_recuperator      : float  [W]  (항상 0.0)
    """
    fluid = config["fluid"]
    m_dot = config["mass_flow"]
    eta_c = config["comp"]["eta_isen"]
    eta_t = config["expander"]["eta_isen"]
    P_low = config["P_low"]

    # Aftercooler UA 파라미터
    ac = config["hx_aftercooler"]
    ac_UA_rated    = ac["UA_rated"]
    ac_m_dot_rated = ac["m_dot_rated"]
    ac_T_sec       = ac["T_secondary"]
    ac_m_dot_sec   = ac["m_dot_secondary"]

    # Load HX UA 파라미터
    lhx = config["hx_load"]
    lhx_UA_rated    = lhx["UA_rated"]
    lhx_m_dot_rated = lhx["m_dot_rated"]
    lhx_T_sec       = lhx["T_secondary"]
    lhx_m_dot_sec   = lhx["m_dot_secondary"]

    # T1 초기 추정값
    T1 = config["comp"]["T_inlet"]

    for _ in range(30):
        # State 1: 압축기 입구
        state1 = state_from_TP(T1, P_low, fluid, "State1")

        # Compressor: 1 → 2
        comp_res = compressor.run(state1, P_out=P_high, eta_c=eta_c, m_dot=m_dot)
        state2 = comp_res.state_out

        # Aftercooler: 2 → 3  (UA·LMTD)
        ac_res = hx_aftercooler.run(
            state2,
            UA_rated=ac_UA_rated, m_dot=m_dot,
            m_dot_rated=ac_m_dot_rated,
            T_sec=ac_T_sec, m_dot_sec=ac_m_dot_sec,
        )
        state3 = ac_res.state_out

        # Expander: 3 → 4
        exp_res = expander.run(state3, P_out=P_low, eta_t=eta_t, m_dot=m_dot)
        state4 = exp_res.state_out

        # Load HX: 4 → 1  (UA·LMTD, hot=IM-7, cold=Air)
        lhx_res = hx_load.run(
            state4,
            UA_rated=lhx_UA_rated, m_dot=m_dot,
            m_dot_rated=lhx_m_dot_rated,
            T_sec=lhx_T_sec, m_dot_sec=lhx_m_dot_sec,
        )
        T1_new = lhx_res.state_out.T

        if abs(T1_new - T1) < 0.05:
            T1 = T1_new
            break
        T1 = T1_new

    state1 = state_from_TP(T1, P_low, fluid, "State1")
    states = [state1, state2, state3, state4]
    component_results = [comp_res, ac_res, exp_res, lhx_res]

    return dict(
        states            = states,
        T_expander_outlet = state4.T,
        component_results = component_results,
        Q_cold            = lhx_res.Q_dot,
        W_compressor      = comp_res.W_dot,
        W_expander        = -exp_res.W_dot,
        Q_recuperator     = 0.0,
    )
