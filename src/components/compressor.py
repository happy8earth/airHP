"""
components/compressor.py
────────────────────────
비등엔트로피 압축기 모델.

  in → out_s : 등엔트로피 압축 (이상)
  in → out   : 실제 압축 (η_c 적용)

  h_out_s = f(s_in, P_out)
  h_out   = h_in + (h_out_s - h_in) / η_c
  W_dot   = m_dot * (h_out - h_in)   [W, 양수 = 소비]
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
    state_in : ThermodynamicState  압축기 입구 상태
    P_out    : float               출구 압력 [Pa]
    eta_c    : float               등엔트로피 효율 [-]
    m_dot    : float               질량 유량 [kg/s]

    Returns
    -------
    ComponentResult
        state_out : 압축기 출구 상태
        W_dot     : 소비 동력 [W], 양수
        Q_dot     : 0.0
    """
    # 등엔트로피 출구 (이상, ideal)
    state_out_s = state_from_sP(state_in.s, P_out,
                                fluid=state_in.fluid, label="CompressorOut_s")

    # 실제 출구 엔탈피
    h_out = state_in.h + (state_out_s.h - state_in.h) / eta_c

    # 실제 출구 상태
    state_out = state_from_hP(h_out, P_out,
                               fluid=state_in.fluid, label="CompressorOut")

    W_dot = m_dot * (state_out.h - state_in.h)   # 양수

    return ComponentResult(state_out=state_out, W_dot=W_dot, Q_dot=0.0,
                           label="Compressor")
