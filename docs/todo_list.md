# TODO List — Reverse Brayton Cryogenic Refrigerator

## 우선순위 높음

### [x] 0. `src/properties/` 패키지 구조 전환 (선행 조건)

**현재 상태**
`src/properties.py` 단일 파일로 CoolProp 기반 유체(Air 등)만 지원.
`src/properties/im7_liquid_properties.csv` 가 이미 존재하여 **파일/디렉터리 충돌** 상태.

**목표**
`properties` 를 패키지로 전환하여 CoolProp 유체 + 테이블 기반 유체를 통합 관리:

```
src/properties/
├─ __init__.py              ← 기존 properties.py 내용 이전 + fluid 분기 로직
├─ im7_properties.py        ← IM-7 테이블 기반 물성 (Task 0-B)
└─ im7_liquid_properties.csv
```

`state_from_TP(T, P, fluid, label)` 에서 `fluid` 문자열로 분기:
- `"Air"`, `"N2"`, `"He"` 등 → CoolProp 호출 (기존 동작 유지)
- `"IM7"` → `im7_properties` 모듈 호출

**변경 파일**
- `src/properties.py` → `src/properties/__init__.py` 로 이동 (내용 그대로)
- 기존 import `from properties import ...` 경로 불변 (패키지 `__init__` 이 동일 심볼 export)
- `cycle_solver.py`, `components/*.py`, `cycles/*.py` import 수정 불필요

**확장성**
- 향후 PAO, Syltherm 등 추가 시 `src/properties/<fluid>_properties.py` 신규 파일만 추가

---

### [x] 0-B. IM-7 유체 물성 모듈 (`im7_properties.py`) 구현

**의존**: Task 0 (패키지 전환) 완료 후 진행

**데이터 소스**
`src/properties/im7_liquid_properties.csv`
- 컬럼: T_C, T_K, Tr, P_sat_MPa, rho_liq_kg_m3, mu_liq_mPa_s, nu_liq_mm2_s, Cp_liq_J_kgK, k_liq_mW_mK
- 유효 범위: −70 ∼ 70°C (Cp, rho, mu, k). −100∼−80°C 및 80∼100°C 행은 빈 셀(NaN)

**구현 단계**

```
1. CSV 로드 + NaN 처리
   └─ 유효 데이터만 추출 (dropna per column)

2. 보간 함수 (각 물성 독립적으로)
   └─ scipy.interpolate.interp1d (kind='linear')
      + 범위 외: 명시적 linear extrapolation (fill_value 없이 직접 구현)
      + 외삽 시 경고 없음 (조용히 처리)

3. Cp(T) 다항식 피팅
   └─ numpy.polyfit(T_K, Cp, deg=2)  ← 데이터가 거의 선형이므로 2차로 충분
      (Cp ≈ 1030 + 2·(T_C+70) [J/kg·K], 선형에 가까움)

4. h(T) 해석적 적분  [T_ref = 273.15 K, h_ref = 0]
   └─ Cp = a₀ + a₁T + a₂T²  (T in K)
      h(T) = a₀(T−T_ref) + ½a₁(T²−T_ref²) + ⅓a₂(T³−T_ref³)

5. s(T) 해석적 적분  [T_ref = 273.15 K, s_ref = 0]
   └─ s(T) = a₀·ln(T/T_ref) + a₁(T−T_ref) + ½a₂(T²−T_ref²)

6. 단위 변환 (로드 시 1회)
   └─ k: mW/(m·K) → W/(m·K)  (÷1000)
      mu: mPa·s   → Pa·s      (÷1000)

7. state_from_TP_im7(T_K, P_Pa, label="") → ThermodynamicState
   └─ P_Pa 는 인자로 받되 내부 계산에 미사용 (비압축성 액체 가정)
```

**클래스 인터페이스**

