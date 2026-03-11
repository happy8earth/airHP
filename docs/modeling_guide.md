# Air Refrigerant Simple Reverse Brayton Cryogenic Refrigerator
## Modeling Guideline (Python / CoolProp)

---

## 1. 프로젝트 개요

### 1.1 목적

공기(Air)를 냉매로 사용하는 **리큐퍼레이터 없는 단순 역브레이튼 사이클(Simple Reverse Brayton Cycle)**의 열역학적 모델링.  
CoolProp 라이브러리를 통해 실제 유체 물성을 반영하고, 각 구성 요소의 성능 지표를 계산한다.

### 1.2 설계 입력 조건

| 파라미터 | 값 | 단위 |
|---|---|---|
| 냉매 | Air (CoolProp) | - |
| 질량 유량 | 0.5 | kg/s |
| 터빈 출구 온도 | −100 | °C |
| 압축기 등엔트로피 효율 | 0.75 | - |
| 터빈 등엔트로피 효율 | 0.80 | - |
| 사이클 유형 | Simple Reverse Brayton | - |

> **Note:** 터빈 출구 온도(−100 °C)는 냉동 부하가 흡수되는 저온 단(cold end)의 조건이다.

---

## 2. 사이클 설명 및 상태점 정의

### 2.1 사이클 구성도

```
        ┌──────────────────────────────────────────┐
        │           고온 열교환기 (Hot HX)           │
        │       (대기 또는 냉각수에 열 방출)           │
        └───────────┬──────────────────┬───────────┘
                    │                  │
               State 2               State 1
           (압축기 출구)           (압축기 입구)
                    │                  │
               ┌────┴────┐        ┌────┴────┐
               │ 압축기   │        │  터빈   │
               │ (η_c)   │        │ (η_t)   │
               └────┬────┘        └────┬────┘
                    │                  │
               State 1               State 3 ← 냉동 부하 흡수
           (사이클 입구)           (터빈 출구 = −100 °C)
                    │                  │
                    └──────────────────┘
                      저온 열교환기 (Cold HX / Refrigeration Load)
```

### 2.2 상태점 정의

| 상태점 | 위치 | 설명 |
|---|---|---|
| **State 1** | 압축기 입구 | 저압, 저온 (Cold HX 출구) |
| **State 2** | 압축기 출구 | 고압, 고온 |
| **State 3** | 터빈 출구 | 저압, 극저온 (**설계 조건: −100 °C**) |
| **State 2'** | 터빈 입구 (= Hot HX 출구) | 고압, 냉각 후 |

> **State 1 = State 3의 압력**: 저압단은 동일 압력으로 연결됨.  
> **State 2 = State 2'의 압력**: 고압단은 동일 압력으로 연결됨.

### 2.3 열역학적 과정

