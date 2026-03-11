"""
components/hx_recuperator.py
─────────────────────────────
역류형 리큐퍼레이터 (effectiveness 기반).

  hot side  : 고압 스트림이 열을 방출  (Q_dot < 0)
  cold side : 저압 스트림이 열을 흡수  (Q_dot > 0)

  평형 유량 (m_dot_hot = m_dot_cold = m_dot) 가정.

  ε 정의 (온도 기반):
    ε = (T_hot_in - T_hot_out) / (T_hot_in - T_cold_in)
  ∴ T_hot_out = T_hot_in - ε * (T_hot_in - T_cold_in)

  에너지 수지 (실제 엔탈피 기반):
    Q = m_dot * (h_hot_in - h_hot_out)          [정확]
    h_cold_out = h_cold_in + Q / m_dot          [정확]
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from properties import ThermodynamicState, ComponentResult, state_from_TP, state_from_hP


def run(state_hot_in: ThermodynamicState,
        state_cold_in: ThermodynamicState,
        effectiveness: float,
        m_dot: float) -> tuple[ComponentResult, ComponentResult]:
    """
    Parameters
    ----------
    state_hot_in   : ThermodynamicState  고압(hot) 스트림 입구
    state_cold_in  : ThermodynamicState  저압(cold) 스트림 입구
    effectiveness  : float               열교환 효율 ε  [0, 1]
    m_dot          : float               질량 유량 [kg/s] (양측 동일)

    Returns
    -------
    (result_hot, result_cold) : tuple[ComponentResult, ComponentResult]
        result_hot  : hot 스트림 출구 (Q_dot < 0)
        result_cold : cold 스트림 출구 (Q_dot > 0)
    """
    if state_hot_in.T <= state_cold_in.T:
        raise ValueError(
            f"Recuperator: T_hot_in ({state_hot_in.T:.2f} K) "
            f"<= T_cold_in ({state_cold_in.T:.2f} K)"
        )
    if not (0.0 < effectiveness <= 1.0):
        raise ValueError(f"Recuperator: effectiveness={effectiveness} 는 (0, 1] 범위여야 함.")

    # hot side 출구 온도 (ε 정의)
    T_hot_out = state_hot_in.T - effectiveness * (state_hot_in.T - state_cold_in.T)
    state_hot_out = state_from_TP(T_hot_out, state_hot_in.P,
                                  fluid=state_hot_in.fluid, label="RecupHotOut")

    # hot side 열량 (음수: 방열)
    Q_hot = m_dot * (state_hot_out.h - state_hot_in.h)   # < 0

    # cold side 출구 엔탈피 (에너지 수지)
    h_cold_out = state_cold_in.h + (-Q_hot / m_dot)      # = h_cold_in + |Q_hot|/m_dot
    state_cold_out = state_from_hP(h_cold_out, state_cold_in.P,
                                   fluid=state_cold_in.fluid, label="RecupColdOut")

    # cold side 열량 (양수: 흡열)
    Q_cold = m_dot * (state_cold_out.h - state_cold_in.h)   # > 0

    result_hot  = ComponentResult(state_out=state_hot_out,  W_dot=0.0,
                                  Q_dot=Q_hot,  label="RecupHot")
    result_cold = ComponentResult(state_out=state_cold_out, W_dot=0.0,
                                  Q_dot=Q_cold, label="RecupCold")
    return result_hot, result_cold
