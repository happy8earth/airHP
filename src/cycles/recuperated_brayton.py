"""
cycles/recuperated_brayton.py
----------------------------
Recuperated Brayton cycle (effectiveness-based recuperator).

State mapping (updated topology):
  State 1 -> [Compressor]             -> State 2
  State 2 -> [Hot HX]                 -> State 3
  State 3 -> [Recuperator hot side]   -> State 4
  State 4 -> [Expander]               -> State 5
  State 5 -> [Load HX]                -> State 6
  State 6 -> [Recuperator cold side]  -> State 1

Couplings:
  - T1 (compressor inlet) depends on recuperator cold outlet.
  - T4 (recuperator hot outlet / expander inlet) is solved by inner brentq.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scipy.optimize import brentq

from properties import state_from_TP, ComponentResult
from components import compressor, expander
from components import hx_aftercooler, hx_load
import components.hx_recuperator as hx_recuperator


STATE_LABELS = [
    "1 (C-in / Recup-out)",
    "2 (C-out)",
    "3 (HX-out)",
    "4 (E-in)",
    "5 (E-out / Load-in)",
    "6 (Load-out / Recup-in)",
]


def run_cycle(config: dict, P_high: float) -> dict:
    """
    Parameters
    ----------
    config : dict   YAML settings
    P_high : float  high pressure [Pa]

    Returns
    -------
    dict with keys:
        states             : list[ThermodynamicState]  State1 ~ State6
        T_expander_outlet  : float  [K]  State5 temperature
        component_results  : list[ComponentResult]
        Q_cold             : float  [W]
        W_compressor       : float  [W]
        W_expander         : float  [W]
        Q_recuperator      : float  [W]
    """
    fluid = config["fluid"]
    m_dot = config["mass_flow"]
    eta_c = config["comp"]["eta_isen"]
    eta_t = config["expander"]["eta_isen"]
    P_low = config["P_low"]

    # Recuperator UA 파라미터
    rc = config["hx_recup"]
    rc_UA_rated    = rc["UA_rated"]
    rc_m_dot_rated = rc["m_dot_rated"]

    # T1: compressor inlet (recuperator cold outlet) initial guess
    T1 = config["comp"]["T_inlet"]

    # Aftercooler UA params
    ac = config["hx_aftercooler"]
    ac_UA_rated    = ac["UA_rated"]
    ac_m_dot_rated = ac["m_dot_rated"]
    ac_T_sec       = ac["T_secondary"]
    ac_m_dot_sec   = ac["m_dot_secondary"]

    # Load HX 파라미터 (hotside/coldside breakdown)
    lhx      = config["hx_load"]
    lhx_hot  = lhx["hotside"]
    lhx_cold = lhx["coldside"]

    for _ in range(30):
        # State 1: compressor inlet
        state1 = state_from_TP(T1, P_low, fluid, "State1")

        # Compressor: 1 -> 2
        comp_res = compressor.run(state1, P_out=P_high, eta_c=eta_c, m_dot=m_dot)
        state2 = comp_res.state_out

        # Aftercooler: 2 -> 3  (UA·LMTD)
        hothx_res = hx_aftercooler.run(
            state2,
            UA_rated=ac_UA_rated, m_dot=m_dot,
            m_dot_rated=ac_m_dot_rated,
            T_sec=ac_T_sec, m_dot_sec=ac_m_dot_sec,
        )
        state3 = hothx_res.state_out

        # Inner brentq: find T4 such that recuperator hot outlet matches T4
        def _residual(T4_K: float) -> float:
            _s4 = state_from_TP(T4_K, P_high, fluid)
            _s5 = expander.run(_s4, P_out=P_low, eta_t=eta_t, m_dot=m_dot).state_out
            _lhx = hx_load.run(_s5,
                               htc_hot_rated=lhx_hot["htc_rated"],
                               area_hot=lhx_hot["area"],
                               m_dot_hot=lhx_hot["m_dot_rated"],
                               m_dot_hot_rated=lhx_hot["m_dot_rated"],
                               htc_cold_rated=lhx_cold["htc_rated"],
                               area_cold=lhx_cold["area"],
                               m_dot_cold=m_dot,
                               m_dot_cold_rated=lhx_cold["m_dot_rated"],
                               T_sec=lhx_hot["T_inlet"])
            _s6 = _lhx.state_out
            _recup_hot, _ = hx_recuperator.run(state3, _s6,
                               UA_rated=rc_UA_rated, m_dot=m_dot, m_dot_rated=rc_m_dot_rated)
            return T4_K - _recup_hot.state_out.T

        T4_lo, T4_hi = 140.0, state3.T
        if _residual(T4_lo) * _residual(T4_hi) > 0:
            raise ValueError(
                f"Recuperator inner solve: [{T4_lo:.1f}, {T4_hi:.1f}] K "
                f"no sign change. eps={eps}, P_high={P_high/1e3:.1f} kPa"
            )
        T4_sol = brentq(_residual, T4_lo, T4_hi, xtol=0.01, rtol=1e-6)
        state4 = state_from_TP(T4_sol, P_high, fluid, "State4")

        # Expander: 4 -> 5
        exp_res = expander.run(state4, P_out=P_low, eta_t=eta_t, m_dot=m_dot)
        state5 = exp_res.state_out

        # Load HX: 5 -> 6  (UA·LMTD, hot=IM-7, cold=Air)
        loadhx_res = hx_load.run(
            state5,
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
        state6 = loadhx_res.state_out

        # Recuperator: hot (3->4) and cold (6->1)  (UA·LMTD)
        recup_hot, recup_cold = hx_recuperator.run(
            state3, state6,
            UA_rated=rc_UA_rated, m_dot=m_dot, m_dot_rated=rc_m_dot_rated,
        )

        T1_new = recup_cold.state_out.T
        if abs(T1_new - T1) < 0.05:
            T1 = T1_new
            break
        T1 = T1_new

    state1 = state_from_TP(T1, P_low, fluid, "State1")
    states = [state1, state2, state3, state4, state5, state6]
    component_results = [comp_res, hothx_res, recup_hot, exp_res, loadhx_res, recup_cold]

    return dict(
        states            = states,
        T_expander_outlet = state5.T,
        component_results = component_results,
        Q_cold            = loadhx_res.Q_dot,        # > 0
        W_compressor      = comp_res.W_dot,           # > 0
        W_expander        = -exp_res.W_dot,           # > 0
        Q_recuperator     = -recup_hot.Q_dot,         # > 0
    )