| 과정 | 구간 | 설명 |
|---|---|---|
| 1 → 2 | 압축기 | 비등엔트로피 압축 (η_c 적용) |
| 2 → 2' | Hot HX | 등압 냉각 (고온 열 방출) |
| 2' → 3 | 터빈 | 비등엔트로피 팽창 (η_t 적용) |
| 3 → 1 | Cold HX | 등압 가열 (냉동 부하 흡수) |

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
# 'D' : 밀도 [kg/m³]
```

> **단위 주의**: CoolProp은 SI 단위계 사용.  
> 온도: K, 압력: Pa, 엔탈피: J/kg, 엔트로피: J/kg·K

### 3.2 압축기 모델 (`compressor.py`)

**등엔트로피 압축 (이상):**

$$h_{2s} = f(s_1, P_2) \quad \text{(등엔트로피 과정)}$$

**실제 압축기 출구 엔탈피 (효율 적용):**

$$h_2 = h_1 + \frac{h_{2s} - h_1}{\eta_c}$$

**압축기 소비 동력:**

$$\dot{W}_c = \dot{m} \cdot (h_2 - h_1)$$

### 3.3 터빈 모델 (`turbine.py`)

**등엔트로피 팽창 (이상):**

$$h_{3s} = f(s_{2'}, P_3) \quad \text{(등엔트로피 과정)}$$

**실제 터빈 출구 엔탈피 (효율 적용):**

$$h_3 = h_{2'} - \eta_t \cdot (h_{2'} - h_{3s})$$

**터빈 발생 동력:**

$$\dot{W}_t = \dot{m} \cdot (h_{2'} - h_3)$$

### 3.4 열교환기 모델 (등압 가정)

**Hot HX (고온 열 방출):**

$$\dot{Q}_{hot} = \dot{m} \cdot (h_2 - h_{2'})$$

**Cold HX (냉동 부하):**

$$\dot{Q}_{cold} = \dot{m} \cdot (h_1 - h_3)$$

### 3.5 성능 지표

**성적 계수 (COP):**

$$\text{COP} = \frac{\dot{Q}_{cold}}{\dot{W}_{net}} = \frac{\dot{Q}_{cold}}{\dot{W}_c - \dot{W}_t}$$

**냉동 능력 (Refrigeration Capacity):**

$$\dot{Q}_{cold} = \dot{m} \cdot (h_1 - h_3) \quad [\text{W}]$$

---

## 4. 압력비 결정 전략

단순 역브레이튼 사이클에서 **압력비(r_p = P_high / P_low)**는 외부에서 지정하는 설계 변수이다.

### 4.1 기본 전략

- 터빈 출구 조건(T_3 = −100 °C)과 터빈 입구 조건(T_2', P_high)이 주어지면, 터빈 방정식으로부터 역산하여 요구 압력비를 구한다.
- 또는 압력비를 파라미터 스윕하여 COP 최적화를 수행할 수 있다.

### 4.2 역산 절차 (터빈 출구 온도 고정 시)

1. T_3 = −100 °C, P_low 가정 (예: 101325 Pa = 1 atm)
2. h_3, s_3 계산
3. 터빈 효율 역적용: h_{2'} = h_3 / η_t + h_{3s} 관계로부터 P_high 탐색
4. scipy.optimize 활용하여 수치적으로 P_high 결정

---

## 5. 프로젝트 구조 및 파일명 체계화

사이클 구성(configuration)이 다양해질 것을 고려하여, 소스 코드 / 설정 파일 / 결과 파일의 세 레이어로 나누어 체계화한다.

### 5.1 소스 코드 구조 (`src/`)

컴포넌트 모듈은 재사용 가능한 단위로 분리하고, **사이클 위상(topology)만 교체**할 수 있도록 `cycles/` 폴더를 별도로 둔다. `cycle_solver.py`는 위상에 무관한 범용 솔버로 유지한다.

```
air_brayton_cryocooler_project/
│
├─ configs/                            ← 설정 파일 (YAML)
│   ├─ simple_baseline.yaml
│   ├─ recuperated_baseline.yaml
│   └─ parametric_sweep.yaml
│
├─ docs/
│   └─ modeling_guide.md              ← 본 문서
│
├─ src/
│   ├─ components/                    ← 재사용 가능한 컴포넌트 단위 모듈
│   │   ├─ compressor.py
│   │   ├─ turbine.py
│   │   ├─ hx_base.py                 ← 등압 열교환 공통 로직 (내부용)
│   │   ├─ hx_heat_rejection.py       ← Hot HX: 고압측 열 방출 (현재 미사용)
│   │   ├─ hx_heat_absorption.py      ← Cold HX: 냉동 부하 흡수 (현재 미사용)
│   │   └─ hx_recuperator.py          ← 내부 열교환, 2-stream (현재 미사용)
│   │
│   ├─ cycles/                        ← 사이클 위상 정의 (컴포넌트 연결 순서)
│   │   ├─ simple_brayton.py          ← 현재 구현 대상
│   │   ├─ recuperated_brayton.py     ← 향후 확장
│   │   └─ two_stage_brayton.py       ← 향후 확장
│   │
│   ├─ properties.py                  ← CoolProp 래퍼, ThermodynamicState 정의
│   └─ cycle_solver.py                ← 범용 솔버 (위상 정의를 받아 실행)
│
├─ main.py                            ← python main.py --config configs/simple_baseline.yaml
│
└─ results/                           ← 설정별 자동 폴더 생성
    └─ {cycle}__{params}/
