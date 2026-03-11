"""
cycles/simple_brayton.py
────────────────────────
단순 역브레이튼 사이클 위상(topology) 정의.

상태점 흐름:
  State 1 → [Compressor] → State 2
  State 2 → [Hot HX]     → State 3
  State 3 → [Turbine]    → State 4
  State 4 → [Cold HX]    → State 1

SEQUENCE: cycle_solver.py 가 순차 실행할 컴포넌트 목록.
각 항목 형식: (label, component_fn, extra_kwargs_builder)
  - label             : 결과 식별자
  - component_fn      : run(state_in, ...) → ComponentResult
  - extra_kwargs_fn   : config + state_in 을 받아 나머지 kwargs 반환하는 함수
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from components import compressor, turbine
from components import hx_heat_rejection, hx_heat_absorption


def _compressor_kwargs(config: dict, state_in, P_high: float) -> dict:
    return dict(P_out=P_high, eta_c=config["comp"]["eta_isen"], m_dot=config["mass_flow"])


def _hot_hx_kwargs(config: dict, state_in, P_high: float) -> dict:
    return dict(T_out=config["hx_hotside"]["T_outlet"], m_dot=config["mass_flow"])


def _turbine_kwargs(config: dict, state_in, P_high: float) -> dict:
    return dict(P_out=config["P_low"], eta_t=config["turbine"]["eta_isen"], m_dot=config["mass_flow"])


def _cold_hx_kwargs(config: dict, state_in, P_high: float) -> dict:
    return dict(T_out=config["comp"]["T_inlet"], m_dot=config["mass_flow"])


STATE_LABELS = [
    "1 (C-in)",
    "2 (C-out)",
    "3 (T-in)",
    "4 (T-out)",
]

# cycle_solver.py 가 읽는 SEQUENCE
# 각 항목: (label, component_fn, kwargs_fn)
SEQUENCE = [
    ("Compressor", compressor.run,          _compressor_kwargs),
    ("HotHX",      hx_heat_rejection.run,   _hot_hx_kwargs),
    ("Turbine",    turbine.run,             _turbine_kwargs),
    ("ColdHX",     hx_heat_absorption.run,  _cold_hx_kwargs),
]
