# TODO List — Reverse Brayton Cryogenic Refrigerator

## 우선순위 높음

### [x] 0. Recuperated Load HX: Q_load-based outlet

- Goal: use Q_load (refrigeration load) to compute load HX outlet temperature (State 6) instead of fixed T_outlet
- Q_load: **5 kW** (fixed for baseline)
- Rationale: with topology recup cold side = 6→1, fixed T_outlet can make T_hot_in <= T_cold_in and break recuperator
- YAML proposal:
  - add `hx_load.Q_load` [W]
  - make `hx_load.T_outlet` optional; define priority if both exist
- Topology: 3→4 (recup hot), 4→5 (expander), 5→6 (load HX), 6→1 (recup cold)
- Checks:
  - sign convention for Q_load (positive = cooling load)
  - bounds/feasibility for property inversion


### [ ] 1. HX 모델 전환: T_out 고정 / ε-NTU → UA·LMTD

**대상**: hx_aftercooler, hx_load, hx_recup (전체 전환)

**2차측 유체**: aftercooler = 물(water), hx_load = IM-7, hx_recup = 공기(대칭)

**UA scaling**: 2차측 유량 고정(rated) → 1차측만 scaling
```
UA = UA_rated × (m_dot / m_dot_rated)^0.8
```

**Catalog rated 값 (YAML 기입 완료)**
| HX | UA_rated [W/K] | m_dot_rated [kg/s] | T_sec [K] | m_dot_sec [kg/s] |
|----|---|----|----|----|
| aftercooler | 870 | 0.382 | 291.15 | 0.38 |
| hx_load | 1301.01 | 0.382 | 197.65 | 0.827 |
| hx_recup | 5102.04 | 0.382 | — (대칭) | — |

**구조 변화 (핵심)**
- 기존: `T3`(aftercooler 출구), `T1`(comp 입구) = config 고정값
- 변경 후: `T3`, `T1` = UA·LMTD 계산 결과 (output)
- T1 circular dependency → cycle solver 내 **fixed-point iteration** 추가
  (`T1_guess → run_cycle → T1_new → 반복, 보통 2~3회 수렴`)

---

#### [A] YAML 파라미터 교체

- `hx_aftercooler`: `T_outlet` 제거 → `UA_rated, m_dot_rated, T_secondary, m_dot_secondary`
- `hx_load`: `UA_rated, m_dot_rated, T_secondary, m_dot_secondary` 추가
- `hx_recup`: `effectiveness` 제거 → `UA_rated, m_dot_rated`
- simple_baseline.yaml, recuperated_baseline.yaml 모두 적용

---

#### [B] `hx_ua_lmtd.py` — 공용 counter-flow solver 신규 구현

```python
# src/components/hx_ua_lmtd.py
def ua_scale(UA_rated, m_dot, m_dot_rated) -> float
def solve_counterflow(UA, state_hot_in, state_cold_in,
                      m_dot_hot, m_dot_cold,
                      fluid_cold="Air") -> (T_hot_out, T_cold_out, Q_dot, LMTD)
# 내부: brentq on T_hot_out
# Residual: Q_dot(T_hot_out) - UA * LMTD(T_hot_out) = 0
```

---

#### [C] `hx_heat_rejection.py` 리팩터

- hot side = working fluid, cold side = 물 (Cp_water ≈ 4186 J/kg·K)
- `run(state_in, UA_rated, m_dot, m_dot_rated, T_sec, m_dot_sec)` → ComponentResult

---

#### [D] `hx_heat_absorption.py` 리팩터

- hot side = IM-7 (Cp from im7_properties), cold side = working fluid
- `run(state_in, UA_rated, m_dot, m_dot_rated, T_sec, m_dot_sec)` → ComponentResult

---

#### [E] `hx_recuperator.py` 리팩터

- `effectiveness` 제거, `UA_rated, m_dot_rated` 사용
- UA scaling: `UA = UA_rated × (m_dot / m_dot_rated)^0.8` (양측 대칭)
- `run(state_hot_in, state_cold_in, UA_rated, m_dot, m_dot_rated)` → (result_hot, result_cold)

---

#### [F] cycle solver 업데이트

- `simple_brayton.py`, `recuperated_brayton.py`:
  - `T3_set` 제거 → aftercooler UA 기반으로 T3 계산
  - `T_out=T1` 제거 → cold HX UA 기반으로 T1 계산
  - T1 fixed-point loop 추가 (초기값 = `comp.T_inlet_guess`)
  - `recuperated_brayton.py` inner brentq residual 수정:
    ε 기반 `T4 = T3 - ε*(T3-T5)` → UA 기반 `Q(T4) - UA·LMTD(T4) = 0`

---

#### [G] `main.py` 출력 업데이트

- 각 HX별 UA [W/K], LMTD [K], Q_dot [W] 출력 행 추가

---

### [ ] 2. 열교환기 압력 손실 모델링 (Pressure Drop)

**현재 상태**
모든 HX에서 작동 유체의 출구 압력 = 입구 압력 (압손 = 0 가정).

**목표 (1단계: 고정값 압손)**
각 HX에 상수 압손 `dP [Pa]` 를 파라미터로 추가:

```
P_out = P_in - dP
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

- [x] `src/properties/` 패키지 전환 — `properties.py` → `properties/__init__.py`, `fluid` 문자열 분기 (`"IM7"` vs CoolProp)
- [x] IM-7 물성 모듈 (`im7_properties.py`) — CSV 보간 + 2차 Cp 피팅 + h/s 해석적 적분, 유효범위 −70∼70°C (외삽 지원)
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

