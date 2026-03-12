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

    # Aftercooler 파라미터 (hotside/coldside breakdown)
    ac      = config["hx_aftercooler"]
    ac_hot  = ac["hotside"]
    ac_cold = ac["coldside"]

    # Load HX 파라미터 (hotside/coldside breakdown)
    lhx      = config["hx_load"]
    lhx_hot  = lhx["hotside"]
    lhx_cold = lhx["coldside"]

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
            htc_hot_rated=ac_hot["htc_rated"],
            area_hot=ac_hot["area"],
            m_dot_hot=m_dot,
            m_dot_hot_rated=ac_hot["m_dot_rated"],
            htc_cold_rated=ac_cold["htc_rated"],
            area_cold=ac_cold["area"],
            m_dot_cold=ac_cold["m_dot_rated"],
            m_dot_cold_rated=ac_cold["m_dot_rated"],
            T_sec=ac_cold["T_inlet"],
        )
        state3 = ac_res.state_out

        # Expander: 3 → 4
        exp_res = expander.run(state3, P_out=P_low, eta_t=eta_t, m_dot=m_dot)
        state4 = exp_res.state_out

        # Load HX: 4 → 1  (UA·LMTD, hot=IM-7, cold=Air)
        lhx_res = hx_load.run(
            state4,
            htc_hot_rated=lhx_hot["htc_rated"],
            area_hot=lhx_hot["area"],
            m_dot_hot=lhx_hot["m_dot_rated"],
            m_dot_hot_rated=lhx_hot["m_dot_rated"],
            htc_cold_rated=lhx_cold["htc_rated"],
            area_cold=lhx_cold["area"],
            m_dot_cold=m_dot,
            m_dot_cold_rated=lhx_cold["m_dot_rated"],
            T_sec=lhx_hot["T_inlet"],
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
        Q_aftercooler     = -ac_res.Q_dot,
        sec_temps         = dict(
            ac   = dict(air_in_idx=1, air_out_idx=2,
                        T_sec_in=ac_cold["T_inlet"],
                        T_sec_out=ac_res.extra["T_sec_out"]),
            load = dict(air_in_idx=3, air_out_idx=0,
                        T_sec_in=lhx_hot["T_inlet"],
                        T_sec_out=lhx_res.extra["T_sec_out"]),
        ),
    )
