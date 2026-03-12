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
from components.hx_ua_lmtd import ua_scale_two_side, solve_counterflow


def run(state_in: ThermodynamicState,
        htc_hot_rated:   float,
        area_hot:        float,
        m_dot_hot:       float,
        m_dot_hot_rated: float,
        htc_cold_rated:  float,
        area_cold:       float,
        m_dot_cold:      float,
        m_dot_cold_rated: float,
        T_sec:           float) -> ComponentResult:
    """
    Parameters
    ----------
    state_in         : ThermodynamicState  팽창기 출구 상태
    htc_hot_rated    : float  정격 hot side HTC [W/m²K]  (IM-7, 50:50 가정)
    area_hot         : float  hot side 면적 [m²]
    m_dot_hot        : float  실제 IM-7 유량 [kg/s]
    m_dot_hot_rated  : float  정격 IM-7 유량 [kg/s]
    htc_cold_rated   : float  정격 cold side HTC [W/m²K]  (Air, 50:50 가정)
    area_cold        : float  cold side 면적 [m²]
    m_dot_cold       : float  실제 Air 유량 [kg/s]
    m_dot_cold_rated : float  정격 Air 유량 [kg/s]
    T_sec            : float  IM-7 입구 온도 [K]  (hot side)

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

    UA = ua_scale_two_side(
        htc_hot_rated, area_hot,  m_dot_hot,  m_dot_hot_rated,
        htc_cold_rated, area_cold, m_dot_cold, m_dot_cold_rated,
    )

    # hot = IM-7 (T_sec), cold = Air (state_in)
    _T_sec_out, T_cold_out, Q_cf, lmtd = solve_counterflow(
        UA,
        T_sec,       101325.0,   "IM7",             # hot side: IM-7
        state_in.T,  state_in.P, state_in.fluid,    # cold side: Air
        m_dot_hot, m_dot_cold,
    )

    state_out = state_from_TP(T_cold_out, state_in.P,
                               fluid=state_in.fluid, label="LoadHX_out")
    return ComponentResult(state_out=state_out, W_dot=0.0, Q_dot=Q_cf,
                           label="LoadHX",
                           extra={"UA": UA, "LMTD": lmtd})