```

> **설계 원칙**: 새로운 사이클 추가 시 기존 코드를 수정하지 않고 `cycles/`에 파일을 추가하는 것만으로 확장 가능하도록 한다.

### 5.2 설정 파일 체계 (`configs/`)

하드코딩을 피하고 YAML로 설정을 외부화한다. `main.py`는 YAML만 읽어서 실행하므로, 설정 변경 시 코드를 건드리지 않는다.

**`configs/simple_baseline.yaml` 예시:**

```yaml
cycle: simple_brayton        # cycles/ 폴더의 모듈명과 일치
fluid: Air
mass_flow: 0.5               # [kg/s]
T_turbine_outlet: 173.15     # [K] − 항상 K 단위로 저장
eta_compressor: 0.75
eta_turbine: 0.80
P_low: 101325                # [Pa]
pressure_ratio: 5.0          # 고정값 또는 null (역산 시)
```

> **단위 규칙**: 설정 파일 내 온도는 항상 **K**, 압력은 항상 **Pa**로 저장한다.  
> 사용자 입력(°C, kPa 등)의 변환은 `main.py` 진입부에서만 수행한다.

### 5.3 결과 파일 체계 (`results/`)

결과 폴더명에 설정 정보를 인코딩하여 실험 결과를 추적 가능하게 한다.

**폴더명 규칙:** `{cycle_type}__{key}val__{key}val__...`

- 그룹 구분: 더블 언더스코어 (`__`)
- key-value 연결: 단일 문자 (예: `rp` = pressure ratio, `Tt` = turbine outlet temp)

```
results/
├─ simple__rp5.0__Tt173K__etac0.75__etat0.80/
│   ├─ state_points.csv
│   ├─ performance.csv
│   ├─ cycle_Ts.png
│   └─ cycle_Ph.png
│
├─ recuperated__rp5.0__effr0.85__Tt173K__etac0.75__etat0.80/
│   └─ ...
│
└─ simple__rp_sweep__Tt173K/          ← 파라미터 스윕 결과
    ├─ cop_vs_rp.csv
    └─ cop_vs_rp.png
```

**폴더명 자동 생성 규칙 (`cycle_solver.py` 내):**

```python
def make_result_dir(config: dict) -> str:
    cycle  = config["cycle"].replace("_brayton", "")   # "simple"
    rp     = f"rp{config['pressure_ratio']}"
    Tt     = f"Tt{int(config['T_turbine_outlet'])}K"
    etac   = f"etac{config['eta_compressor']}"
    etat   = f"etat{config['eta_turbine']}"
    return f"results/{cycle}__{rp}__{Tt}__{etac}__{etat}"
```

### 5.4 각 모듈 역할 요약

| 모듈 | 역할 |
|---|---|
| `properties.py` | CoolProp 래퍼, `ThermodynamicState` / `ComponentResult` 데이터클래스 정의 |
| `components/compressor.py` | 압축기 열역학 모델 (입력 → 출구 상태 + 동력) |
| `components/turbine.py` | 터빈 열역학 모델 (입력 → 출구 상태 + 동력) |
| `components/hx_base.py` | 등압 열교환 공통 로직 (hx_* 파일들의 베이스) |
| `components/hx_heat_rejection.py` | Hot HX: 고압측 열 방출 모델 |
| `components/hx_heat_absorption.py` | Cold HX: 냉동 부하 흡수 모델 |
| `components/hx_recuperator.py` | 리큐퍼레이터: 2-stream 내부 열교환 모델 |
| `cycles/simple_brayton.py` | 상태점 연결 순서 정의 (1→2→2'→3→1) |
| `cycle_solver.py` | 위상 정의를 받아 순차 실행, 에너지 평형 검증, 성능 계산 |
| `main.py` | YAML 로드 → solver 호출 → 콘솔 출력 및 결과 저장 |

---

## 6. 컴포넌트 I/O 인터페이스 설계

컴포넌트 간 데이터 전달 방식을 통일하지 않으면, 사이클 위상이 바뀔 때 연결부에서 버그가 발생하기 쉽다. 모든 컴포넌트가 **동일한 타입을 입력받고 동일한 타입을 반환**하도록 강제한다.

### 6.1 공용 데이터 타입 (`properties.py`에 정의)

**`ThermodynamicState`** — 모든 상태점의 표준 표현:

```python
from dataclasses import dataclass

@dataclass
class ThermodynamicState:
    fluid: str        # "Air"
    T:     float      # [K]      ← 항상 K, °C 혼용 금지
    P:     float      # [Pa]     ← 항상 Pa
    h:     float      # [J/kg]
    s:     float      # [J/kg·K]
    label: str = ""   # 디버깅용 식별자 ("State1", "Compressor_out" 등)
```

**`ComponentResult`** — 컴포넌트 출력의 표준 반환 타입:

```python
@dataclass
class ComponentResult:
    state_out: ThermodynamicState
    W_dot:     float = 0.0   # [W]  일: 소비(+), 발생(−)
    Q_dot:     float = 0.0   # [W]  열: 흡수(+), 방출(−)
    label:     str   = ""
