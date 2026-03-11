"""
components/hx_heat_absorption.py
─────────────────────────────────
Cold HX: 냉동 부하 흡수 모델.

  3 → 1 : 터빈 출구(저압, 극저온) → 압축기 입구(저압, 복귀)
  Q_dot > 0  (유체가 냉동 공간에서 열 흡수 = 냉동 능력)
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
    state_in : ThermodynamicState  터빈 출구 상태 (State 3)
    T_out    : float               압축기 입구 온도 [K]  (State 1)
    m_dot    : float               질량 유량 [kg/s]

    Returns
    -------
    ComponentResult
        state_out : 압축기 입구 상태 (State 1)
        W_dot     : 0.0
        Q_dot     : > 0  (냉동 능력, 유체가 열 흡수)
    """
    return _base_run(state_in, T_out, m_dot, label="ColdHX")
