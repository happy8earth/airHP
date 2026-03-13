"""
components/hx_recuperator.py
─────────────────────────────
역류형 리큐퍼레이터 (UA·LMTD 기반).

  hot side  : 고압 스트림 (State 3 → State 4)  Q_dot < 0
  cold side : 저압 스트림 (State 6 → State 1)  Q_dot > 0

  양측 모두 작동 유체(Air) — CoolProp, 서로 다른 압력.

  UA scaling (각 측 독립):
    hA_i = htc_i_rated × area_i × (m_dot_i / m_dot_i_rated)^0.8
    UA   = 1 / (1/hA_hot + 1/hA_cold)

  Bypass 사이클에서 hot/cold 유량이 다를 수 있음:
    m_dot_hot  = (1-x)·ṁ  (Aftercooler → Recuperator hot side)
    m_dot_cold = ṁ        (Recuperator cold side → Compressor)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from properties import ThermodynamicState, ComponentResult, state_from_TP
from components.hx_ua_lmtd import ua_scale_two_side, solve_counterflow


def run(state_hot_in: ThermodynamicState,
        state_cold_in: ThermodynamicState,
        htc_hot_rated:    float,
        area_hot:         float,
        m_dot_hot_rated:  float,
        htc_cold_rated:   float,
        area_cold:        float,
        m_dot_cold_rated: float,
        m_dot:            float,
        m_dot_hot:        float = None,
        m_dot_cold:       float = None) -> tuple[ComponentResult, ComponentResult]:
    """
    Parameters
    ----------
    state_hot_in      : ThermodynamicState  고압(hot) 스트림 입구 (State 3)
    state_cold_in     : ThermodynamicState  저압(cold) 스트림 입구 (State 6)
    htc_hot_rated     : float  정격 hot side HTC [W/m²K]
    area_hot          : float  hot side 면적 [m²]
    m_dot_hot_rated   : float  정격 hot side 유량 [kg/s]
    htc_cold_rated    : float  정격 cold side HTC [W/m²K]
    area_cold         : float  cold side 면적 [m²]
    m_dot_cold_rated  : float  정격 cold side 유량 [kg/s]
    m_dot             : float  기본 질량 유량 [kg/s] (m_dot_hot/cold 미지정 시 양측에 사용)
    m_dot_hot         : float  실제 hot side 유량 [kg/s] (None → m_dot 사용)
    m_dot_cold        : float  실제 cold side 유량 [kg/s] (None → m_dot 사용)

    Returns
    -------
    (result_hot, result_cold) : tuple[ComponentResult, ComponentResult]
        result_hot  : hot 스트림 출구 (Q_dot < 0)
        result_cold : cold 스트림 출구 (Q_dot > 0)
    """
    mdot_hot  = m_dot_hot  if m_dot_hot  is not None else m_dot
    mdot_cold = m_dot_cold if m_dot_cold is not None else m_dot

    UA = ua_scale_two_side(
        htc_hot_rated, area_hot,  mdot_hot,  m_dot_hot_rated,
        htc_cold_rated, area_cold, mdot_cold, m_dot_cold_rated,
    )

    dT_in = state_hot_in.T - state_cold_in.T

    if abs(dT_in) < 1e-6:
        # 완전 동온 → Q = 0
        result_hot  = ComponentResult(state_out=state_hot_in,  W_dot=0.0, Q_dot=0.0,
                                      label="RecupHot",
                                      extra={"UA": UA, "LMTD": 0.0, "Q_signed": 0.0})
        result_cold = ComponentResult(state_out=state_cold_in, W_dot=0.0, Q_dot=0.0,
                                      label="RecupCold",
                                      extra={"Q_signed": 0.0})
        return result_hot, result_cold

    if dT_in < 0:
        # 온도 역전: cold inlet > hot inlet → hot/cold 스왑하여 solve_counterflow 재호출.
        # Q_swapped > 0 = 실제 cold→hot 방향 열전달.
        T_cold_out_sol, T_hot_out_sol, _, lmtd = solve_counterflow(
            UA,
            state_cold_in.T, state_cold_in.P, state_cold_in.fluid,  # swapped "hot"
            state_hot_in.T,  state_hot_in.P,  state_hot_in.fluid,   # swapped "cold"
            mdot_cold, mdot_hot,
        )
        state_hot_out  = state_from_TP(T_hot_out_sol,  state_hot_in.P,
                                        fluid=state_hot_in.fluid,  label="RecupHotOut")
        state_cold_out = state_from_TP(T_cold_out_sol, state_cold_in.P,
                                        fluid=state_cold_in.fluid, label="RecupColdOut")
        Q_hot  = mdot_hot  * (state_hot_out.h  - state_hot_in.h)   # > 0 (흡열)
        Q_cold = mdot_cold * (state_cold_out.h - state_cold_in.h)  # < 0 (방열)
        result_hot  = ComponentResult(state_out=state_hot_out,  W_dot=0.0,
                                      Q_dot=Q_hot,  label="RecupHot",
                                      extra={"UA": UA, "LMTD": lmtd, "Q_signed": Q_hot})
        result_cold = ComponentResult(state_out=state_cold_out, W_dot=0.0,
                                      Q_dot=Q_cold, label="RecupCold",
                                      extra={"Q_signed": Q_cold})
        return result_hot, result_cold

    # 정방향 (T_hot > T_cold)
    T_hot_out, T_cold_out, _, lmtd = solve_counterflow(
        UA,
        state_hot_in.T,  state_hot_in.P,  state_hot_in.fluid,   # hot side
        state_cold_in.T, state_cold_in.P, state_cold_in.fluid,   # cold side
        mdot_hot, mdot_cold,
    )

    state_hot_out  = state_from_TP(T_hot_out,  state_hot_in.P,
                                    fluid=state_hot_in.fluid,  label="RecupHotOut")
    state_cold_out = state_from_TP(T_cold_out, state_cold_in.P,
                                    fluid=state_cold_in.fluid, label="RecupColdOut")

    Q_hot  = mdot_hot  * (state_hot_out.h  - state_hot_in.h)   # < 0
    Q_cold = mdot_cold * (state_cold_out.h - state_cold_in.h)  # > 0

    result_hot  = ComponentResult(state_out=state_hot_out,  W_dot=0.0,
                                  Q_dot=Q_hot,  label="RecupHot",
                                  extra={"UA": UA, "LMTD": lmtd, "Q_signed": Q_hot})
    result_cold = ComponentResult(state_out=state_cold_out, W_dot=0.0,
                                  Q_dot=Q_cold, label="RecupCold",
                                  extra={"Q_signed": Q_cold})
    return result_hot, result_cold
