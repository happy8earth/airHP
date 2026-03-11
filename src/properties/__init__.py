"""
properties/
───────────
CoolProp 래퍼 및 공용 데이터 타입 정의.

규칙:
  - CoolProp 직접 호출은 이 패키지에서만 허용.
  - 온도는 항상 K, 압력은 항상 Pa, 엔탈피/엔트로피는 J/kg, J/kg·K.
  - 신규 유체 추가 시: src/properties/<fluid>_properties.py 작성 후
    state_from_TP 분기에 등록.
"""

from dataclasses import dataclass
import CoolProp.CoolProp as CP


# ─────────────────────────────────────────────
# 공용 데이터 타입
# ─────────────────────────────────────────────

@dataclass
class ThermodynamicState:
    """모든 상태점의 표준 표현."""
    fluid: str          # 예: "Air", "IM7"
    T:     float        # [K]
    P:     float        # [Pa]
    h:     float        # [J/kg]
    s:     float        # [J/kg·K]
    label: str = ""     # 디버깅용 식별자

    def T_celsius(self) -> float:
        return self.T - 273.15

    def P_kPa(self) -> float:
        return self.P / 1e3

    def h_kJ(self) -> float:
        return self.h / 1e3

    def s_kJ(self) -> float:
        return self.s / 1e3


@dataclass
class ComponentResult:
    """컴포넌트 출력의 표준 반환 타입.

    부호 규칙 (열역학 제1법칙 기준):
      W_dot > 0 : 시스템이 외부로부터 일을 받음  → 압축기
      W_dot < 0 : 시스템이 외부로 일을 함        → 팽창기
      Q_dot < 0 : 시스템이 외부로 열을 방출       → Aftercooler
      Q_dot > 0 : 시스템이 외부로부터 열을 받음   → Load HX

    에너지 평형: ΣW_dot + ΣQ_dot ≈ 0
    """
    state_out: ThermodynamicState
    W_dot:     float = 0.0   # [W]
    Q_dot:     float = 0.0   # [W]
    label:     str   = ""


# ─────────────────────────────────────────────
# CoolProp 래퍼 (Air, N2, He 등)
# ─────────────────────────────────────────────

_COOLPROP_FLUIDS = {"Air", "N2", "He", "Ar", "CO2"}   # 필요 시 추가


def _get_h_s(fluid: str, input1: str, val1: float,
             input2: str, val2: float) -> tuple[float, float]:
    """내부 헬퍼: h, s 동시 계산."""
    h = CP.PropsSI("H", input1, val1, input2, val2, fluid)
    s = CP.PropsSI("S", input1, val1, input2, val2, fluid)
    return h, s


def state_from_TP(T_K: float, P_Pa: float,
                  fluid: str = "Air", label: str = "") -> ThermodynamicState:
    """온도·압력으로 상태점 계산.

    CoolProp 유체(Air 등)와 테이블 기반 유체(IM7 등) 모두 지원.
    """
    if fluid == "IM7":
        from properties.im7_properties import state_from_TP as _im7_state
        return _im7_state(T_K, P_Pa, label=label)
    h, s = _get_h_s(fluid, "T", T_K, "P", P_Pa)
    return ThermodynamicState(fluid=fluid, T=T_K, P=P_Pa, h=h, s=s, label=label)


def state_from_sP(s: float, P_Pa: float,
                  fluid: str = "Air", label: str = "") -> ThermodynamicState:
    """엔트로피·압력으로 상태점 계산 (등엔트로피 과정용)."""
    T = CP.PropsSI("T", "S", s, "P", P_Pa, fluid)
    h = CP.PropsSI("H", "S", s, "P", P_Pa, fluid)
    return ThermodynamicState(fluid=fluid, T=T, P=P_Pa, h=h, s=s, label=label)


def state_from_hP(h: float, P_Pa: float,
                  fluid: str = "Air", label: str = "") -> ThermodynamicState:
    """엔탈피·압력으로 상태점 계산 (실제 과정 출구용)."""
    T = CP.PropsSI("T", "H", h, "P", P_Pa, fluid)
    s = CP.PropsSI("S", "H", h, "P", P_Pa, fluid)
    return ThermodynamicState(fluid=fluid, T=T, P=P_Pa, h=h, s=s, label=label)