```

> **부호 규칙 (표준 열역학 제1법칙 기준)**
> `W_dot > 0` : 유체가 외부로부터 일을 받음 → 압축기
> `W_dot < 0` : 유체가 외부로 일을 함 → 터빈
> `Q_dot < 0` : 유체가 외부로 열을 방출 → Hot HX
> `Q_dot > 0` : 유체가 외부로부터 열을 받음 → Cold HX (**냉동 능력**)
>
> 이 부호 규칙을 따르면 에너지 평형 검증식이 성립한다:
> `ΣW_dot + ΣQ_dot = Σ m_dot*(h_out - h_in) = 0` (사이클 폐루프)
>
> > **Note:** 냉동 능력은 `Q_cold = ComponentResult.Q_dot` (양수),
> > COP = `Q_cold / W_net` where `W_net = W_comp + W_turb` (W_turb < 0이므로 자동 차감)

### 6.2 컴포넌트별 I/O 명세

모든 컴포넌트는 `ThermodynamicState`를 입력으로 받아 `ComponentResult`를 반환하는 **동일한 시그니처 패턴**을 따른다.

| 컴포넌트 | 함수 시그니처 | `W_dot` | `Q_dot` |
|---|---|---|---|
| 압축기 | `run(state_in, P_out, eta_c, m_dot)` | `> 0` (소비) | `0` |
| 터빈 | `run(state_in, P_out, eta_t, m_dot)` | `< 0` (발생) | `0` |
| Hot/Cold HX | `run(state_in, T_out, m_dot)` | `0` | `±` |
| 리큐퍼레이터 | `run(state_hot_in, state_cold_in, eff, m_dot)` | `0` | 내부 교환 |

> **리큐퍼레이터**는 입출력이 2쌍이므로 반환 타입이 `tuple[ComponentResult, ComponentResult]`으로 달라진다.  
> 이 점이 `cycle_solver.py`에서 리큐퍼레이터 처리 로직을 별도로 분기해야 하는 이유이다.

#### 압축기 (`components/compressor.py`)

```python
# 입력
state_in : ThermodynamicState   # 압축기 입구 상태 (State 1)
P_out    : float                # 출구 압력 [Pa]
eta_c    : float                # 등엔트로피 효율 [-]
m_dot    : float                # 질량 유량 [kg/s]

# 출력
result   : ComponentResult
  └─ state_out : ThermodynamicState   # 압축기 출구 상태 (State 2)
  └─ W_dot     : float                # 소비 동력 [W], 양수
  └─ Q_dot     : 0.0
```

#### 터빈 (`components/turbine.py`)

```python
# 입력
state_in : ThermodynamicState   # 터빈 입구 상태 (State 2')
P_out    : float                # 출구 압력 [Pa]
eta_t    : float                # 등엔트로피 효율 [-]
m_dot    : float                # 질량 유량 [kg/s]

# 출력
result   : ComponentResult
  └─ state_out : ThermodynamicState   # 터빈 출구 상태 (State 3)
  └─ W_dot     : float                # 발생 동력 [W], 음수
  └─ Q_dot     : 0.0
```

#### 열교환기 (`components/hx_heat_rejection.py`, `hx_heat_absorption.py`)

```python
# 입력
state_in : ThermodynamicState   # 입구 상태
T_out    : float                # 출구 온도 [K]  (또는 Q_dot 지정 방식도 가능)
m_dot    : float                # 질량 유량 [kg/s]

# 출력
result   : ComponentResult
  └─ state_out : ThermodynamicState   # 출구 상태
  └─ W_dot     : 0.0
  └─ Q_dot     : float                # 열량 [W], Hot HX: 양수 / Cold HX: 음수
```

### 6.3 `properties.py`의 역할 제한

CoolProp 직접 호출은 **`properties.py`만 허용**한다. 컴포넌트 내부에서 `CP.PropsSI()`를 직접 호출하지 않는다.

```python
# properties.py 주요 인터페이스
def state_from_TP(T_K, P_Pa, fluid, label="") -> ThermodynamicState
def state_from_sP(s, P_Pa, fluid, label="")   -> ThermodynamicState  # 등엔트로피 과정용
def state_from_hP(h, P_Pa, fluid, label="")   -> ThermodynamicState
```

이 규칙을 지키면 나중에 CoolProp을 다른 물성 라이브러리로 교체할 때 `properties.py`만 수정하면 된다.

### 6.4 `cycle_solver.py`에서의 활용 패턴

컴포넌트가 동일한 시그니처를 따르므로, 사이클 위상을 컴포넌트 리스트로 표현하고 순차 실행할 수 있다.

```python
# cycles/simple_brayton.py 에서 위상 정의
SEQUENCE = [
    ("compressor", compressor.run),
    ("hot_hx",     hx_heat_rejection.run),
    ("turbine",    turbine.run),
    ("cold_hx",    hx_heat_absorption.run),
]

