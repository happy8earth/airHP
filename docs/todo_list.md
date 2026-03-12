# TODO List — Reverse Brayton Cryogenic Refrigerator

---

## 우선순위 높음

### [ ] A. Bypass 사이클 구현 — Topology A (Mixer @ Expander 전단)

**목표**
압축기 토출부(State 2)에서 추기율 `x`만큼 분기하여 Expander 입구에서 혼합하는 사이클 구현.
**핵심 설계 문제**: Load HX 2차측 출구온도(`T_sec_out`) 목표값을 만족하는 데 필요한 추기율 `x`를 역산.

**배경 — Load HX 2차측 열균형**
```
Q_load = ṁ_sec × Cp_sec × (T_sec_in − T_sec_out)
```
- `T_sec_out` (목표), `T_sec_in`, `ṁ_sec` → `Q_load` 결정
- Bypass는 Expander 출구온도(T_air_in)를 조절 → T_sec_out 제어
- bypass 부족 → 냉매 과냉 → T_sec_out 과도 하강
- bypass 과다 → 냉매 불충분 냉각 → T_sec_out 목표 미달

**DOF 분석 결론**

| 미지수 | {T1, T4, x} = 3 | (P_high는 pressure_ratio로 고정) |
|--------|-----------------|----------------------------------|
| 제약 방정식 | Load HX UA-LMTD (⑥) + Recuperator 에너지 (⑦) + Recuperator UA-LMTD (⑧) = 3 |
| **DOF** | **= 0** ✓ 완전 결정계 |

- `pressure_ratio` 고정값 지정 → `P_high = P_low × r_p` 고정 → DOF 닫힘
- Load HX는 **순방향(forward) UA-LMTD 모드** 유지: T_sec_in 고정, T_sec_out을 출력으로 계산
- brentq는 x에 대해서만 수행: `T_sec_out_cycle(x) − T_sec_out_target = 0`
- `T_outlet_target` 불필요 (기존 recuperated 사이클의 outer brentq 조건은 bypass 사이클에서 사용 안 함)

**새 토폴로지**
```
State 2 ─(1-x)→ [Aftercooler] → [Recup.hot] → State 4 ─┐
         └─(x)──────────────────────────────── State 2  ─┴→ [Mixer] → State 4m → [Expander] → [LoadHX] → [Recup.cold] → State 1
```

**세부 액션**

**A-1. `src/components/splitter.py` 신규 작성**
- 입력: `state_in`, `x` (bypass 분율), `m_dot`
- 출력: `(state_main, m_dot_main, state_bypass, m_dot_bypass)`
- 물리: 질량/에너지 보존, 양측 상태 동일(압력·엔탈피 변화 없음)

**A-2. `src/components/mixer.py` 신규 작성**
- 입력: `state_a`, `m_dot_a`, `state_b`, `m_dot_b`, `fluid`
- 출력: `ComponentResult` (혼합 출구 상태)
- 물리: `h_mix = (ṁ_a·h_a + ṁ_b·h_b) / (ṁ_a + ṁ_b)`, 같은 압력 가정

**A-3. `src/components/hx_recuperator.py` 수정**
- 현재: Hot/Cold 양측 `m_dot` 동일 가정
- 변경: `m_dot_hot`, `m_dot_cold` 독립 인자 추가
- UA 스케일링: 각 측 독립적으로 `(m_dot/m_dot_rated)^0.8` 적용 후 평균 또는 최소값 검토
- 기존 Recuperated 사이클 호환성 유지 (기본값 `m_dot_hot = m_dot_cold = m_dot`)

**A-4. `src/cycles/bypass_a_brayton.py` 신규 작성**
- `run_cycle(config, P_high, x)` 시그니처
- 외부 T1 고정점 반복 + 내부 brentq (T4 수렴)
- `T4m` (혼합 후 Expander 입구) = Mixer(State 2, State 4, x) 결과
- Recuperator: `m_dot_hot = (1-x)·ṁ`, `m_dot_cold = ṁ`
- Aftercooler: `m_dot = (1-x)·ṁ`
- Load HX: **순방향 UA·LMTD 모드** — `T_sec_in` 고정, `T_sec_out` 출력 (기존 recuperated 방식 유지)
- `T_outlet_target` 미사용 — `pressure_ratio`로 P_high가 이미 고정되므로 outer brentq 불필요
- 반환값에 `T_sec_out` (Load HX 2차측 출구온도) 포함

**A-5. `configs/bypass_a_baseline.yaml` 신규 작성**
- Recuperated baseline 기반
- `pressure_ratio`: **고정값 필수** (null 불가) — DOF를 닫는 핵심 파라미터
- `expander.T_outlet_target`: bypass 사이클에서는 참고값으로만 존재 (수렴 기준 아님)
- `hx_load` 섹션에 `T_sec_out_target` 파라미터 추가 (역산 목표값, bypass_solver가 사용)
- `bypass.x`: 역산 결과로 출력 (YAML 입력값 아님)

