# Air Refrigerant Reverse Brayton Cryogenic Refrigerator
## Modeling Guideline (Python / CoolProp)

---

## 1. 프로젝트 개요

### 1.1 목적

공기(Air)를 냉매로 사용하는 **역브레이튼 사이클(Reverse Brayton Cycle)**의 열역학적 모델링.
CoolProp 라이브러리를 통해 실제 유체 물성을 반영하고, 각 구성 요소의 성능 지표를 계산한다.

지원 사이클:

| 사이클 | 모듈 | 설명 |
|---|---|---|
| Simple Brayton | `cycles/simple_brayton.py` | 리큐퍼레이터 없는 기본 사이클 |
| Recuperated Brayton | `cycles/recuperated_brayton.py` | 리큐퍼레이터 포함 |

### 1.2 설계 입력 조건

| 파라미터 | YAML 키 | 기본값 | 단위 |
|---|---|---|---|
| 냉매 | `fluid` | Air | - |
| 질량 유량 | `mass_flow` | 0.5 | kg/s |
| 저압 | `P_low` | 101325 | Pa |
| 압축기 등엔트로피 효율 | `comp.eta_isen` | 0.75 | - |
| 압축기 입구 온도 | `comp.T_inlet` | 298.15 | K |
| 터빈 등엔트로피 효율 | `turbine.eta_isen` | 0.80 | - |
| 터빈 출구 목표 온도 | `turbine.T_outlet_target` | 173.15 | K |
| Aftercooler 출구 온도 | `hx_aftercooler.T_outlet` | 298.15 | K |
| Aftercooler 압손 | `hx_aftercooler.dP` | 0 | Pa |
| Load HX 압손 | `hx_load.dP` | 0 | Pa |
| Recuperator 효율 (회수 사이클) | `hx_recup.effectiveness` | 0.80 | - |
| Recuperator 고압측 압손 | `hx_recup.dP_hot` | 0 | Pa |
| Recuperator 저압측 압손 | `hx_recup.dP_cold` | 0 | Pa |

> **Note:** `turbine.T_outlet_target`(−100 °C)는 냉동 부하가 흡수되는 저온 단(cold end)의 설계 조건이다. `pressure_ratio: null` 설정 시 이 조건을 만족하는 압력비를 `brentq`로 자동 역산한다.

---

## 2. 사이클 설명 및 상태점 정의

### 2.1 Simple Brayton Cycle (4-state)

#### 사이클 구성도

```
  State 1 ──[Compressor]──► State 2 ──[Aftercooler]──► State 3
  (C-in, 저압)               (C-out, 고압)               (T-in, 고압, 냉각)
       ▲                                                        │
       │                                                  [Turbine]
       │                                                        │
  State 4 ◄──[Load HX]──────────────────────────────── State 4
  (T-out, 저압, 극저온 = −100 °C)              ← 냉동 부하 흡수 →
```

#### 상태점 정의

| 상태점 | 위치 | 설명 |
|---|---|---|
| **State 1** | 압축기 입구 | 저압, 상온 |
| **State 2** | 압축기 출구 | 고압, 고온 |
| **State 3** | Aftercooler 출구 = 터빈 입구 | 고압, 상온으로 냉각 |
| **State 4** | 터빈 출구 | 저압, 극저온 (**설계 조건: −100 °C**) |

#### 열역학적 과정

| 과정 | 구간 | 설명 |
|---|---|---|
| 1 → 2 | 압축기 | 비등엔트로피 압축 (η_c 적용) |
| 2 → 3 | Aftercooler (`hx_aftercooler`) | 등압 냉각 (고온 열 방출) |
| 3 → 4 | 터빈 | 비등엔트로피 팽창 (η_t 적용) |
| 4 → 1 | Load HX (`hx_load`) | 등압 가열 (냉동 부하 흡수) |

---

### 2.2 Recuperated Brayton Cycle (6-state)

리큐퍼레이터는 터빈 입구 스트림(고압)을 터빈 출구 스트림(저압)으로 예냉하여 압력비를 대폭 낮춘다.

#### 사이클 구성도

