"""
cycles/bypass_a_brayton.py
──────────────────────────
Bypass Topology A — Recuperated Brayton cycle with compressor-outlet bleed.

State mapping:
  State 1  → [Compressor]                    → State 2
  State 2  → [Splitter x]                    → State 2_main (1-x)·ṁ
                                             → State 2_bypass   x·ṁ
  State 2_main → [Aftercooler, (1-x)·ṁ]     → State 3
  State 3  → [Recup.hot,  m_dot=(1-x)·ṁ]    → State 4
  State 4  + State 2_bypass → [Mixer]        → State 4m
  State 4m → [Expander,  ṁ]                 → State 5
  State 5  → [Load HX,   ṁ]                 → State 6
  State 6  → [Recup.cold, m_dot=ṁ]          → State 1 (next iter)

Couplings:
  - T1 (compressor inlet) depends on Recup cold outlet → outer fixed-point iteration
  - T4 (Recup hot outlet / before Mixer) solved by inner brentq
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scipy.optimize import brentq

from properties import state_from_TP, ComponentResult
from components import compressor, expander
from components import hx_aftercooler, hx_load
from components.splitter import run as splitter_run
from components.mixer import run as mixer_run
import components.hx_recuperator as hx_recuperator


STATE_LABELS = [
    "1 (C-in / Recup-out)",
    "2 (C-out / Splitter-in)",
    "3 (AC-out / Recup.hot-in)",
    "4 (Recup.hot-out)",
    "4m (Mixer-out / E-in)",
    "5 (E-out / Load-in)",
    "6 (Load-out / Recup.cold-in)",
]


def run_cycle(config: dict, P_high: float, x: float) -> dict:
    """
    Parameters
    ----------
    config  : dict   YAML 설정
    P_high  : float  고압 [Pa]
    x       : float  bypass 분율 [-]  (0 ≤ x < 1)

    Returns
    -------
    dict with keys:
        states             : list[ThermodynamicState]  State1 ~ State6 + State4m
        T_expander_outlet  : float  [K]  State5 온도
        T_sec_out          : float  [K]  Load HX 2차측(IM-7) 출구온도
        component_results  : list[ComponentResult]
        Q_cold             : float  [W]
        W_compressor       : float  [W]
        W_expander         : float  [W]
        Q_recuperator      : float  [W]
    """
    fluid = config["fluid"]
    m_dot = config["mass_flow"]
    eta_c = config["comp"]["eta_isen"]
    eta_t = config["expander"]["eta_isen"]
    P_low = config["P_low"]

    rc      = config["hx_recup"]
    rc_hot  = rc["hotside"]
    rc_cold = rc["coldside"]

    ac      = config["hx_aftercooler"]
    ac_hot  = ac["hotside"]
    ac_cold = ac["coldside"]

    lhx      = config["hx_load"]
    lhx_hot  = lhx["hotside"]
    lhx_cold = lhx["coldside"]

    m_dot_main   = (1.0 - x) * m_dot   # Aftercooler / Recup.hot 측 유량
    m_dot_bypass = x * m_dot            # Bypass 스트림 유량

    # T1 초기 추정값
    T1 = config["comp"]["T_inlet"]

    for _ in range(30):
        # State 1: 압축기 입구
        state1 = state_from_TP(T1, P_low, fluid, "State1")

        # Compressor: 1 → 2
        comp_res = compressor.run(state1, P_out=P_high, eta_c=eta_c, m_dot=m_dot)
        state2 = comp_res.state_out

        # Splitter: 2 → 2_main (1-x)·ṁ  +  2_bypass x·ṁ
        split_res = splitter_run(state2, x=x, m_dot=m_dot)
        state2_main   = split_res.state_main
        state2_bypass = split_res.state_bypass

        # Aftercooler: 2_main → 3  ((1-x)·ṁ)
        ac_res = hx_aftercooler.run(
            state2_main,
            htc_hot_rated=ac_hot["htc_rated"],
            area_hot=ac_hot["area"],
            m_dot_hot=m_dot_main,
            m_dot_hot_rated=ac_hot["m_dot_rated"],
            htc_cold_rated=ac_cold["htc_rated"],
            area_cold=ac_cold["area"],
            m_dot_cold=ac_cold["m_dot_rated"],
            m_dot_cold_rated=ac_cold["m_dot_rated"],
            T_sec=ac_cold["T_inlet"],
        )
        state3 = ac_res.state_out

        # Inner brentq: T4 수렴 (Recup.hot 출구 자기일관성)
        def _residual(T4_K: float) -> float:
            _s4 = state_from_TP(T4_K, P_high, fluid)
            # Mixer: State4 + State2_bypass → State4m
            _mix = mixer_run(_s4, m_dot_main, state2_bypass, m_dot_bypass)
            _s4m = _mix.state_out
            # Expander: 4m → 5  (전체 유량 ṁ)
            _s5 = expander.run(_s4m, P_out=P_low, eta_t=eta_t, m_dot=m_dot).state_out
            # Load HX: 5 → 6
            _lhx = hx_load.run(
                _s5,
                htc_hot_rated=lhx_hot["htc_rated"],
                area_hot=lhx_hot["area"],
                m_dot_hot=lhx_hot["m_dot_rated"],
                m_dot_hot_rated=lhx_hot["m_dot_rated"],
                htc_cold_rated=lhx_cold["htc_rated"],
                area_cold=lhx_cold["area"],
                m_dot_cold=m_dot,
                m_dot_cold_rated=lhx_cold["m_dot_rated"],
                T_sec=lhx_hot["T_inlet"],
            )
            _s6 = _lhx.state_out
            # Recup.hot: 3 → 4  (hot=(1-x)·ṁ, cold=ṁ)
            _recup_hot, _ = hx_recuperator.run(
                state3, _s6,
                htc_hot_rated=rc_hot["htc_rated"],
                area_hot=rc_hot["area"],
                m_dot_hot_rated=rc_hot["m_dot_rated"],
                htc_cold_rated=rc_cold["htc_rated"],
                area_cold=rc_cold["area"],
                m_dot_cold_rated=rc_cold["m_dot_rated"],
                m_dot=m_dot,
                m_dot_hot=m_dot_main,
                m_dot_cold=m_dot,
            )
            return T4_K - _recup_hot.state_out.T

        T4_lo, T4_hi = 140.0, state3.T
        if _residual(T4_lo) * _residual(T4_hi) > 0:
            raise ValueError(
                f"Recuperator inner solve: [{T4_lo:.1f}, {T4_hi:.1f}] K "
                f"no sign change. x={x:.4f}, P_high={P_high/1e3:.1f} kPa"
            )
        T4_sol = brentq(_residual, T4_lo, T4_hi, xtol=0.01, rtol=1e-6)
        state4 = state_from_TP(T4_sol, P_high, fluid, "State4")

        # Mixer: State4 + State2_bypass → State4m
        mix_res = mixer_run(state4, m_dot_main, state2_bypass, m_dot_bypass)
        state4m = mix_res.state_out

        # Expander: 4m → 5  (전체 유량 ṁ)
        exp_res = expander.run(state4m, P_out=P_low, eta_t=eta_t, m_dot=m_dot)
        state5 = exp_res.state_out

        # Load HX: 5 → 6
        loadhx_res = hx_load.run(
            state5,
            htc_hot_rated=lhx_hot["htc_rated"],
            area_hot=lhx_hot["area"],
            m_dot_hot=lhx_hot["m_dot_rated"],
            m_dot_hot_rated=lhx_hot["m_dot_rated"],
            htc_cold_rated=lhx_cold["htc_rated"],
            area_cold=lhx_cold["area"],
            m_dot_cold=m_dot,
            m_dot_cold_rated=lhx_cold["m_dot_rated"],
            T_sec=lhx_hot["T_inlet"],
        )
        state6 = loadhx_res.state_out

        # Recup: hot (3→4), cold (6→1)  hot=(1-x)·ṁ, cold=ṁ
        recup_hot, recup_cold = hx_recuperator.run(
            state3, state6,
            htc_hot_rated=rc_hot["htc_rated"],
            area_hot=rc_hot["area"],
            m_dot_hot_rated=rc_hot["m_dot_rated"],
            htc_cold_rated=rc_cold["htc_rated"],
            area_cold=rc_cold["area"],
            m_dot_cold_rated=rc_cold["m_dot_rated"],
            m_dot=m_dot,
            m_dot_hot=m_dot_main,
            m_dot_cold=m_dot,
        )

        T1_new = recup_cold.state_out.T
        if abs(T1_new - T1) < 0.05:
            T1 = T1_new
            break
        T1 = T1_new
        if T1 > 500.0:
            # 고 bypass 구간에서 외부 반복 발산 감지 (T5 > T_IM7 → Load HX Q=0 → 리큐퍼 역전 → T1↑)
            raise ValueError(
                f"bypass_a_brayton: T1 발산 (T1={T1:.1f} K). "
                f"x={x:.4f} 는 안정 수렴 불가 구간입니다 (Load HX 냉동 불가 영역)."
            )

    state1 = state_from_TP(T1, P_low, fluid, "State1")

    # T_sec_out: Load HX 2차측(IM-7) 출구온도
    T_sec_out = loadhx_res.extra.get("T_sec_out", None)

    states = [state1, state2, state3, state4, state4m, state5, state6]
    component_results = [comp_res, ac_res, recup_hot, mix_res, exp_res, loadhx_res, recup_cold]

    return dict(
        states            = states,
        T_expander_outlet = state5.T,
        T_sec_out         = T_sec_out,
        component_results = component_results,
        Q_cold            = loadhx_res.Q_dot,
        W_compressor      = comp_res.W_dot,
        W_expander        = -exp_res.W_dot,
        Q_recuperator     = -recup_hot.Q_dot,
    )
