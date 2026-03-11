"""
components/hx_base.py
─────────────────────
등압 열교환 공통 로직 (내부용).

  hx_aftercooler.py, hx_load.py 의 베이스.
  직접 호출하지 말고 각 전용 모듈을 사용할 것.

  부호 규칙 (표준 열역학, ΣW_dot + ΣQ_dot = 0 만족):
    Q_dot < 0 : 유체가 열을 방출 (h_out < h_in) → Hot HX
    Q_dot > 0 : 유체가 열을 흡수 (h_out > h_in) → Cold HX  ← 냉동 능력
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from properties import ThermodynamicState, ComponentResult, state_from_TP


def run(state_in: ThermodynamicState,
        T_out: float,
        m_dot: float,
        label: str = "HX") -> ComponentResult:
    """
    Parameters
    ----------
    state_in : ThermodynamicState  입구 상태
    T_out    : float               출구 온도 [K]
    m_dot    : float               질량 유량 [kg/s]
    label    : str                 식별자

    Returns
    -------
    ComponentResult
        state_out : 출구 상태 (P = state_in.P 유지)
        W_dot     : 0.0
        Q_dot     : 열량 [W]  Hot HX: 음수 / Cold HX: 양수
    """
    state_out = state_from_TP(T_out, state_in.P,
                               fluid=state_in.fluid, label=label + "_out")
    Q_dot = m_dot * (state_out.h - state_in.h)   # 표준 규칙: h_out - h_in
    return ComponentResult(state_out=state_out, W_dot=0.0, Q_dot=Q_dot,
                           label=label)
