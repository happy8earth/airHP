"""
components/compressor.py
────────────────────────
비등엔트로피 압축기 모델.

  1→2s : 등엔트로피 압축 (이상)
  1→2  : 실제 압축 (η_c 적용)

  h_2s = f(s_1, P_2)
  h_2  = h_1 + (h_2s - h_1) / η_c
  W_dot = m_dot * (h_2 - h_1)   [W, 양수 = 소비]
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from properties import ThermodynamicState, ComponentResult, state_from_sP, state_from_hP


def run(state_in: ThermodynamicState,
        P_out: float,
        eta_c: float,
        m_dot: float) -> ComponentResult:
    """
    Parameters
    ----------
    state_in : ThermodynamicState  압축기 입구 상태 (State 1)
    P_out    : float               출구 압력 [Pa]
    eta_c    : float               등엔트로피 효율 [-]
    m_dot    : float               질량 유량 [kg/s]

    Returns
    -------
    ComponentResult
        state_out : 압축기 출구 상태 (State 2)
        W_dot     : 소비 동력 [W], 양수
        Q_dot     : 0.0
    """
    # 등엔트로피 출구 (이상)
    state_2s = state_from_sP(state_in.s, P_out,
                              fluid=state_in.fluid, label="State2s")

    # 실제 출구 엔탈피
    h_2 = state_in.h + (state_2s.h - state_in.h) / eta_c

    # 실제 출구 상태
    state_out = state_from_hP(h_2, P_out,
                               fluid=state_in.fluid, label="State2")

    W_dot = m_dot * (state_out.h - state_in.h)   # 양수

    return ComponentResult(state_out=state_out, W_dot=W_dot, Q_dot=0.0,
                           label="Compressor")
