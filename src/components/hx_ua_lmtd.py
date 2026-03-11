"""
components/hx_ua_lmtd.py
─────────────────────────
공용 counter-flow UA·LMTD solver.

지원 유체
  "Air", "N2", ... : CoolProp (state_from_TP / state_from_hP)
  "IM7"            : im7_properties 모듈
  "water"          : 상수 Cp = 4186 J/kg·K (비압축성 가정)

공개 API
  ua_scale(UA_rated, m_dot, m_dot_rated) -> float
  solve_counterflow(...) -> (T_hot_out, T_cold_out, Q_dot, LMTD)
"""

import sys
import os
import math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scipy.optimize import brentq
from properties import state_from_TP, state_from_hP


_CP_WATER = 4186.0   # [J/kg·K]  물 비열 (일정값 근사)
_IM7 = None          # 지연 초기화 — 필요 시 import


def _get_im7():
    global _IM7
    if _IM7 is None:
        from properties.im7_properties import IM7Properties
        _IM7 = IM7Properties()
    return _IM7


# ─────────────────────────────────────────────
# UA Scaling
# ─────────────────────────────────────────────

def ua_scale(UA_rated: float, m_dot: float, m_dot_rated: float) -> float:
    """Dittus-Boelter 지수 기반 UA 보정.

    UA = UA_rated * (m_dot / m_dot_rated)^0.8
    """
    return UA_rated * (m_dot / m_dot_rated) ** 0.8


# ─────────────────────────────────────────────
# 유체별 h(T) / T(h) 헬퍼 (내부용)
# ─────────────────────────────────────────────

def _h_from_T(T: float, fluid: str, P: float) -> float:
    if fluid == "water":
        return _CP_WATER * T        # 상대값, 차이만 사용
    if fluid == "IM7":
        return _get_im7().h(T)
    return state_from_TP(T, P, fluid).h


def _T_from_h(h: float, fluid: str, P: float,
              T_lo: float = 100.0, T_hi: float = 1000.0) -> float:
    if fluid == "water":
        return h / _CP_WATER
    if fluid == "IM7":
        im7 = _get_im7()
        return brentq(lambda T: im7.h(T) - h, T_lo, T_hi, xtol=0.001, rtol=1e-6)
    return state_from_hP(h, P, fluid).T


# ─────────────────────────────────────────────
# LMTD 계산
# ─────────────────────────────────────────────

def _lmtd(dT1: float, dT2: float) -> float:
    """Counter-flow LMTD. dT1 ≈ dT2 이면 산술평균 반환."""
    if dT1 <= 0.0 or dT2 <= 0.0:
        return 0.0
    if abs(dT1 - dT2) < 1e-6:
        return (dT1 + dT2) / 2.0
    return (dT1 - dT2) / math.log(dT1 / dT2)


# ─────────────────────────────────────────────
# Counter-flow solver
# ─────────────────────────────────────────────

def solve_counterflow(
    UA:         float,
    T_hot_in:   float, P_hot:   float, fluid_hot:   str,
    T_cold_in:  float, P_cold:  float, fluid_cold:  str,
    m_dot_hot:  float, m_dot_cold: float,
) -> tuple[float, float, float, float]:
    """Counter-flow HX 출구 온도 결정 (brentq on T_hot_out).

    Parameters
    ----------
    UA          : 유효 UA [W/K]
    T_hot_in    : 고온 유체 입구 온도 [K]
    P_hot       : 고온 유체 압력 [Pa]  (CoolProp 유체만 사용; water/IM7 무시)
    fluid_hot   : 고온 유체 종류  ("Air", "IM7", "water", ...)
    T_cold_in   : 저온 유체 입구 온도 [K]
    P_cold      : 저온 유체 압력 [Pa]
    fluid_cold  : 저온 유체 종류
    m_dot_hot   : 고온 유체 유량 [kg/s]
    m_dot_cold  : 저온 유체 유량 [kg/s]

    Returns
    -------
    (T_hot_out, T_cold_out, Q_dot, LMTD)
      Q_dot : 열전달량 [W]  (> 0 : hot → cold)
      LMTD  : 대수평균온도차 [K]
    """
    if T_hot_in <= T_cold_in:
        raise ValueError(
            f"solve_counterflow: T_hot_in ({T_hot_in:.2f} K) "
            f"<= T_cold_in ({T_cold_in:.2f} K)"
        )

    h_hot_in  = _h_from_T(T_hot_in,  fluid_hot,  P_hot)
    h_cold_in = _h_from_T(T_cold_in, fluid_cold, P_cold)

    def _residual(T_hot_out: float) -> float:
        h_hot_out = _h_from_T(T_hot_out, fluid_hot, P_hot)
        Q = m_dot_hot * (h_hot_in - h_hot_out)
        if Q <= 0.0:
            return -1e9
        h_cold_out = h_cold_in + Q / m_dot_cold
        T_cold_out = _T_from_h(h_cold_out, fluid_cold, P_cold,
                                T_lo=T_cold_in,
                                T_hi=T_hot_in + 50.0)
        dT1 = T_hot_in  - T_cold_out   # 고온 유체 입구 단
        dT2 = T_hot_out - T_cold_in    # 고온 유체 출구 단
        return Q - UA * _lmtd(dT1, dT2)

    T_lo = T_cold_in + 1e-3
    T_hi = T_hot_in  - 1e-3

    r_lo = _residual(T_lo)
    r_hi = _residual(T_hi)

    if r_lo * r_hi > 0:
        # 부호 변환 없음 → UA 과대(NTU→∞): T_hot_out ≈ T_cold_in
        T_hot_out_sol = T_lo
    else:
        T_hot_out_sol = brentq(_residual, T_lo, T_hi, xtol=0.001, rtol=1e-6)

    # 최종 결과 재계산
    h_hot_out  = _h_from_T(T_hot_out_sol, fluid_hot, P_hot)
    Q_dot      = m_dot_hot * (h_hot_in - h_hot_out)
    h_cold_out = h_cold_in + Q_dot / m_dot_cold
    T_cold_out = _T_from_h(h_cold_out, fluid_cold, P_cold,
                            T_lo=T_cold_in,
                            T_hi=T_hot_in + 50.0)
    dT1      = T_hot_in       - T_cold_out
    dT2      = T_hot_out_sol  - T_cold_in
    lmtd_val = _lmtd(dT1, dT2)

    return T_hot_out_sol, T_cold_out, Q_dot, lmtd_val
