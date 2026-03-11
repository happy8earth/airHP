"""
components/hx_load.py
─────────────────────
Load HX: 냉동 부하 흡수 모델 (UA·LMTD counter-flow).

  hot  side : IM-7 (냉동 공간)   T_sec_in → T_sec_out
  cold side : working fluid (Air)  State 4 → State 1
  Q_dot > 0  (working fluid 기준, 열 흡수 = 냉동 능력)
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
    state_in    : ThermodynamicState  팽창기 출구 상태 (State 4)
    UA_rated    : float               정격 UA [W/K]
    m_dot       : float               1차측(IM-7) 질량 유량 기준 — 여기서는 cold(Air) 유량 [kg/s]
    m_dot_rated : float               정격 1차측(IM-7) 유량 [kg/s]
    T_sec       : float               IM-7 입구 온도 [K]  (hot side)
    m_dot_sec   : float               IM-7 유량 [kg/s]

    Returns
    -------
    ComponentResult
        state_out : 압축기 입구 상태 (State 1)
        W_dot     : 0.0
        Q_dot     : > 0  (냉동 능력, working fluid 열 흡수)
    """
    # IM-7이 Air보다 차갑거나 같으면 열전달 불가 (Q_dot = 0)
    if T_sec <= state_in.T:
        return ComponentResult(state_out=state_from_TP(state_in.T, state_in.P,
                                fluid=state_in.fluid, label="LoadHX_out"),
                               W_dot=0.0, Q_dot=0.0, label="LoadHX")

    UA = ua_scale(UA_rated, m_dot_sec, m_dot_rated)

    # hot = IM-7 (T_sec), cold = Air (state_in)
    _T_sec_out, T_cold_out, Q_cf, lmtd = solve_counterflow(
        UA,
        T_sec,       101325.0,   "IM7",             # hot side: IM-7
        state_in.T,  state_in.P, state_in.fluid,    # cold side: Air
        m_dot_sec, m_dot,
    )

    state_out = state_from_TP(T_cold_out, state_in.P,
                               fluid=state_in.fluid, label="LoadHX_out")
    return ComponentResult(state_out=state_out, W_dot=0.0, Q_dot=Q_cf,
                           label="LoadHX",
                           extra={"UA": UA, "LMTD": lmtd})