```python
class IM7Properties:
    def h(self, T_K: float) -> float      # [J/kg]
    def s(self, T_K: float) -> float      # [J/kg·K]
    def rho(self, T_K: float) -> float    # [kg/m³]
    def Cp(self, T_K: float) -> float     # [J/kg·K]
    def mu(self, T_K: float) -> float     # [Pa·s]
    def k_th(self, T_K: float) -> float   # [W/m·K]  (k는 Python 예약어 회피)

# 모듈 수준 편의 함수 (CoolProp 인터페이스와 동일)
def state_from_TP(T_K, P_Pa, label="") -> ThermodynamicState
```

**외삽 범위 메모**
- Load HX 운전 시 IM-7 입구 ≈ −100°C 가능 → 데이터 하한(−70°C) 아래 외삽 발생
- 선형 외삽이므로 −100°C 에서 Cp ≈ 1030 − 2×30 = **970 J/kg·K** 로 추정됨 (합리적 범위)

---

### [ ] 1. ε-NTU 모델 적용 — Aftercooler / Load HX

**현재 상태**
`hx_heat_rejection.py` (Aftercooler) / `hx_heat_absorption.py` (Load HX) 모두 출구 온도(`T_out`)를 직접 지정.
실제 열교환기 크기(UA)와 유체 조건으로부터 성능을 계산하지 않음.

**목표**
NTU–효율 관계식으로 출구 상태를 결정:

```
ε  = 1 − exp(−NTU)          (한쪽 유체 C_min → ∞, 예: 외기 / 냉매 측)
NTU = UA / C_min
T_out = T_in − ε · (T_in − T_secondary)
```

또는 두 유체 모두 유한 열용량인 경우 counter-flow ε-NTU:

```
ε = [1 − exp(−NTU·(1−C_r))] / [1 − C_r·exp(−NTU·(1−C_r))]
C_r = C_min / C_max
```

**변경 파일**
- `src/components/hx_heat_rejection.py` — `run(state_in, UA, T_secondary, m_dot, m_dot_secondary, fluid_secondary)` 로 시그니처 변경
- `src/components/hx_heat_absorption.py` — 동일
- `configs/simple_baseline.yaml`, `configs/recuperated_baseline.yaml` — `hx_aftercooler.T_outlet` 대신 `hx_aftercooler.UA`, `hx_aftercooler.T_secondary` 로 교체; `hx_load.UA`, `hx_load.T_secondary` 추가
- `src/cycles/simple_brayton.py`, `src/cycles/recuperated_brayton.py` — HX 호출부 수정

**비고**
- 1차적으로는 이차 유체(secondary)를 무한 열용량으로 가정(등온)하여 단순화 가능
- 이차 유체 유량·온도를 파라미터로 받는 구조 권장
- Recuperator(`hx_recup`)는 이미 ε 기반이므로 변경 불필요

---

### [ ] 2. 열교환기 압력 손실 모델링 (Pressure Drop)

**현재 상태**
모든 HX에서 작동 유체의 출구 압력 = 입구 압력 (압손 = 0 가정).

**목표 (1단계: 고정값 압손)**
각 HX에 상수 압손 `dP [Pa]` 를 파라미터로 추가:

```
P_out = P_in − dP
```

사이클 영향:
- Aftercooler (`hx_aftercooler`) 압손 → 터빈 입구 압력 저하 → 팽창비 감소 → W_turbine ↓
- Load HX (`hx_load`) 압손 → 압축기 입구 압력 저하 → 압축비 증가 → W_compressor ↑
- Recuperator (`hx_recup`) 양측 압손 → 동일 방향으로 영향

**변경 파일**
- `src/components/hx_heat_rejection.py` — `run(..., dP=0.0)` 추가, `P_out = state_in.P - dP`로 출구 상태 계산
- `src/components/hx_heat_absorption.py` — 동일
- `src/components/hx_recuperator.py` — `dP_hot=0.0`, `dP_cold=0.0` 추가
- `configs/simple_baseline.yaml`, `configs/recuperated_baseline.yaml` — `hx_aftercooler.dP`, `hx_load.dP`, `hx_recup.dP_hot`, `hx_recup.dP_cold` 활성화 (현재 0으로 설정됨)
- `src/cycles/simple_brayton.py`, `src/cycles/recuperated_brayton.py` — HX 호출 시 dP 전달; 각 상태점 압력 반영

