"""
cycle_solver.py
───────────────
범용 사이클 솔버.

  1. config["cycle"] 에 해당하는 cycles/ 모듈을 동적 임포트
  2. pressure_ratio 가 null 이면 scipy brentq 로 P_high 역산
     (팽창기 출구 온도 = T_turbine_outlet 조건)
  3. 사이클 실행 방식:
       - 모듈에 run_cycle() 이 있으면 직접 호출  (recuperated_brayton 등)
       - 없으면 SEQUENCE 순차 실행              (simple_brayton 등)
  4. 에너지 평형 검증
  5. 성능 지표 계산 (COP, Q_cold, W_net)
  6. 결과 반환 (dict)
"""

import importlib
import sys
import os

from scipy.optimize import brentq

sys.path.insert(0, os.path.dirname(__file__))
from properties import state_from_TP


# ─────────────────────────────────────────────
# 결과 폴더명 생성
# ─────────────────────────────────────────────

def make_result_dir(config: dict) -> str:
    cycle = config["cycle"].replace("_brayton", "")
    rp    = f"rp{config['pressure_ratio']:.2f}"
    Tt    = f"Tt{int(config['expander']['T_outlet_target'])}K"
    etac  = f"etac{config['comp']['eta_isen']}"
    etat  = f"etat{config['expander']['eta_isen']}"
    return os.path.join("results", f"{cycle}__{rp}__{Tt}__{etac}__{etat}")


# ─────────────────────────────────────────────
# SEQUENCE 기반 실행 (simple_brayton 등)
# ─────────────────────────────────────────────

def _run_sequence(cycle_module, config: dict, P_high: float):
    """주어진 P_high 로 SEQUENCE 를 한 바퀴 실행하고 결과 리스트를 반환."""
    state = state_from_TP(
        config["comp"]["T_inlet"],
        config["P_low"],
        fluid=config["fluid"],
        label="State1",
    )
    results = []
    for label, fn, kwargs_fn in cycle_module.SEQUENCE:
        kwargs = kwargs_fn(config, state, P_high)
        result = fn(state, **kwargs)
        results.append(result)
        state = result.state_out
    return results


# ─────────────────────────────────────────────
# P_high 역산
# ─────────────────────────────────────────────

def _find_P_high(cycle_module, config: dict, use_run_cycle: bool) -> float:
    """
    scipy brentq 로 팽창기 출구 온도 = T_turbine_outlet 을 만족하는 P_high 탐색.
    """
    T_target = config["expander"]["T_outlet_target"]
    P_low    = config["P_low"]

    def error(P_high):
        if use_run_cycle:
            try:
                out = cycle_module.run_cycle(config, P_high)
                T_expander_out = out["T_expander_outlet"]
            except ValueError:
                # 작동 유체가 두 상 영역 진입 등 물리적으로 불가능한 조건
                # → 팽창기 출구가 목표보다 훨씬 낮다고 간주 (P_high 가 너무 큼)
                return T_target - 400.0
        else:
            results = _run_sequence(cycle_module, config, P_high)
            # Turbine 은 SEQUENCE 의 세 번째 항목 (index 2)
            T_expander_out = results[2].state_out.T
        return T_expander_out - T_target

    # 탐색 범위: 1.5 atm ~ 50 atm
    P_lo = P_low * 1.5
    P_hi = P_low * 50.0

    if error(P_lo) * error(P_hi) > 0:
        raise ValueError(
            f"brentq: 탐색 범위 [{P_lo/1e3:.1f}, {P_hi/1e3:.1f}] kPa 에서 "
            f"부호 변환 없음. T_expander_outlet={T_target:.2f} K 달성 불가능.\n"
            f"  T_expander at P_lo={error(P_lo)+T_target:.2f} K, "
            f"T_expander at P_hi={error(P_hi)+T_target:.2f} K"
        )

    P_high_sol = brentq(error, P_lo, P_hi, xtol=1.0, rtol=1e-8)
    return P_high_sol


# ─────────────────────────────────────────────
# 메인 솔버
# ─────────────────────────────────────────────

def solve(config: dict) -> dict:
    """
    Parameters
    ----------
    config : dict  (yaml 에서 로드한 설정)

    Returns
    -------
    dict with keys:
        cycle          : str
        pressure_ratio : float
        P_high         : float  [Pa]
        states         : list[ThermodynamicState]
        state_labels   : list[str]
        results        : list[ComponentResult]
        T_turbine_outlet : float  [K]
        Q_cold         : float  [W]
        W_compressor   : float  [W]
        W_turbine      : float  [W]
        W_net          : float  [W]
        COP            : float
        Q_recuperator  : float  [W]  (recuperated cycle 만 해당, 나머지는 0.0)
        energy_error   : float
        result_dir     : str
    """
    # 사이클 모듈 동적 임포트
    cycle_module = importlib.import_module(f"cycles.{config['cycle']}")
    use_run_cycle = hasattr(cycle_module, "run_cycle")

    # P_high 결정
    if config.get("pressure_ratio") is None:
        P_high = _find_P_high(cycle_module, config, use_run_cycle)
        config["pressure_ratio"] = P_high / config["P_low"]
    else:
        P_high = config["P_low"] * config["pressure_ratio"]

    # 사이클 실행
    if use_run_cycle:
        cycle_out = cycle_module.run_cycle(config, P_high)
        states            = cycle_out["states"]
        component_results = cycle_out["component_results"]
        T_expander_outlet  = cycle_out["T_expander_outlet"]
        Q_cold            = cycle_out["Q_cold"]
        W_compressor      = cycle_out["W_compressor"]
        W_expander         = cycle_out["W_expander"]
        Q_recuperator     = cycle_out.get("Q_recuperator", 0.0)
    else:
        seq_results = _run_sequence(cycle_module, config, P_high)
        state1 = state_from_TP(config["comp"]["T_inlet"], config["P_low"],
                                fluid=config["fluid"], label="State1")
        states = [
            state1,
            seq_results[0].state_out,   # Compressor 출구 → State 2
            seq_results[1].state_out,   # HotHX 출구      → State 3
            seq_results[2].state_out,   # Expander 출구    → State 4
        ]
        component_results = seq_results
        T_expander_outlet  = states[3].T
        Q_cold            = seq_results[3].Q_dot    # ColdHX, 양수
        W_compressor      = seq_results[0].W_dot    # 양수
        W_expander         = -seq_results[2].W_dot   # 음수→양수
        Q_recuperator     = 0.0

    # 성능 지표
    W_net = W_compressor - W_expander
    COP   = Q_cold / W_net

    # 에너지 평형 검증
    energy_residual = sum(r.W_dot + r.Q_dot for r in component_results)
    energy_error    = abs(energy_residual) / abs(Q_cold)

    result_dir = make_result_dir(config)

    return dict(
        cycle            = config["cycle"],
        pressure_ratio   = config["pressure_ratio"],
        P_high           = P_high,
        states           = states,
        state_labels     = cycle_module.STATE_LABELS,
        results          = component_results,
        T_expander_outlet = T_expander_outlet,
        Q_cold           = Q_cold,
        W_compressor     = W_compressor,
        W_expander        = W_expander,
        W_net            = W_net,
        COP              = COP,
        Q_recuperator    = Q_recuperator,
        energy_error     = energy_error,
        result_dir       = result_dir,
    )