**A-6. 역산 Solver: T_sec_out_target → x**
- 별도 `bypass_solver.py` 또는 `cycle_solver.py` 확장으로 구현
- `P_high = P_low × pressure_ratio` 로 고정 (DOF 닫기)
- 내부 brentq: `x` ∈ [0, x_max] 에서 `T_sec_out_cycle(x) − T_sec_out_target = 0` 수렴
  - `T_sec_out_cycle(x)`: `bypass_a_brayton.run_cycle(config, P_high, x)` 반환값
- 수렴 후 출력: 필요 추기율 `x`, COP, W_net, Q_load, 전체 상태점

**A-7. T_sec_out_target 스윕 + 시각화**
- `visualize.py`에 `sweep_T_sec_out(config, T_targets)` 함수 추가
- 출력: `x`, COP, W_net, T_expander_outlet vs. `T_sec_out_target` 그래프
- 결과 CSV 저장: `results/<run>/x_vs_T_sec_out.csv`

**A-8. `src/components/hx_load.py` — ε, T_sec_out 출력 추가**
- 현재: `extra={"UA": UA, "LMTD": lmtd}` 만 반환; `_T_sec_out` 버려짐
- 추가: `T_sec_out` (IM-7 출구온도), ε (effectiveness) 계산 후 `extra`에 포함
  - `ε = Q_actual / Q_max`, `Q_max = C_min × (T_sec_in − T_air_in)`
  - `C_hot = ṁ_IM7 × Cp_IM7`, `C_cold = ṁ_air × Cp_air`, `C_min = min(C_hot, C_cold)`
- 사이클 출력(`run_cycle` 반환 dict)에 `T_sec_out`, `epsilon_load` 키 추가
- 역산 solver(A-6)에서 `T_sec_out_cycle(x)` 로 직접 사용

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

### [ ] B. Bypass 사이클 구현 — Topology B (Mixer @ Expander 후단)

**목표**
추기 스트림을 교축(등엔탈피 팽창) 후 Expander 출구에서 혼합하는 사이클 구현.

**새 토폴로지**
```
State 2 ─(1-x)→ [Aftercooler] → [Recup.hot] → [Expander] → State 5 ─┐
         └─(x)──→ [Throttle P_high→P_low] ──────────────── State 2t ─┴→ [Mixer] → State 5m → [LoadHX] → [Recup.cold] → State 1
```

**세부 액션**

**B-1. `src/components/throttle.py` 신규 작성**
- 물리: 등엔탈피 교축 (`h_out = h_in`, `P_out` 지정)
- 출력: `ComponentResult`

**B-2. `src/cycles/bypass_b_brayton.py` 신규 작성**
- Expander는 `(1-x)·ṁ` 처리
- Mixer: throttle 출구(State 2t) + Expander 출구(State 5) → State 5m
- LoadHX, Recuperator cold side: 전체 유량 `ṁ` 처리

**B-3. Topology A vs B 비교 분석**
- 동일 추기율 x에서 양 토폴로지 성능 비교 그래프

---

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
- `tests/test_recuperator.py` — 에너지 균형 검증 (불균형 유량 케이스 포함)
- `tests/test_mixer.py` — 에너지 보존 검증
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
- [x] HX 분리: `hx_aftercooler`, `hx_load`, `hx_recuperator` (`hx_base` 삭제 — UA·LMTD 전환으로 불필요)
- [x] Recuperated Brayton cycle 6-상태 구현 (1→6)
- [x] 리큐퍼레이터 순환 의존성 inner brentq 해결
- [x] CoolProp 이상 영역 ValueError 핸들링 (T4_lo = 140 K)
- [x] main.py 대화형 사이클 선택 메뉴
- [x] visualize.py 4/6-상태 자동 분기
- [x] docs/modeling_guide.md 전면 업데이트
- [x] YAML 계층 구조 리팩토링 (comp/expander/hx_aftercooler/hx_load/hx_recup)
- [x] 컴포넌트 명칭 통일: `hx_aftercooler`, `hx_load`, `hx_recuperator` (파일명 포함)
- [x] Recuperated Load HX: Q_load 기반 State 6 계산 (`hx_load.Q_load` YAML 파라미터)
- [x] HX 모델 전환: T_out 고정 → UA·LMTD (`hx_ua_lmtd.py` 공용 solver, UA scaling `(m_dot/m_dot_rated)^0.8`)
  - Aftercooler: 2차측 물, Simple T3=308 K / Recuperated T3=305 K, energy_error < 1.2e-3
  - Load HX: 2차측 IM-7 (Cp 가변), Simple T5=173.15 K / Recuperated T5=179.9 K
  - Recuperator: 양측 Air, T5=168.48 K, Q_cold=11.02 kW, COP=0.368, energy_error=5.8e-4
- [x] YAML HX 파라미터 hotside/coldside 분리 (`UA_rated` → `htc_rated`, `area`, `m_dot_rated` per side)
  - `configs/recuperated_baseline.yaml`, `configs/simple_baseline.yaml` 적용
  - `UA = 1/(1/hA_hot + 1/hA_cold)`, 각 측 독립 HTC·면적 지정 가능
  - `src/cycles/simple_brayton.py`, `src/cycles/recuperated_brayton.py` 호출 인자 갱신
  - A-3 (`hx_recuperator.py` 독립 유량) 수행을 위한 YAML 구조 준비 완료