**비고**
- 압손이 있으면 `P_high` outer brentq 의 수렴 조건 변경 없음 (`turbine.T_outlet_target` 기준 유지)
- 단, 압손 합산이 클 경우 P_high / P_low 의 정의 재검토 필요:
  - P_low = 압축기 입구 압력 (Load HX 출구) — 압손 반영 시 Load HX 입구 ≠ P_low
  - 향후 2단계에서 각 상태점 압력을 독립 변수로 분리 고려

---

### [ ] 3. UA·LMTD 후처리 (post-processing)

**현재 상태**
ε 기반 리큐퍼레이터와 지정 온도 HX만 있어 실제 열교환기 크기를 계산하지 않음.

**목표**
시뮬레이션 결과로부터 각 열교환기의 UA 와 LMTD 역산:

```
UA = Q_dot / LMTD
LMTD = (ΔT1 − ΔT2) / ln(ΔT1 / ΔT2)
```

**변경 파일**
- `src/postprocess/hx_sizing.py` (신규) — `compute_UA(Q_dot, T_hot_in, T_hot_out, T_cold_in, T_cold_out)`
- `main.py` — 성능 출력 섹션에 UA / LMTD 행 추가
- `results/*/performance.csv` — UA, LMTD 컬럼 추가

---

## 우선순위 중간

### [ ] 3. 파라미터 스윕 자동화 개선

**현재 상태**
`visualize.py`의 `sweep_rp()` 는 압력비 스윕만 지원.

**목표**
- 효율(η_c, η_t), 유효도(ε), 질량유량(m_dot) 스윕 추가
- 스윕 결과 CSV 자동 저장
- 2D 파라미터 공간 히트맵 (예: η_c × ε → COP)

---

### [ ] 4. 복합 사이클 구성 지원

**현재 상태**
Simple / Recuperated 두 사이클 고정.

**목표**
두 단 압축기 (two-stage compression with intercooling) 또는 두 단 팽창기 사이클 지원.

---

## 우선순위 낮음

### [ ] 5. 단위 테스트 추가

- `tests/test_compressor.py` — 이상기체 등엔트로피 관계 검증
- `tests/test_turbine.py`
- `tests/test_recuperator.py` — 에너지 균형 검증
- `tests/test_cycle_solver.py` — Simple / Recuperated 결과 회귀 테스트

### [ ] 6. 작동 유체 확장

**현재 상태**
Air 고정 (CoolProp `"Air"` pseudo-pure).

**목표**
- N₂, He, Ar 지원
- YAML `fluid:` 변경만으로 사이클 재계산 가능 (이미 구조적으로 지원됨 — 검증 필요)

---

## 완료됨

- [x] Simple Reverse Brayton cycle 4-상태 구현 (1→2→3→4)
- [x] 상태 표기 정수화 (prime 표기 제거)
- [x] HX 분리: `hx_base`, `hx_heat_rejection`, `hx_heat_absorption`, `hx_recuperator`
- [x] Recuperated Brayton cycle 6-상태 구현 (1→6)
- [x] 리큐퍼레이터 순환 의존성 inner brentq 해결
- [x] CoolProp 이상 영역 ValueError 핸들링 (T4_lo = 140 K)
- [x] main.py 대화형 사이클 선택 메뉴
- [x] visualize.py 4/6-상태 자동 분기
- [x] docs/modeling_guide.md 전면 업데이트
- [x] YAML 계층 구조 리팩토링 (comp/turbine/hx_aftercooler/hx_load/hx_recup)
- [x] 컴포넌트 명칭 통일: Aftercooler (`hx_aftercooler`), Load HX (`hx_load`), Recuperator (`hx_recup`)
