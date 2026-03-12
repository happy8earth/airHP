"""
components/splitter.py
──────────────────────
질량 유량 분기기 (splitter).

  state_in  ─(1-x)→  state_main   (m_dot_main  = (1-x)·m_dot)
            └──(x)→  state_bypass (m_dot_bypass =    x ·m_dot)

물리: 압력·엔탈피 변화 없음 (등압, 등엔탈피 분기).
      양측 출구 상태 = 입구 상태.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dataclasses import dataclass
from properties import ThermodynamicState


@dataclass
class SplitterResult:
    state_main:    ThermodynamicState   # (1-x) 스트림 상태 (= state_in)
    m_dot_main:    float                # (1-x)·m_dot  [kg/s]
    state_bypass:  ThermodynamicState   # x 스트림 상태 (= state_in)
    m_dot_bypass:  float                #    x·m_dot  [kg/s]


def run(state_in: ThermodynamicState,
        x: float,
        m_dot: float) -> SplitterResult:
    """
    Parameters
    ----------
    state_in : ThermodynamicState  분기 전 입구 상태
    x        : float               bypass 분율 [0, 1)  (x=0 → 분기 없음)
    m_dot    : float               총 질량 유량 [kg/s]

    Returns
    -------
    SplitterResult
        state_main    : (1-x) 스트림 상태 (Aftercooler 방향)
        m_dot_main    : (1-x)·m_dot  [kg/s]
        state_bypass  : x 스트림 상태 (Mixer 직행)
        m_dot_bypass  :    x·m_dot  [kg/s]
    """
    if not (0.0 <= x < 1.0):
        raise ValueError(f"Splitter: x={x:.4f} 범위 오류 (허용: 0 ≤ x < 1)")

    return SplitterResult(
        state_main=state_in,
        m_dot_main=(1.0 - x) * m_dot,
        state_bypass=state_in,
        m_dot_bypass=x * m_dot,
    )