```
  State 1 ──[Compressor]──► State 2 ──[Aftercooler]──► State 3
  (C-in, 저압)               (C-out, 고압)               (고압, 상온)
       ▲                                                        │
       │                                            [Recuperator hot]
       │                                                        │
  State 6 ◄──[Load HX]──── State 5 ◄──[Turbine]──── State 4
  (저압, Load HX 입구)      (T-out, 극저온)            (T-in, 고압, 예냉)
       │                        │
  [Recuperator cold]         (냉동 부하 흡수: Load HX)
       │
  State 6 → State 1 (Load HX 출구 = Compressor 입구)
```

#### 상태점 정의

| 상태점 | 위치 | 설명 |
|---|---|---|
| **State 1** | 압축기 입구 | 저압, 상온 |
| **State 2** | 압축기 출구 | 고압, 고온 |
| **State 3** | Aftercooler 출구 | 고압, 상온 (= Recuperator hot 입구) |
| **State 4** | Recuperator hot 출구 = 터빈 입구 | 고압, 예냉 상태 |
| **State 5** | 터빈 출구 | 저압, 극저온 (**설계 조건: −100 °C**) |
| **State 6** | Recuperator cold 출구 = Load HX 입구 | 저압, 예열 상태 |

#### 열역학적 과정

| 과정 | 구간 | 설명 |
|---|---|---|
| 1 → 2 | 압축기 | 비등엔트로피 압축 |
| 2 → 3 | Aftercooler (`hx_aftercooler`) | 등압 냉각 (고온 열 방출) |
| 3 → 4 | Recuperator hot (`hx_recup`) | 등압 예냉 (고압 스트림) |
| 4 → 5 | 터빈 | 비등엔트로피 팽창 |
| 5 → 6 | Recuperator cold (`hx_recup`) | 등압 예열 (저압 스트림) |
| 6 → 1 | Load HX (`hx_load`) | 등압 가열 (냉동 부하 흡수) |

---

## 3. 열역학 모델링 방정식

### 3.1 CoolProp 물성 호출 규칙

```python
import CoolProp.CoolProp as CP

# 기본 호출 형식
value = CP.PropsSI(output, input1, val1, input2, val2, fluid)

# 예시: 온도·압력으로 엔탈피 계산
h = CP.PropsSI('H', 'T', T_K, 'P', P_Pa, 'Air')

# 주요 출력 키
# 'H' : 비엔탈피 [J/kg]
# 'S' : 비엔트로피 [J/kg·K]
# 'T' : 온도 [K]
# 'P' : 압력 [Pa]
```

> **단위 주의**: CoolProp은 SI 단위계 사용. 온도: K, 압력: Pa, 엔탈피: J/kg, 엔트로피: J/kg·K

### 3.2 압축기 모델 (`components/compressor.py`)

**등엔트로피 압축 (이상):**

$$h_\text{out,s} = f(s_\text{in},\ P_\text{out}) \quad \text{(등엔트로피 과정)}$$

**실제 압축기 출구 엔탈피 (효율 적용):**

$$h_\text{out} = h_\text{in} + \frac{h_\text{out,s} - h_\text{in}}{\eta_c}$$

**압축기 소비 동력:**

$$\dot{W}_c = \dot{m} \cdot (h_\text{out} - h_\text{in}) \quad [W,\ \text{양수}]$$

### 3.3 터빈 모델 (`components/turbine.py`)

**등엔트로피 팽창 (이상):**

$$h_\text{out,s} = f(s_\text{in},\ P_\text{out}) \quad \text{(등엔트로피 과정)}$$

**실제 터빈 출구 엔탈피 (효율 적용):**

$$h_\text{out} = h_\text{in} - \eta_t \cdot (h_\text{in} - h_\text{out,s})$$

**터빈 발생 동력:**

$$\dot{W}_t = \dot{m} \cdot (h_\text{out} - h_\text{in}) \quad [W,\ \text{음수}]$$

### 3.4 열교환기 모델 — 출구 온도 지정 방식 (`components/hx_*.py`)

현재 모델은 **출구 온도 T_out을 직접 지정**하는 방식이다 (prescribed outlet temperature).

$$\dot{Q} = \dot{m} \cdot (h_\text{out} - h_\text{in}) \quad [W]$$

