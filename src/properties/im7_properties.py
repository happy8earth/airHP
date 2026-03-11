"""
properties/im7_properties.py
────────────────────────────
IM-7 냉각유체 물성 모듈 (테이블 기반).

데이터 소스: im7_liquid_properties.csv
유효 범위  : −70 ∼ 70°C (Cp, rho, mu, k). 범위 밖은 선형 외삽.
비압축성 가정: P는 인자로 받되 h/s 계산에 미사용.

기준 상태 (h=0, s=0): T_ref = 273.15 K (0°C)
"""

import os
import math
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from properties import ThermodynamicState


# ─────────────────────────────────────────────
# 내부 헬퍼: 선형 외삽 포함 interp1d 래퍼
# ─────────────────────────────────────────────

def _make_interp(x: np.ndarray, y: np.ndarray):
    """유효 데이터만으로 interp1d 생성 + 범위 밖 선형 외삽."""
    # 내부 구간은 scipy 선형 보간
    f_inner = interp1d(x, y, kind="linear", bounds_error=False, fill_value=np.nan)

    def interp(t):
        val = float(f_inner(t))
        if not math.isnan(val):
            return val
        # 하단 외삽
        if t < x[0]:
            slope = (y[1] - y[0]) / (x[1] - x[0])
            return float(y[0] + slope * (t - x[0]))
        # 상단 외삽
        slope = (y[-1] - y[-2]) / (x[-1] - x[-2])
        return float(y[-1] + slope * (t - x[-1]))

    return interp


# ─────────────────────────────────────────────
# IM7Properties 클래스
# ─────────────────────────────────────────────

class IM7Properties:
    """IM-7 액체 냉각유체 물성.

    인스턴스 생성 시 CSV를 한 번만 읽고 보간 함수/다항식을 구축.
    이후 h(), s(), rho(), Cp(), mu(), k_th() 는 단순 계산만 수행.
    """

    T_REF = 273.15   # [K]  기준 온도 (h=0, s=0)

    def __init__(self):
        csv_path = os.path.join(os.path.dirname(__file__), "im7_liquid_properties.csv")
        df = pd.read_csv(csv_path)

        T_K_all = df["T_K"].to_numpy(dtype=float)

        # ── rho, mu, Cp, k: 유효(NaN 제외) 행만 사용 ──────────────────
        col_map = {
            "rho": "rho_liq_kg_m3",
            "mu":  "mu_liq_mPa_s",
            "Cp":  "Cp_liq_J_kgK",
            "k":   "k_liq_mW_mK",
        }

        interps = {}
        valid_rows = {}
        for key, col in col_map.items():
            mask = df[col].notna()
            T_valid = T_K_all[mask.to_numpy()]
            y_valid = df.loc[mask, col].to_numpy(dtype=float)
            # 단위 변환 (로드 시 1회)
            if key == "mu":
                y_valid = y_valid / 1000.0        # mPa·s → Pa·s
            if key == "k":
                y_valid = y_valid / 1000.0        # mW/(m·K) → W/(m·K)
            interps[key] = _make_interp(T_valid, y_valid)
            valid_rows[key] = (T_valid, y_valid)

        self._rho_interp = interps["rho"]
        self._mu_interp  = interps["mu"]
        self._k_interp   = interps["k"]

        # ── Cp 다항식 피팅 (deg=2, T in K) ────────────────────────────
        T_cp, y_cp = valid_rows["Cp"]
        self._cp_coef = np.polyfit(T_cp, y_cp, deg=2)   # [a2, a1, a0]

        # 다항식 계수: Cp = a0 + a1*T + a2*T^2
        a2, a1, a0 = self._cp_coef
        self._a0 = a0
        self._a1 = a1
        self._a2 = a2
        self._T_ref = self.T_REF

    # ── 물성 메서드 ──────────────────────────────────────────────────

    def Cp(self, T_K: float) -> float:
        """비열 [J/kg·K]. Cp = a0 + a1*T + a2*T²"""
        T = float(T_K)
        return self._a0 + self._a1 * T + self._a2 * T * T

    def h(self, T_K: float) -> float:
        """비엔탈피 [J/kg]. 기준: T_ref=273.15K, h=0.
        h(T) = a0*(T-Tr) + a1/2*(T²-Tr²) + a2/3*(T³-Tr³)
        """
        T = float(T_K)
        Tr = self._T_ref
        a0, a1, a2 = self._a0, self._a1, self._a2
        return (  a0 * (T - Tr)
                + a1 / 2.0 * (T**2 - Tr**2)
                + a2 / 3.0 * (T**3 - Tr**3))

    def s(self, T_K: float) -> float:
        """비엔트로피 [J/kg·K]. 기준: T_ref=273.15K, s=0.
        s(T) = a0*ln(T/Tr) + a1*(T-Tr) + a2/2*(T²-Tr²)
        """
        T = float(T_K)
        Tr = self._T_ref
        a0, a1, a2 = self._a0, self._a1, self._a2
        return (  a0 * math.log(T / Tr)
                + a1 * (T - Tr)
                + a2 / 2.0 * (T**2 - Tr**2))

    def rho(self, T_K: float) -> float:
        """밀도 [kg/m³]."""
        return self._rho_interp(float(T_K))

    def mu(self, T_K: float) -> float:
        """동적 점도 [Pa·s]."""
        return self._mu_interp(float(T_K))

    def k_th(self, T_K: float) -> float:
        """열전도율 [W/m·K]. (k 는 Python 예약어 회피)"""
        return self._k_interp(float(T_K))


# ─────────────────────────────────────────────
# 모듈 수준 싱글톤 (CSV 는 import 시 1회만 로드)
# ─────────────────────────────────────────────

_IM7 = IM7Properties()


# ─────────────────────────────────────────────
# 공개 인터페이스
# ─────────────────────────────────────────────

def state_from_TP(T_K: float, P_Pa: float, label: str = "") -> ThermodynamicState:
    """온도·압력으로 IM-7 상태점 반환.

    비압축성 가정: P_Pa 는 ThermodynamicState 에 저장되나
    h, s 계산에는 사용되지 않음.
    """
    return ThermodynamicState(
        fluid="IM7",
        T=float(T_K),
        P=float(P_Pa),
        h=_IM7.h(T_K),
        s=_IM7.s(T_K),
        label=label,
    )