# cycle_solver.py 에서 범용 실행
results = []
state = state_init
for name, component_fn in cycle.SEQUENCE:
    result = component_fn(state, ...)
    results.append(result)
    state = result.state_out

# 에너지 평형 검증
energy_residual = sum(r.W_dot + r.Q_dot for r in results)
assert abs(energy_residual) / Q_cold < 1e-6
```

---

## 7. 수치 해석 고려사항

### 7.1 수렴 조건

- 에너지 보존 검증: `|Q_cold + W_net - Q_hot| / Q_hot < 1e-6`
- 상태점 계산 시 CoolProp 오류 처리 (상 경계 근처 등)

### 7.2 압력 탐색 (scipy 활용)

```python
from scipy.optimize import brentq

def turbine_outlet_error(P_high):
    # 주어진 P_high에서 터빈 출구 온도 계산 후 목표값과의 차이 반환
    ...
    return T_3_calc - T_3_target

P_high_solution = brentq(turbine_outlet_error, P_low * 1.5, P_low * 20)
```

### 7.3 예외 처리

- CoolProp이 액상/2상 영역에서 호출될 경우 예외 발생 가능
- Air는 −193 °C(80 K) 이하에서 액화 시작 → T_3 = −100 °C(173 K)는 기상 영역으로 안전

---

## 8. 출력 결과 형식

### 8.1 콘솔 출력 예시

```
============================================================
  Simple Reverse Brayton Cryogenic Refrigerator Results
============================================================
  Fluid          : Air
  Mass Flow Rate : 0.500 kg/s
  Pressure Ratio : X.XX

  State Points:
  ┌──────────┬──────────┬──────────┬──────────┬──────────┐
  │  State   │  T [°C]  │  P [kPa] │ h [kJ/kg]│ s [kJ/kgK]│
  ├──────────┼──────────┼──────────┼──────────┼──────────┤
  │  1 (C-in)│   XX.X   │   XXX.X  │  XXXX.X  │   X.XXX  │
  │  2 (C-out)│   XX.X  │   XXX.X  │  XXXX.X  │   X.XXX  │
  │  2'(T-in)│   XX.X   │   XXX.X  │  XXXX.X  │   X.XXX  │
  │  3 (T-out)│ -100.0  │   XXX.X  │  XXXX.X  │   X.XXX  │
  └──────────┴──────────┴──────────┴──────────┴──────────┘

  Performance:
    Q_cold (Refrigeration)  : XX.XX kW
    W_compressor            : XX.XX kW
    W_turbine               : XX.XX kW
    W_net                   : XX.XX kW
    COP                     : X.XXX
    Energy balance error    : X.XXe-XX
============================================================
```

### 8.2 결과 파일

| 파일명 | 내용 |
|---|---|
| `results/state_points.csv` | 상태점 온도, 압력, 엔탈피, 엔트로피 |
| `results/performance.csv` | COP, 동력, 냉동 능력 |
| `results/cycle_Ts.png` | T-s 선도 (선택) |
| `results/cycle_Ph.png` | P-h 선도 (선택) |

---

## 9. 개발 순서 (권장)

1. `properties.py` — `ThermodynamicState`, `ComponentResult` 정의 및 CoolProp 래퍼 구현, 단위 테스트
2. `components/compressor.py` — I/O 인터페이스 준수하여 구현, 단독 검증
3. `components/turbine.py` — I/O 인터페이스 준수하여 구현, 단독 검증
4. `cycles/simple_brayton.py` — 컴포넌트 연결 순서(SEQUENCE) 정의
5. `cycle_solver.py` — 범용 솔버 구현, 에너지 평형 검증 (`ΣW_dot + ΣQ_dot ≈ 0`)
6. `main.py` — YAML 로드, solver 호출, 결과 폴더 자동 생성 및 저장
7. 파라미터 스윕 (압력비 vs COP) 및 T-s / P-h 선도 시각화

---

## 10. 의존성

```
Python >= 3.9
CoolProp >= 6.4
scipy >= 1.9
numpy >= 1.23
matplotlib >= 3.6    # 선도 시각화 (선택)
pandas >= 1.5        # 결과 저장 (선택)
```

설치:
```bash
pip install CoolProp scipy numpy matplotlib pandas
```

---

*Last updated: 2026-03-11 — 섹션 5 (파일명 체계화), 섹션 6 (컴포넌트 I/O 인터페이스) 추가*
