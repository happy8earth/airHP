# TODO List — Reverse Brayton Cryogenic Refrigerator

## 우선순위 높음

### [ ] 1. HX 모델 전환: T_out 고정 / ε-NTU → UA·LMTD

**전환 순서**: Aftercooler → Load HX → Recuperator (하나씩 순차 적용 후 검증)

**공통 사항**

2차측 유체: aftercooler = 물(water), hx_load = IM-7, hx_recup = 공기(대칭)

UA scaling (1차측만):
```
UA = UA_rated × (m_dot / m_dot_rated)^0.8
```

Catalog rated 값 (YAML 기입 완료):
| HX | UA_rated [W/K] | m_dot_rated [kg/s] | T_sec [K] | m_dot_sec [kg/s] |
|----|---|----|----|----|
| hx_aftercooler | 870 | 0.382 | 291.15 | 0.38 |
| hx_load | 1301.01 | 0.382 | 197.65 | 0.827 |
| hx_recup | 5102.04 | 0.382 | — (대칭) | — |

공용 solver (`hx_ua_lmtd.py`) — Aftercooler 전환 시 함께 작성:
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

### [ ] 1-1. Aftercooler UA·LMTD 전환
*(가장 단순 — 2차측 물, Cp 상수, 순환 의존성 없음)*

- **[A]** YAML: `hx_aftercooler.T_outlet` 제거 → `UA_rated, m_dot_rated, T_secondary, m_dot_secondary`
- **[B]** `hx_ua_lmtd.py` 공용 solver 신규 작성
- **[C]** `hx_aftercooler.py` 리팩터
  - hot = working fluid, cold = 물 (Cp_water ≈ 4186 J/kg·K)
  - `run(state_in, UA_rated, m_dot, m_dot_rated, T_sec, m_dot_sec)` → ComponentResult
- **[D]** `simple_brayton.py`: `T3_set` 제거 → aftercooler UA 기반 T3 계산
- **[E]** `recuperated_brayton.py`: 동일 (`T3_set` 제거)
- **[F]** `main.py`: Aftercooler UA [W/K], LMTD [K], Q_dot [W] 출력 추가
- 검증: Simple Brayton으로 T3, Q_dot, COP 확인

---

### [ ] 1-2. Load HX UA·LMTD 전환
*(2차측 IM-7, Cp 가변 — im7_properties 연동)*

- **[A]** YAML: `hx_load.UA_rated, m_dot_rated, T_secondary, m_dot_secondary` 추가
- **[B]** `hx_load.py` 리팩터
  - hot = IM-7 (Cp from im7_properties), cold = working fluid
  - `run(state_in, UA_rated, m_dot, m_dot_rated, T_sec, m_dot_sec)` → ComponentResult
- **[C]** `simple_brayton.py`, `recuperated_brayton.py`: Load HX 호출 인자 변경
  - T1 circular dependency → **fixed-point iteration** 추가
    (`T1_guess → run_cycle → T1_new → 반복, 보통 2~3회 수렴`)
- **[D]** `main.py`: Load HX UA [W/K], LMTD [K], Q_dot [W] 출력 추가
- 검증: T1 수렴성, Q_cold, COP 확인

---

### [ ] 1-3. Recuperator UA·LMTD 전환
*(양측 모두 작동유체, 가장 복잡 — inner brentq 수정 필요)*

- **[A]** YAML: `hx_recup.effectiveness` 제거 → `UA_rated, m_dot_rated`
- **[B]** `hx_recuperator.py` 리팩터
  - UA scaling: `UA = UA_rated × (m_dot / m_dot_rated)^0.8` (양측 대칭)
  - `run(state_hot_in, state_cold_in, UA_rated, m_dot, m_dot_rated)` → (result_hot, result_cold)
- **[C]** `recuperated_brayton.py` inner brentq residual 수정:
  ε 기반 `T4 = T3 - ε*(T3-T5)` → UA 기반 `Q(T4) - UA·LMTD(T4) = 0`
- **[D]** `main.py`: Recuperator UA [W/K], LMTD [K], Q_dot [W] 출력 추가
- 검증: T1 수렴성, 에너지 평형, COP 확인

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
- Aftercooler (`hx_aftercooler`) 압손 → 팽창기 입구 압력 저하 → 팽창비 감소 → W_expander ↓
- Load HX (`hx_load`) 압손 → 압축기 입구 압력 저하 → 압축비 증가 → W_compressor ↑
- Recuperator (`hx_recup`) 양측 압손 → 동일 방향으로 영향

**변경 파일**
- `src/components/hx_aftercooler.py` — `run(..., dP=0.0)` 추가, `P_out = state_in.P - dP`로 출구 상태 계산
- `src/components/hx_load.py` — 동일
- `src/components/hx_recuperator.py` — `dP_hot=0.0`, `dP_cold=0.0` 추가
- `configs/simple_baseline.yaml`, `configs/recuperated_baseline.yaml` — `hx_aftercooler.dP`, `hx_load.dP`, `hx_recup.dP_hot`, `hx_recup.dP_cold` 활성화 (현재 0으로 설정됨)
- `src/cycles/simple_brayton.py`, `src/cycles/recuperated_brayton.py` — HX 호출 시 dP 전달; 각 상태점 압력 반영

**비고**
- 압손이 있으면 `P_high` outer brentq 의 수렴 조건 변경 없음 (`expander.T_outlet_target` 기준 유지)
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
- `tests/test_expander.py`
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
- [x] HX 분리: `hx_base`, `hx_aftercooler`, `hx_load`, `hx_recuperator`
- [x] Recuperated Brayton cycle 6-상태 구현 (1→6)
- [x] 리큐퍼레이터 순환 의존성 inner brentq 해결
- [x] CoolProp 이상 영역 ValueError 핸들링 (T4_lo = 140 K)
- [x] main.py 대화형 사이클 선택 메뉴
- [x] visualize.py 4/6-상태 자동 분기
- [x] docs/modeling_guide.md 전면 업데이트
- [x] YAML 계층 구조 리팩토링 (comp/expander/hx_aftercooler/hx_load/hx_recup)
- [x] 컴포넌트 명칭 통일: `hx_aftercooler`, `hx_load`, `hx_recuperator` (파일명 포함)
- [x] Recuperated Load HX: Q_load 기반 State 6 계산 (`hx_load.Q_load` YAML 파라미터)
