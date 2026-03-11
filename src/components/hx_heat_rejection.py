"""
components/hx_heat_rejection.py
────────────────────────────────
Hot HX: 고압측 등압 열 방출 모델.

  2 → 2' : 압축기 출구(고압, 고온) → 터빈 입구(고압, 냉각)
  Q_dot < 0  (유체가 대기/냉각수에 열 방출)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from properties import ThermodynamicState, ComponentResult
from components.hx_base import run as _base_run


def run(state_in: ThermodynamicState,
        T_out: float,
        m_dot: float) -> ComponentResult:
    """
    Parameters
    ----------
    state_in : ThermodynamicState  압축기 출구 상태 (State 2)
    T_out    : float               터빈 입구 온도 [K]  (State 2')
    m_dot    : float               질량 유량 [kg/s]

    Returns
    -------
    ComponentResult
        state_out : 터빈 입구 상태 (State 2')
        W_dot     : 0.0
        Q_dot     : < 0  (유체가 열 방출)
    """
    return _base_run(state_in, T_out, m_dot, label="HotHX")
