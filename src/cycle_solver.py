"""
cycle_solver.py
───────────────
범용 사이클 솔버.

  1. config["cycle"] 에 해당하는 cycles/ 모듈을 동적 임포트
  2. pressure_ratio 가 null 이면 scipy brentq 로 P_high 역산
     (터빈 출구 온도 = T_turbine_outlet 조건)
  3. SEQUENCE 순차 실행 → 상태점 + ComponentResult 수집
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
    Tt    = f"Tt{int(config['T_turbine_outlet'])}K"
    etac  = f"etac{config['eta_compressor']}"
    etat  = f"etat{config['eta_turbine']}"
    return os.path.join("results", f"{cycle}__{rp}__{Tt}__{etac}__{etat}")


# ─────────────────────────────────────────────
# 단일 압력비 실행
# ─────────────────────────────────────────────

def _run_sequence(cycle_module, config: dict, P_high: float):
    """주어진 P_high 로 SEQUENCE 를 한 바퀴 실행하고 결과 리스트를 반환."""
    state = state_from_TP(
        config["T_compressor_inlet"],
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
# P_high 역산 (T_3 고정 시)
# ─────────────────────────────────────────────

def _find_P_high(cycle_module, config: dict) -> float:
    """
    scipy brentq 로 터빈 출구 온도 = T_turbine_outlet 을 만족하는 P_high 탐색.

    turbine outlet 온도를 반환하는 내부 함수:
      error(P_high) = T_3_calc - T_3_target
    """
    T_target = config["T_turbine_outlet"]
    P_low    = config["P_low"]

    def error(P_high):
        results = _run_sequence(cycle_module, config, P_high)
        # Turbine 은 SEQUENCE 의 세 번째 항목 (index 2)
        T_3_calc = results[2].state_out.T
        return T_3_calc - T_target

    # 탐색 범위: 1.5 atm ~ 20 atm
    P_lo = P_low * 1.5
    P_hi = P_low * 20.0

    # 범위 단순 검증
    if error(P_lo) * error(P_hi) > 0:
        raise ValueError(
            f"brentq: 탐색 범위 [{P_lo/1e3:.1f}, {P_hi/1e3:.1f}] kPa 에서 "
            f"부호 변환 없음. T_turbine_outlet={T_target:.2f} K 달성 불가능.\n"
            f"  T3 at P_lo={error(P_lo)+T_target:.2f} K, "
            f"T3 at P_hi={error(P_hi)+T_target:.2f} K"
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
        pressure_ratio : float
        P_high         : float  [Pa]
        states         : list[ThermodynamicState]   State1 … State3
        results        : list[ComponentResult]
        Q_cold         : float  [W]  냉동 능력 (양수)
        W_compressor   : float  [W]  소비 동력 (양수)
        W_turbine      : float  [W]  발생 동력 (양수)
        W_net          : float  [W]  순 소비 동력 (양수)
        COP            : float
        energy_error   : float  에너지 평형 잔차 / Q_cold
        result_dir     : str
    """
    # 사이클 모듈 동적 임포트
    cycle_module = importlib.import_module(f"cycles.{config['cycle']}")

    # P_high 결정
    if config.get("pressure_ratio") is None:
        P_high = _find_P_high(cycle_module, config)
        config["pressure_ratio"] = P_high / config["P_low"]
    else:
        P_high = config["P_low"] * config["pressure_ratio"]

    # SEQUENCE 실행
    results = _run_sequence(cycle_module, config, P_high)

    # 상태점 수집: State1, State2, State2', State3
    state1  = state_from_TP(config["T_compressor_inlet"], config["P_low"],
                             fluid=config["fluid"], label="State1")
    state2  = results[0].state_out   # Compressor 출구
    state2p = results[1].state_out   # HotHX 출구
    state3  = results[2].state_out   # Turbine 출구
    states  = [state1, state2, state2p, state3]

    # 성능 지표
    Q_cold       =  results[3].Q_dot                    # ColdHX, 양수
    W_compressor =  results[0].W_dot                    # 양수
    W_turbine    = -results[2].W_dot                    # 음수→양수로 변환
    W_net        =  W_compressor - W_turbine
    COP          =  Q_cold / W_net

    # 에너지 평형 검증
    energy_residual = sum(r.W_dot + r.Q_dot for r in results)
    energy_error    = abs(energy_residual) / abs(Q_cold)

    result_dir = make_result_dir(config)

    return dict(
        pressure_ratio = config["pressure_ratio"],
        P_high         = P_high,
        states         = states,
        results        = results,
        Q_cold         = Q_cold,
        W_compressor   = W_compressor,
        W_turbine      = W_turbine,
        W_net          = W_net,
        COP            = COP,
        energy_error   = energy_error,
        result_dir     = result_dir,
    )