- Aftercooler (`hx_aftercooler`): $\dot{Q} < 0$ (유체 방열)
- Load HX (`hx_load`): $\dot{Q} > 0$ (유체 흡열 = 냉동 능력)

> **향후 확장**: ε-NTU 방법 또는 UA·LMTD 방법으로 교체 예정 ([todolist.md](../todolist.md) 참조)

### 3.5 리큐퍼레이터 모델 (`components/hx_recuperator.py`)

**효율 정의 (온도 기반, balanced flow 가정):**

$$\varepsilon = \frac{T_\text{hot,in} - T_\text{hot,out}}{T_\text{hot,in} - T_\text{cold,in}}$$

$$\therefore T_\text{hot,out} = T_\text{hot,in} - \varepsilon \cdot (T_\text{hot,in} - T_\text{cold,in})$$

**에너지 수지 (실제 엔탈피 기반):**

$$\dot{Q} = \dot{m} \cdot (h_\text{hot,in} - h_\text{hot,out})$$

$$h_\text{cold,out} = h_\text{cold,in} + \dot{Q} / \dot{m}$$

### 3.6 성능 지표

**성적 계수 (COP):**

$$\text{COP} = \frac{\dot{Q}_{cold}}{\dot{W}_{net}} = \frac{\dot{Q}_{cold}}{\dot{W}_c - \dot{W}_t}$$

**에너지 평형 검증:**

$$\sum \dot{W} + \sum \dot{Q} = \sum \dot{m}(h_\text{out} - h_\text{in}) = 0 \quad \text{(폐루프)}$$

---

## 4. 압력비 결정 전략

### 4.1 기본 전략

`pressure_ratio: null` 설정 시 scipy `brentq`로 역산.
**목적**: 터빈 출구 온도 = `turbine.T_outlet_target` (기본: 173.15 K = −100 °C)

### 4.2 Simple Brayton 역산

단일 brentq 루프:

```python
error(P_high) = T4_calc(P_high) - T_turbine_outlet
P_high_sol = brentq(error, P_low * 1.5, P_low * 20)
```

결과: r_p ≈ **12.9** (η_c=0.75, η_t=0.80, T3=25°C 조건)

### 4.3 Recuperated Brayton 역산

이중 중첩 brentq:

- **외부 brentq**: `T5(P_high) = T_turbine_outlet`
- **내부 brentq**: `T4 = T3 - ε·(T3 - T5(T4))` (순환 의존성 해소)

```python
# 내부: T4 수렴
residual(T4) = T4 - (T3 - ε*(T3 - turbine_outlet_T(T4)))

# 외부: P_high 수렴
error(P_high) = T5(P_high) - T_turbine_outlet
```

결과: r_p ≈ **1.8** (ε=0.80 조건) — Simple 대비 압력비 대폭 감소.

> **주의**: Air의 cricondentherm ≈ 132.5 K. T4 탐색 하한을 140 K으로 설정하여 두 상 영역 진입 방지.

---

## 5. 프로젝트 구조

### 5.1 소스 코드 구조

```
airHP/
│
├─ configs/
│   ├─ simple_baseline.yaml          ← Simple Brayton 기본 설정
│   └─ recuperated_baseline.yaml     ← Recuperated Brayton 기본 설정
│
├─ docs/
│   ├─ modeling_guide.md             ← 본 문서
│   └─ todolist.md                   ← 개발 예정 항목
│
├─ src/
│   ├─ components/
│   │   ├─ compressor.py             ← 비등엔트로피 압축기
│   │   ├─ turbine.py                ← 비등엔트로피 터빈
│   │   ├─ hx_base.py                ← 등압 열교환 공통 로직
│   │   ├─ hx_heat_rejection.py      ← Hot HX (고압측 방열)
│   │   ├─ hx_heat_absorption.py     ← Cold HX (냉동 부하)
│   │   └─ hx_recuperator.py         ← 리큐퍼레이터 (ε 기반)
│   │
│   ├─ cycles/
│   │   ├─ simple_brayton.py         ← SEQUENCE 방식 (4 states)
│   │   └─ recuperated_brayton.py    ← run_cycle 방식 (6 states)
│   │
│   ├─ properties.py                 ← CoolProp 래퍼, 데이터클래스
│   └─ cycle_solver.py               ← 범용 솔버
│
├─ main.py                           ← CLI / 대화형 사이클 선택
├─ visualize.py                      ← T-s, P-h 선도 + r_p 스윕
│
└─ results/
    └─ {cycle}__{rp}__{Tt}__{etac}__{etat}/
        ├─ state_points.csv
        ├─ performance.csv
        ├─ cycle_Ts.png
        ├─ cycle_Ph.png
        ├─ cop_vs_rp.png
        └─ cop_vs_rp.csv
```

