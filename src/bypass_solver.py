"""
bypass_solver.py
────────────────
Bypass Topology A 역산 솔버.

  목표: Load HX 2차측 출구온도(T_sec_out) = T_sec_out_target 을 만족하는
        bypass 분율 x 를 brentq 로 역산.

  DOF 폐쇄 조건:
    - pressure_ratio 고정값 → P_high = P_low × r_p (config 필수)
    - T_sec_out_target = config["hx_load"]["T_sec_out_target"]
    - brentq: x ∈ [0, x_max] 에서 T_sec_out_cycle(x) − T_sec_out_target = 0

  x_max (최대 유효 bypass 분율):
    고 bypass 구간에서 Load HX 가 Q=0 (냉동 불가) → 외부 T1 반복 발산.
    이진 탐색으로 사이클이 수렴하는 최대 x_max 를 자동 결정.
"""

import importlib
import sys
import os

from scipy.optimize import brentq

sys.path.insert(0, os.path.dirname(__file__))


# ─────────────────────────────────────────────
# 결과 폴더명 생성
# ─────────────────────────────────────────────

def make_result_dir(config: dict, x: float) -> str:
    cycle = config["cycle"].replace("_brayton", "")
    rp    = f"rp{config['pressure_ratio']:.2f}"
    xstr  = f"x{x:.4f}"
    etac  = f"etac{config['comp']['eta_isen']}"
    etat  = f"etat{config['expander']['eta_isen']}"
    return os.path.join("results", f"{cycle}__{rp}__{xstr}__{etac}__{etat}")


# ─────────────────────────────────────────────
# 메인 솔버
# ─────────────────────────────────────────────

def solve(config: dict) -> dict:
    """
    Parameters
    ----------
    config : dict  (yaml 에서 로드한 설정)
             pressure_ratio          : float  (필수, 고정값)
             hx_load.T_sec_out_target: float  [K]  역산 목표 (반드시 < hx_load.hotside.T_inlet)

    Returns
    -------
    dict with keys:
        cycle          : str
        pressure_ratio : float
        P_high         : float  [Pa]
        x_bypass       : float  [-]  역산된 bypass 분율
        x_max          : float  [-]  사이클 수렴 최대 bypass 분율
        states         : list[ThermodynamicState]
        state_labels   : list[str]
        results        : list[ComponentResult]
        T_expander_outlet : float  [K]
        T_sec_out      : float  [K]  Load HX IM-7 출구온도
        T_sec_out_target : float  [K]
        Q_cold         : float  [W]
        W_compressor   : float  [W]
        W_expander      : float  [W]
        W_net          : float  [W]
        COP            : float
        Q_recuperator  : float  [W]
        energy_error   : float
        result_dir     : str
    """
    if config.get("pressure_ratio") is None:
        raise ValueError(
            "bypass_solver: pressure_ratio 는 고정값이어야 합니다 (null 불가). "
            "DOF 분석 참조."
        )

    T_sec_in = config["hx_load"]["hotside"]["T_inlet"]
    T_sec_target = config["hx_load"]["T_sec_out_target"]

    if T_sec_target >= T_sec_in:
        raise ValueError(
            f"bypass_solver: T_sec_out_target ({T_sec_target:.2f} K) ≥ "
            f"T_sec_in ({T_sec_in:.2f} K). IM-7 출구는 입구보다 낮아야 합니다."
        )

    P_high = config["P_low"] * config["pressure_ratio"]

    # 사이클 모듈 동적 임포트
    cycle_module = importlib.import_module(f"cycles.{config['cycle']}")

    def _T_sec_out(x: float) -> float:
        out = cycle_module.run_cycle(config, P_high, x)
        return out["T_sec_out"]

    def _safe_T_sec_out(x: float):
        """ValueError/RuntimeError 발생 시 None 반환 (발산 구간)."""
        try:
            return _T_sec_out(x)
        except (ValueError, RuntimeError):
            return None

    # ── x_max 탐색: 사이클이 수렴하는 최대 bypass 분율 이진 탐색 ──
    x_lo, x_hi = 0.0, 0.98
    if _safe_T_sec_out(x_hi) is None:
        lo_valid, hi_invalid = x_lo, x_hi
        for _ in range(20):
            mid = (lo_valid + hi_invalid) / 2.0
            if _safe_T_sec_out(mid) is None:
                hi_invalid = mid
            else:
                lo_valid = mid
            if hi_invalid - lo_valid < 1e-4:
                break
        x_hi = lo_valid

    x_max = x_hi

    # ── 탐색 범위 잔차 확인 ──
    r_lo = _T_sec_out(x_lo) - T_sec_target
    r_hi = _T_sec_out(x_hi) - T_sec_target

    if r_lo * r_hi > 0:
        raise ValueError(
            f"bypass_solver: x ∈ [0, {x_max:.4f}] 범위에서 부호 변환 없음.\n"
            f"  T_sec_out(x=0)         = {r_lo + T_sec_target:.2f} K\n"
            f"  T_sec_out(x={x_max:.4f}) = {r_hi + T_sec_target:.2f} K\n"
            f"  T_sec_out_target       = {T_sec_target:.2f} K\n"
            f"  → 목표 온도가 달성 가능 범위 밖에 있습니다.\n"
            f"  달성 가능 범위: {r_lo+T_sec_target:.2f} ~ {r_hi+T_sec_target:.2f} K"
        )

    x_sol = brentq(lambda x: _T_sec_out(x) - T_sec_target,
                   x_lo, x_hi, xtol=1e-4, rtol=1e-6)

    # 최종 사이클 계산
    cycle_out = cycle_module.run_cycle(config, P_high, x_sol)

    states            = cycle_out["states"]
    component_results = cycle_out["component_results"]
    T_expander_outlet = cycle_out["T_expander_outlet"]
    T_sec_out         = cycle_out["T_sec_out"]
    Q_cold            = cycle_out["Q_cold"]
    W_compressor      = cycle_out["W_compressor"]
    W_expander        = cycle_out["W_expander"]
    Q_recuperator     = cycle_out.get("Q_recuperator", 0.0)

    W_net = W_compressor - W_expander
    COP   = Q_cold / W_net if W_net > 0 else float("nan")

    energy_residual = sum(r.W_dot + r.Q_dot for r in component_results)
    energy_error    = abs(energy_residual) / abs(Q_cold) if Q_cold != 0.0 else float("nan")

    result_dir = make_result_dir(config, x_sol)

    return dict(
        cycle             = config["cycle"],
        pressure_ratio    = config["pressure_ratio"],
        P_high            = P_high,
        x_bypass          = x_sol,
        x_max             = x_max,
        states            = states,
        state_labels      = cycle_module.STATE_LABELS,
        results           = component_results,
        T_expander_outlet = T_expander_outlet,
        T_sec_out         = T_sec_out,
        T_sec_out_target  = T_sec_target,
        Q_cold            = Q_cold,
        W_compressor      = W_compressor,
        W_expander        = W_expander,
        W_net             = W_net,
        COP               = COP,
        Q_recuperator     = Q_recuperator,
        energy_error      = energy_error,
        result_dir        = result_dir,
    )
