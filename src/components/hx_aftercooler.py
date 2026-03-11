"""
components/hx_aftercooler.py
────────────────────────────
Aftercooler: 압축기 출구 고압 고온 공기를 냉각수로 냉각하는 counter-flow HX.

  hot  side : working fluid (Air)  2 → 3
  cold side : 물(water)            T_sec_in → T_sec_out
  Q_dot < 0  (working fluid 기준, 열 방출)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from properties import ThermodynamicState, ComponentResult, state_from_TP
from components.hx_ua_lmtd import ua_scale, solve_counterflow


def run(state_in: ThermodynamicState,
        UA_rated:    float,
        m_dot:       float,
        m_dot_rated: float,
        T_sec:       float,
        m_dot_sec:   float) -> ComponentResult:
    """
    Parameters
    ----------
    state_in    : ThermodynamicState  압축기 출구 상태 (State 2)
    UA_rated    : float               정격 UA [W/K]
    m_dot       : float               1차측(Air) 질량 유량 [kg/s]
    m_dot_rated : float               정격 1차측 유량 [kg/s]
    T_sec       : float               냉각수 입구 온도 [K]
    m_dot_sec   : float               냉각수 유량 [kg/s]

    Returns
    -------
    ComponentResult
        state_out : 팽창기 입구 상태 (State 3)
        W_dot     : 0.0
        Q_dot     : < 0  (working fluid 열 방출)
    """
    UA = ua_scale(UA_rated, m_dot, m_dot_rated)

    T_hot_out, _T_sec_out, Q_cf, lmtd = solve_counterflow(
        UA,
        state_in.T, state_in.P, state_in.fluid,   # hot side
        T_sec,      101325.0,   "water",           # cold side (P 무시)
        m_dot, m_dot_sec,
    )

    state_out = state_from_TP(T_hot_out, state_in.P,
                               fluid=state_in.fluid, label="Aftercooler_out")
    Q_dot = -Q_cf   # working fluid 기준: 열 방출 → 음수
    return ComponentResult(state_out=state_out, W_dot=0.0, Q_dot=Q_dot,
                           label="Aftercooler",
                           extra={"UA": UA, "LMTD": lmtd})
