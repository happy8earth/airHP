# TODO List — Reverse Brayton Cryogenic Refrigerator

## 우선순위 높음

### [ ] 1. ε-NTU 모델 적용 — Hot HX / Cold HX

**현재 상태**
`hx_heat_rejection.py` / `hx_heat_absorption.py` 모두 출구 온도(`T_out`)를 직접 지정.
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
- `configs/simple_baseline.yaml`, `configs/recuperated_baseline.yaml` — `T_hot_hx_outlet` / `T_compressor_inlet` 대신 `UA_hot_hx` / `UA_cold_hx` 추가
- `src/cycles/simple_brayton.py`, `src/cycles/recuperated_brayton.py` — HX 호출부 수정

**비고**
- 1차적으로는 이차 유체(secondary)를 무한 열용량으로 가정(등온)하여 단순화 가능
- 이차 유체 유량·온도를 파라미터로 받는 구조 권장
- 리큐퍼레이터(`hx_recuperator.py`)는 이미 ε 기반이므로 변경 불필요

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
- Hot HX 압손 → 터빈 입구 압력 저하 → 팽창비 감소 → W_turbine ↓
- Cold HX 압손 → 압축기 입구 압력 저하 → 압축비 증가 → W_compressor ↑
- 리큐퍼레이터 양측 압손 → 동일 방향으로 영향

**변경 파일**
- `src/components/hx_heat_rejection.py` — `run(..., dP=0.0)` 추가, `P_out = state_in.P - dP`로 출구 상태 계산
- `src/components/hx_heat_absorption.py` — 동일
- `src/components/hx_recuperator.py` — `dP_hot=0.0`, `dP_cold=0.0` 추가
- `configs/simple_baseline.yaml`, `configs/recuperated_baseline.yaml` — `dP_hot_hx`, `dP_cold_hx`, `dP_recuperator_hot`, `dP_recuperator_cold` 항목 추가 (기본값 0)
- `src/cycles/simple_brayton.py`, `src/cycles/recuperated_brayton.py` — HX 호출 시 dP 전달; 각 상태점 압력 반영

**비고**
- 압손이 있으면 `P_high` outer brentq 의 수렴 조건 변경 없음 (T_turbine_outlet 기준 유지)
- 단, 압손 합산이 클 경우 P_high / P_low 의 정의 재검토 필요:
  - P_low = 압축기 입구 압력 (Cold HX 출구) — 압손 반영 시 Cold HX 입구 ≠ P_low
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
