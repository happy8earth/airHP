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
from components.hx_ua_lmtd import ua_scale_two_side, solve_counterflow


def run(state_in: ThermodynamicState,
        htc_hot_rated:    float,
        area_hot:         float,
        m_dot_hot:        float,
        m_dot_hot_rated:  float,
        htc_cold_rated:   float,
        area_cold:        float,
        m_dot_cold:       float,
        m_dot_cold_rated: float,
        T_sec:            float) -> ComponentResult:
    """
    Parameters
    ----------
    state_in          : ThermodynamicState  압축기 출구 상태 (State 2)
    htc_hot_rated     : float  정격 hot side HTC [W/m²K]  (Air)
    area_hot          : float  hot side 면적 [m²]
    m_dot_hot         : float  실제 Air 유량 [kg/s]
    m_dot_hot_rated   : float  정격 Air 유량 [kg/s]
    htc_cold_rated    : float  정격 cold side HTC [W/m²K]  (water)
    area_cold         : float  cold side 면적 [m²]
    m_dot_cold        : float  실제 냉각수 유량 [kg/s]
    m_dot_cold_rated  : float  정격 냉각수 유량 [kg/s]
    T_sec             : float  냉각수 입구 온도 [K]

    Returns
    -------
    ComponentResult
        state_out : 팽창기 입구 상태 (State 3)
        W_dot     : 0.0
        Q_dot     : < 0  (working fluid 열 방출)
    """
    UA = ua_scale_two_side(
        htc_hot_rated, area_hot,  m_dot_hot,  m_dot_hot_rated,
        htc_cold_rated, area_cold, m_dot_cold, m_dot_cold_rated,
    )

    T_hot_out, T_sec_out, Q_cf, lmtd = solve_counterflow(
        UA,
        state_in.T, state_in.P, state_in.fluid,   # hot side
        T_sec,      101325.0,   "water",           # cold side (P 무시)
        m_dot_hot, m_dot_cold,
    )

    state_out = state_from_TP(T_hot_out, state_in.P,
                               fluid=state_in.fluid, label="Aftercooler_out")
    Q_dot = -Q_cf   # working fluid 기준: 열 방출 → 음수
    return ComponentResult(state_out=state_out, W_dot=0.0, Q_dot=Q_dot,
                           label="Aftercooler",
                           extra={"UA": UA, "LMTD": lmtd, "T_sec_out": T_sec_out})