### 5.2 각 모듈 역할 요약

| 모듈 | 역할 |
|---|---|
| `properties.py` | CoolProp 래퍼, `ThermodynamicState` / `ComponentResult` 정의 |
| `components/compressor.py` | 압축기: in → out_s (이상) → out (실제) |
| `components/turbine.py` | 터빈: in → out_s (이상) → out (실제) |
| `components/hx_base.py` | 등압 HX 공통 로직 |
| `components/hx_heat_rejection.py` | Aftercooler (`hx_aftercooler`) — 고압측 방열 |
| `components/hx_heat_absorption.py` | Load HX (`hx_load`) — 냉동 부하 흡수 |
| `components/hx_recuperator.py` | 리큐퍼레이터: ε 기반, 양방향 출력 |
| `cycles/simple_brayton.py` | SEQUENCE 정의 + `STATE_LABELS` |
| `cycles/recuperated_brayton.py` | `run_cycle()` + `STATE_LABELS` |
| `cycle_solver.py` | SEQUENCE / run_cycle 자동 분기, brentq 역산 |
| `main.py` | 대화형 사이클 선택 → solver → CSV 저장 |
| `visualize.py` | T-s / P-h 선도, r_p 파라미터 스윕 |

### 5.3 사이클 모듈 확장 방식

| 방식 | 적용 대상 | 필수 요소 |
|---|---|---|
| `SEQUENCE` | 순환 의존성 없는 사이클 | `SEQUENCE`, `STATE_LABELS` |
| `run_cycle()` | 순환 의존성 있는 사이클 (recuperator 등) | `run_cycle()`, `STATE_LABELS` |

`cycle_solver.py`는 `hasattr(cycle_module, 'run_cycle')`로 자동 분기하므로, 새 사이클 추가 시 기존 코드 수정 불필요.

---

## 6. 컴포넌트 I/O 인터페이스

### 6.1 공용 데이터 타입 (`properties.py`)

```python
@dataclass
class ThermodynamicState:
    fluid: str     # "Air"
    T:     float   # [K]
    P:     float   # [Pa]
    h:     float   # [J/kg]
    s:     float   # [J/kg·K]
    label: str = ""

@dataclass
class ComponentResult:
    state_out: ThermodynamicState
    W_dot:     float = 0.0   # [W]
    Q_dot:     float = 0.0   # [W]
    label:     str   = ""
```

**부호 규칙 (표준 열역학 제1법칙):**

| 부호 | 의미 |
|---|---|
| `W_dot > 0` | 유체가 외부로부터 일을 받음 → 압축기 |
| `W_dot < 0` | 유체가 외부로 일을 함 → 터빈 |
| `Q_dot < 0` | 유체가 외부로 열을 방출 → Aftercooler |
| `Q_dot > 0` | 유체가 외부로부터 열을 받음 → Load HX (냉동 능력) |

이 규칙 하에서: `ΣW_dot + ΣQ_dot = 0` (사이클 폐루프)

### 6.2 컴포넌트별 I/O

| 컴포넌트 | 함수 시그니처 | 반환 |
|---|---|---|
| 압축기 | `run(state_in, P_out, eta_c, m_dot)` | `ComponentResult` |
| 터빈 | `run(state_in, P_out, eta_t, m_dot)` | `ComponentResult` |
| Aftercooler / Load HX | `run(state_in, T_out, m_dot)` | `ComponentResult` |
| Recuperator (`hx_recup`) | `run(state_hot_in, state_cold_in, effectiveness, m_dot)` | `tuple[ComponentResult, ComponentResult]` |

