"""
components/turbine.py
─────────────────────
비등엔트로피 터빈 모델.

  2'→3s : 등엔트로피 팽창 (이상)
  2'→3  : 실제 팽창 (η_t 적용)

  h_3s = f(s_2', P_3)
  h_3  = h_2' - η_t * (h_2' - h_3s)
  W_dot = m_dot * (h_3 - h_2')   [W, 음수 = 발생]
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from properties import ThermodynamicState, ComponentResult, state_from_sP, state_from_hP


def run(state_in: ThermodynamicState,
        P_out: float,
        eta_t: float,
        m_dot: float) -> ComponentResult:
    """
    Parameters
    ----------
    state_in : ThermodynamicState  터빈 입구 상태 (State 2')
    P_out    : float               출구 압력 [Pa]
    eta_t    : float               등엔트로피 효율 [-]
    m_dot    : float               질량 유량 [kg/s]

    Returns
    -------
    ComponentResult
        state_out : 터빈 출구 상태 (State 3)
        W_dot     : 발생 동력 [W], 음수
        Q_dot     : 0.0
    """
    # 등엔트로피 출구 (이상)
    state_3s = state_from_sP(state_in.s, P_out,
                              fluid=state_in.fluid, label="State3s")

    # 실제 출구 엔탈피
    h_3 = state_in.h - eta_t * (state_in.h - state_3s.h)

    # 실제 출구 상태
    state_out = state_from_hP(h_3, P_out,
                               fluid=state_in.fluid, label="State3")

    W_dot = m_dot * (state_out.h - state_in.h)   # 음수

    return ComponentResult(state_out=state_out, W_dot=W_dot, Q_dot=0.0,
                           label="Turbine")
