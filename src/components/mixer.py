"""
components/mixer.py
───────────────────
질량 유량 혼합기 (adiabatic mixer).

  state_a (m_dot_a) ─┐
                      ├→ [Mixer] → state_out (m_dot_a + m_dot_b)
  state_b (m_dot_b) ─┘

물리: 단열 혼합 (Q=0, W=0)
  h_mix = (ṁ_a·h_a + ṁ_b·h_b) / (ṁ_a + ṁ_b)
  P_mix = state_a.P  (양측 압력 동일 가정)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from properties import ThermodynamicState, ComponentResult, state_from_hP


def run(state_a: ThermodynamicState, m_dot_a: float,
        state_b: ThermodynamicState, m_dot_b: float) -> ComponentResult:
    """
    Parameters
    ----------
    state_a  : ThermodynamicState  스트림 A 입구 상태
    m_dot_a  : float               스트림 A 질량 유량 [kg/s]
    state_b  : ThermodynamicState  스트림 B 입구 상태
    m_dot_b  : float               스트림 B 질량 유량 [kg/s]

    Returns
    -------
    ComponentResult
        state_out : 혼합 출구 상태  (P = state_a.P)
        W_dot     : 0.0
        Q_dot     : 0.0
        extra     : {"m_dot_out": m_dot_a + m_dot_b}

    Raises
    ------
    ValueError  양측 유체 종류 또는 압력이 다를 경우
    """
    if state_a.fluid != state_b.fluid:
        raise ValueError(
            f"Mixer: 유체 불일치 ({state_a.fluid} vs {state_b.fluid})"
        )
    if abs(state_a.P - state_b.P) / state_a.P > 1e-3:
        raise ValueError(
            f"Mixer: 압력 불일치 ({state_a.P/1e3:.2f} kPa vs {state_b.P/1e3:.2f} kPa)"
        )

    m_dot_out = m_dot_a + m_dot_b
    h_mix = (m_dot_a * state_a.h + m_dot_b * state_b.h) / m_dot_out

    state_out = state_from_hP(h_mix, state_a.P,
                               fluid=state_a.fluid, label="MixerOut")

    return ComponentResult(state_out=state_out, W_dot=0.0, Q_dot=0.0,
                           label="Mixer",
                           extra={"m_dot_out": m_dot_out})