### 6.3 `properties.py` 래퍼

CoolProp 직접 호출은 `properties.py`에서만 허용.

```python
state_from_TP(T_K, P_Pa, fluid, label="") -> ThermodynamicState
state_from_sP(s, P_Pa, fluid, label="")   -> ThermodynamicState  # 등엔트로피 과정
state_from_hP(h, P_Pa, fluid, label="")   -> ThermodynamicState
```

---

## 7. 수치 해석 고려사항

### 7.1 Air 두 상 영역 제한

- Air cricondentherm ≈ 132.5 K → T > 132.5 K 에서는 어떤 압력에서도 기상 보장
- 리큐퍼레이터 내부 brentq T4 탐색 하한: **140 K**
- 외부 brentq에서 CoolProp ValueError 발생 시 `T_target - 400` 반환으로 soft 처리

### 7.2 수렴 허용 기준

| 항목 | 허용값 |
|---|---|
| 에너지 평형 오차 | `|ΣW+ΣQ| / Q_cold < 1e-5` |
| brentq P_high 허용 오차 | `xtol=1.0 Pa` |
| 내부 T4 brentq 허용 오차 | `xtol=0.01 K` |

---

## 8. 출력 결과 형식

### 8.1 콘솔 출력 예시 (Recuperated)

```
================================================================
  Reverse Brayton Cryogenic Refrigerator Results
================================================================
  Cycle           : recuperated_brayton
  Fluid           : Air
  Mass Flow Rate  : 0.500 kg/s
  Pressure Ratio  : 1.8134
  P_low / P_high  : 101.33 kPa / 183.74 kPa

  State Points:
  ----------------------------------------------------------
  State        T [°C]    P [kPa]   h [kJ/kg]  s [kJ/kgK]
  ----------------------------------------------------------
  1 (C-in)     25.0      101.33    424.436    3.8805
  2 (C-out)    98.5      183.74    498.461    3.9315
  3 (HX-out)   25.0      183.74    424.247    3.7091
  4 (T-in)    -75.0      183.74    323.437    3.2972
  5 (T-out)  -100.0      101.33    298.653    3.3336
  6 (rec-out)   0.2      101.33    399.463    3.7930
  ----------------------------------------------------------

  Performance:
    Q_cold  (Refrigeration) :   12.486 kW
    W_compressor            :   37.013 kW
    W_turbine               :   12.392 kW
    W_net                   :   24.621 kW
    Q_recuperator           :   50.405 kW
    COP                     :   0.5071
    Energy balance error    : 4.43e-07
================================================================
```

### 8.2 결과 파일

| 파일 | 내용 |
|---|---|
| `state_points.csv` | 전 상태점 T, P, h, s |
| `performance.csv` | COP, 동력, 냉동 능력, 에너지 오차 |
| `cycle_Ts.png` | T-s 선도 |
| `cycle_Ph.png` | P-h 선도 |
| `cop_vs_rp.png` | 압력비 파라미터 스윕 |
| `cop_vs_rp.csv` | 스윕 데이터 |

---

## 9. 성능 비교 (기준 조건)

| 항목 | Simple | Recuperated (ε=0.80) |
|---|---|---|
| 압력비 r_p | 12.9 | **1.8** |
| Q_cold | 62.9 kW | 12.5 kW |
| W_net | 153.1 kW | 24.6 kW |
| COP | 0.411 | **0.507** |
| Q_recuperator | - | 50.4 kW |

조건: Air, ṁ=0.5 kg/s, T_out=−100°C, η_c=0.75, η_t=0.80

---

## 10. 의존성

```
Python >= 3.9
CoolProp >= 6.4
scipy >= 1.9
numpy >= 1.23
matplotlib >= 3.6
pyyaml
```

```bash
pip install CoolProp scipy numpy matplotlib pyyaml
```

---

*Last updated: 2026-03-11 — YAML 계층 구조 리팩토링 반영 (comp/turbine/hx_aftercooler/hx_load/hx_recup), 컴포넌트 명칭 Aftercooler/Load HX 로 통일*
