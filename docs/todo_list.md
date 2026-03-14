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

**[완료] A-9. `src/components/hx_recuperator.py` — Signed Q (방향 보존 열량 모델)**

- **배경**: Bypass_A 사이클에서 x ≳ 0.45 구간에서 recuperator의 cold-side 입구가 hot-side 입구보다 높아지는 온도역전 발생 → 역방향 열전달 모델링 필요
- **목표**: 스트림 레이블(hot/cold) 고정 상태에서 Q에 방향 부호를 부여 → Q 부호만으로 열전달 방향 식별 가능, 정보 소실 없음
- **로직**:
  ```
  direction = sign(T_hot_in - T_cold_in)   # +1: 정방향, −1: 역방향
  LMTD = LMTD(|ΔT|)                        # 절댓값 기반으로 항상 양수
  Q = direction × UA × LMTD               # 부호 있는 열량
  T_hot_out  = T_hot_in  − Q / (m_dot_hot  × Cp_hot)
  T_cold_out = T_cold_in + Q / (m_dot_cold × Cp_cold)
  ```
- **결과 해석**: Q > 0 → 정방향(hot→cold), Q < 0 → 역방향(cold→hot)
- ΔT_in = 0일 때 direction = 0 → Q = 0 도출

---

**A-8. `src/components/hx_load.py` — ε, T_sec_out 출력 추가**
- 현재: `extra={"UA": UA, "LMTD": lmtd}` 만 반환; `_T_sec_out` 버려짐
- 추가: `T_sec_out` (IM-7 출구온도), ε (effectiveness) 계산 후 `extra`에 포함
  - `ε = Q_actual / Q_max`, `Q_max = C_min × (T_sec_in − T_air_in)`
  - `C_hot = ṁ_IM7 × Cp_IM7`, `C_cold = ṁ_air × Cp_air`, `C_min = min(C_hot, C_cold)`
- 사이클 출력(`run_cycle` 반환 dict)에 `T_sec_out`, `epsilon_load` 키 추가
- 역산 solver(A-6)에서 `T_sec_out_cycle(x)` 로 직접 사용

---
### [x] 1. Load측 모델링

**토폴로지**
```
Chuck 출구(T_chuck_sec_out)
  → [Heater +Q_heater] → T_load_sec_in
  → [Splitter]
      ├─(1-y)·ṁ_sec ──→ [hx_load 2차측] → T_load_sec_out ─┐
      └─ y·ṁ_sec (bypass) ────────────── T_load_sec_in ──→ [Mixer] → T_chuck_sec_in → [Chuck]
```

**변수 매핑 (입력 → 출력)**

| 입력 변수 | 결정하는 출력 |
|-----------|--------------|
| `Q_heater` | `T_load_sec_in` (heater 출구 = hx_load 2차측 입구) |
| `x` (공기측 bypass) | `T_load_sec_out` (hx_load 2차측 출구) — 공기측 상태와 함께 결정 |
| `y` (2차측 bypass) | `mdot_load_sec = (1-y)·ṁ_sec` (hx_load 통과 유량) |

**지배 방정식**

```
① Chuck 에너지 균형 :  T_chuck_sec_out = T_chuck_sec_in + Q_chuck / (ṁ_sec · Cp_sec)
② Heater 에너지 균형:  T_load_sec_in   = T_chuck_sec_out + Q_heater / (ṁ_sec · Cp_sec)
③ hx_load UA-LMTD  :  T_load_sec_out  = f(T_load_sec_in, mdot_load_sec)   [기존 모델]
④ Mixer 제약        :  T_chuck_sec_in  = (1-y)·T_load_sec_out + y·T_load_sec_in
⑤ 유량 정의         :  mdot_load_sec   = (1-y)·ṁ_sec
```

→ 입력 고정 파라미터: `ṁ_sec`, `T_chuck_sec_in`, `Q_chuck`, `Q_heater`, `x`
→ 미지수: `T_chuck_sec_out`(①), `T_load_sec_in`(②), `T_load_sec_out`(③), `y`(④), `mdot_load_sec`(⑤) = 5개
→ 방정식 5개 → **완전 결정계** ✓

**자기일관성 (y ↔ T_load_sec_out 순환 의존성)**

③과 ④·⑤가 서로 연성됨:
```
y → mdot_load_sec = (1-y)·ṁ_sec → hx_load → T_load_sec_out → y (Mixer)
```
→ **brentq on y**: `f(y) = (1-y)·T_load_sec_out(y) + y·T_load_sec_in − T_chuck_sec_in = 0`


**세부 구현 액션**

**[완료] 1-1. `configs/bypass_a_baseline.yaml` — load측 파라미터 추가**
- `load_side.T_chuck_sec_in`: 303.15 K (30°C), `Q_chuck`: 0 W, `Q_heater`: 6000 W
- `m_dot_sec` 미기입 → `hx_load.hotside.m_dot_rated` (0.827 kg/s) 폴백

**[완료] 1-2. `src/load_side_solver.py` 신규 작성**
- `compute_T_load_sec_in(config)` → `(T_chuck_sec_out, T_load_sec_in)` — IM-7 h(T) 직접 사용
- `solve_y(T_load_sec_in, T_chuck_sec_in, m_dot_sec, T_load_sec_out_fn)` — brentq on y
  - y=1 경계: `T_load_sec_in ≤ T_chuck_sec_in + 0.01` → 직접 반환 (m_dot=0 ZeroDivisionError 방지)
  - 유효 운전점: Q_load=0이어도 역브레이튼 사이클 정상 동작 → 에러 아님
- `solve_load_side(config, T_load_sec_out_fn)` 통합 진입점

**[완료] 1-3. `src/bypass_solver.py` — load_side_solver 연동**
- `"load_side"` in config 시 State5 고정 후 `solve_load_side()` 호출 (비결합 근사)
- 반환 dict에 `load_side` 키 추가

**[완료] 1-4. 출력 및 검증**
- `main.py` performance.csv에 `y_sec`, `mdot_load_sec`, `T_chuck_sec_*`, `T_load_sec_*_ls`, `Q_chuck`, `Q_heater` 추가
- Q_heater=6000W, T_chuck_sec_in=303.15K → y=0.9553, mdot_load_sec=0.037 kg/s 검증 완료
- 한계: 비결합 근사로 `Q_cold ≠ Q_heater + Q_chuck` (air측 YAML 고정값 사용)

**[완료] 1-5. 결합 솔버 구현**

**배경**: 비결합 근사의 `Q_cold ≠ Q_heater + Q_chuck` 문제를 해결.
`T_load_sec_in`(Q_heater 역산)·`mdot_load_sec`(Mixer 해석해)를 air측 사이클에 직접 결합.

**결합 솔버 구조 (실제 구현)**:
```
1단계: T_load_sec_in  — compute_T_load_sec_in() (IM-7 h(T) 역산, 반복 없음)
2단계: y_sec          — Mixer 엔탈피 균형 해석적 계산 (brentq 불필요)
         y = (h(T_chuck) − h(T_target)) / (h(T_in) − h(T_target))
3단계: outer brentq on x: T_load_sec_out(x) = T_sec_out_target
         run_cycle(config, P_high, x, T_sec_load=T_load_sec_in, m_dot_hot_sec=m_dot_load_sec)
```

**구현 결과**:
- `src/cycles/bypass_a_brayton.py` — `T_sec_load`, `m_dot_hot_sec` optional 파라미터 추가 완료
- `src/coupled_solver.py` — `solve(config)` 함수; `Q_cold = Q_heater + Q_chuck` 수학적 보장
- `sweep.py` — `--mode Q` (Q_heater 스윕), `--mode T` (T_sec_out_target 스윕), `--mode 2D` (그리드 스윕)
- `visualize.py` — `plot_load_side()` 함수 추가 (load side 토폴로지 다이어그램 + 에너지 흐름)
- 스윕 결과 CSV + PNG 자동 저장: `results/sweep_<timestamp>/`

---

### [ ] 2. 열교환기 압력 손실 모델링 (Pressure Drop)

**현재 상태**
모든 HX에서 작동 유체의 출구 압력 = 입구 압력 (압손 = 0 가정).
각 YAML에 `dP: 0` / `dP_hot: 0` / `dP_cold: 0` 항목만 존재하며 코드에 미반영.

**P_low 정의 기준 (전 사이클 공통)**
`P_low` = 압축기 입구(State 1) 압력 = 고정 기준값.
압손이 있으면 Load HX 입구(= 팽창기 출구) 압력은 `P_low + dP_load`가 되며,
팽창기는 `P_low`가 아닌 `P_low + dP_load`까지만 팽창함 → 팽창기 일 감소.

---

#### 2-1. [ ] Simple 사이클 — 고정값 압손 구현 및 검증

**압력 캐스케이드**

| State | 설명 | 압력 |
|-------|------|------|
| State 1 | 압축기 입구 (기준점) | `P_low` |
| State 2 | 압축기 출구 | `P_high` |
| State 3 | Aftercooler 출구 / 팽창기 입구 | `P_high − dP_AC` |
| State 4 | 팽창기 출구 / Load HX 입구 | `P_low + dP_load` |
| State 1 | Load HX 출구 (순환 완결) | `P_low` ✓ |

팽창기 실제 압력비: `(P_high − dP_AC) / (P_low + dP_load)`

**변경 파일**
- `src/components/hx_aftercooler.py` — `run(..., dP=0.0)` 추가; `state_out.P = state_in.P − dP`
- `src/components/hx_load.py` — `run(..., dP=0.0)` 추가; `state_out.P = state_in.P − dP`
- `src/cycles/simple_brayton.py`
  - Aftercooler 호출 시 YAML `hx_aftercooler.dP` 전달
  - Expander `P_out = P_low + dP_load` (기존 `P_low` 대신)
  - Load HX 호출 시 `dP = dP_load` 전달
- `configs/simple_baseline.yaml` — `hx_aftercooler.dP`, `hx_load.dP` 값 기입

**검증 항목**
- `dP = 0` 시 기존 결과와 동일한지 확인 (회귀)
- `dP_AC = 5 000 Pa, dP_load = 2 000 Pa` 설정 후 에러 없이 실행
- 출력 dict에 각 State 압력값 포함 여부 확인

---

#### 2-2. [ ] Recuperated 사이클 — 고정값 압손 구현 및 검증

**압력 캐스케이드**

| State | 설명 | 압력 |
|-------|------|------|
| State 1 | 압축기 입구 | `P_low` |
| State 2 | 압축기 출구 | `P_high` |
| State 3 | Aftercooler 출구 | `P_high − dP_AC` |
| State 4 | Recup.hot 출구 / 팽창기 입구 | `P_high − dP_AC − dP_recup_hot` |
| State 5 | 팽창기 출구 / Recup.cold 입구 | `P_low + dP_load + dP_recup_cold` |
| State 6 | Recup.cold 출구 / Load HX 입구 | `P_low + dP_load` |
| State 1 | Load HX 출구 | `P_low` ✓ |

팽창기 실제 입출구 압력: State 4 → State 5 (양측 모두 dP 반영)

**변경 파일**
- `src/components/hx_recuperator.py` — `run(..., dP_hot=0.0, dP_cold=0.0)` 추가; 각 측 독립 압손 적용
- `src/cycles/recuperated_brayton.py`
  - 내부 brentq T4 잔차함수 내에서도 Recup 호출 시 `dP_hot` 전달 필요
  - Expander: `P_in = P_high − dP_AC − dP_recup_hot`, `P_out = P_low + dP_load + dP_recup_cold`
- `configs/recuperated_baseline.yaml` — 기존 `dP_hot: 0`, `dP_cold: 0` 값 기입

**주의 사항**
- 내부 brentq T4 수렴 구간 `[140 K, state3.T]` 에서 `state3.T` 계산 시 State 3 압력 = `P_high − dP_AC` 사용 확인

---

#### 2-3. [ ] Bypass_A 사이클 — 고정값 압손 구현 및 검증

**압력 캐스케이드 (분기별)**

| 경로 | State | 압력 |
|------|-------|------|
| 분기 전 | State 2 (압축기 출구) | `P_high` |
| 주 경로 | State 3 (AC 출구) | `P_high − dP_AC` |
| 주 경로 | State 4 (Recup.hot 출구) | `P_high − dP_AC − dP_recup_hot` |
| 바이패스 경로 | State 2_bypass (AC·Recup 미통과) | `P_high` |
| **혼합 후** | **State 4m (Mixer 출구)** | **`P_high − dP_AC − dP_recup_hot` (설계 결정)** |
| 공통 | State 5 (팽창기 출구) | `P_low + dP_load + dP_recup_cold` |
| 공통 | State 6 (Recup.cold 출구) | `P_low + dP_load` |
| 공통 | State 1 (Load HX 출구) | `P_low` ✓ |

**Mixer 압력 불일치 처리 방침**

| 스트림 | 압력 |
|--------|------|
| 주 경로 State 4 | `P_high − dP_AC − dP_recup_hot` (낮음) |
| 바이패스 State 2_bypass | `P_high` (높음) |

두 스트림의 압력이 다름 → Mixer 진입 전 압력 평형 필요.

- **이번 단계(2-3) 단순화 방침**: Mixer 출구 압력 = 낮은 쪽(주 경로) 기준.
  바이패스 스트림의 압력 강하는 암묵적 교축(등엔탈피)으로 간주. dP 값이 작을 때 허용 가능.
- `src/components/mixer.py` — 혼합 압력을 `min(state_a.P, state_b.P)` 로 변경 (현재: `state_a.P`)
- **향후 정밀 모델**: 바이패스 경로에 `throttle.py` (Topology B와 공용) 명시적 추가 후 혼합.

**변경 파일**
- `src/components/mixer.py` — 혼합 압력 `min(P_a, P_b)` 적용
- `src/cycles/bypass_a_brayton.py`
  - 압력 캐스케이드 변수 명시 계산 후 각 컴포넌트에 전달
  - Expander, Load HX, Recup 호출 시 실제 압력 반영
- `src/bypass_solver.py` — 변경 없음 (run_cycle 출력만 소비)
- `configs/bypass_a_baseline.yaml` — dP 항목 값 기입

**검증 항목**
- `x = 0` 시 Recuperated 사이클 결과와 동일한지 확인
- 바이패스 경로 State 2_bypass.P = P_high 유지, Mixer 출구 State 4m.P = State 4.P 확인

---

#### 2-4. [ ] 유량 의존 압손 스케일링 (Rated ΔP → 운전 유량별 ΔP)

**물리 배경**
카탈로그 정격 조건 `(dP_rated, m_dot_rated)`에서 운전 유량에 따른 압손 스케일링:

```
dP = dP_rated × (m_dot / m_dot_rated)^n
```

- `n = 2.0`: 완전 난류 (Darcy-Weisbach; 기본값 권장)
- `n = 1.8`: Dittus-Boelert (UA 스케일링 지수와 통일 시 사용)

**Bypass_A 분기 유량 적용**

| HX | 적용 유량 | dP 계산 |
|----|-----------|---------|
| Aftercooler | `(1−x)·ṁ` | `dP_AC_rated × ((1−x)·ṁ / ṁ_AC_rated)^n` |
| Recup.hot | `(1−x)·ṁ` | `dP_recup_hot_rated × ((1−x)·ṁ / ṁ_rated)^n` |
| Recup.cold | `ṁ` (전량) | `dP_recup_cold_rated × (ṁ / ṁ_rated)^n` |
| Load HX | `ṁ` (전량) | `dP_load_rated × (ṁ / ṁ_rated)^n` |

→ 바이패스율 `x` 증가 시 Aftercooler·Recup.hot 압손 감소, Recup.cold·Load HX 압손 불변.

**YAML 파라미터 추가 (예시)**
```yaml
hx_aftercooler:
  hotside:
    dP_rated: 5000.0    # [Pa] 카탈로그 정격 압손
    dP_scale_n: 2.0     # 스케일링 지수
```
`dP: 0` 고정값 인자도 하위호환으로 유지 (단계 2-1~2-3 결과와 전환 연속성 보장).

**변경 파일**
- `src/components/hx_aftercooler.py`, `hx_load.py`, `hx_recuperator.py`
  — `dP_rated`, `m_dot`, `m_dot_rated`, `n` 인자 추가; 내부에서 dP 계산
- `src/cycles/simple_brayton.py`, `recuperated_brayton.py`, `bypass_a_brayton.py`
  — YAML에서 `dP_rated`, `n` 읽어 각 컴포넌트 호출 시 유량과 함께 전달
- `configs/` 3종 — `dP_rated` 항목 추가

**검증 항목**
- `dP_rated = 0` 시 2-1~2-3과 동일 결과 (회귀)
- `x` 스윕 시 Aftercooler 압손 변화 그래프 확인
- COP vs `x` 곡선에 압손 효과 정량화 (압손 없는 케이스와 비교)

---

**구현 순서 요약**

| 단계 | 핵심 작업 | 상태 |
|------|-----------|------|
| 2-1 | Simple 사이클 고정값 dP 구현·검증 | [ ] |
| 2-2 | Recuperated 사이클 고정값 dP 구현·검증 | [ ] |
| 2-3 | Bypass_A 사이클 고정값 dP 구현·검증 (Mixer 압력 처리 포함) | [ ] |
| 2-4 | 유량 의존 스케일링 dP 구현·전 사이클 적용·COP 영향 분석 | [ ] |

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

## 완료됨 (Task A 전체 + Load측 모델링)

- [x] **A-1** `src/components/splitter.py` — 압축기 토출부 분기 (질량/에너지 보존, state 동일)
- [x] **A-2** `src/components/mixer.py` — 단열 혼합기 (h_mix = 가중 평균, 압력 동일)
- [x] **A-3** `src/components/hx_recuperator.py` — m_dot_hot/m_dot_cold 독립 인자 추가; 온도 역전 pass-through 처리
- [x] **A-4** `src/cycles/bypass_a_brayton.py` — 7-상태 bypass 사이클 (외부 T1 fixed-point + 내부 brentq T4); optional `T_sec_load`·`m_dot_hot_sec` 파라미터 추가 (결합 솔버 연동)
- [x] **A-5** `configs/bypass_a_baseline.yaml` — pressure_ratio 고정 + T_sec_out_target 지정
- [x] **A-6** `src/bypass_solver.py` — T_sec_out_target → x brentq 역산, x_max 이진 탐색, T1 발산 감지
- [x] **A-7** `visualize.py` — `sweep_T_sec_out()` 함수 추가; x, COP, W_net, T_expander_outlet vs T_sec_out_target 2×2 그래프 + CSV 저장; `main()` bypass 분기 처리
- [x] **A-8** `src/components/hx_load.py` — T_sec_out, ε (effectiveness) extra 출력 추가
- [x] **1-1** `configs/bypass_a_baseline.yaml` — load_side 파라미터 추가 (T_chuck_sec_in, Q_chuck, Q_heater)
- [x] **1-2** `src/load_side_solver.py` — `compute_T_load_sec_in()`, `solve_y()` (brentq on y), `solve_load_side()` 통합 진입점
- [x] **1-3** `src/bypass_solver.py` — load_side_solver 연동 (비결합 근사)
- [x] **1-4** `main.py` — performance.csv에 load_side 출력 추가; Q_heater=6000W 검증 완료
- [x] **1-5** `src/coupled_solver.py` — `solve(config)` 완전 결합 솔버; y 해석적 계산, `Q_cold = Q_heater + Q_chuck` 수학적 보장
- [x] **1-5** `sweep.py` — `--mode Q/T/2D` 파라미터 스윕 (Q_heater·T_sec_out_target); CSV + PNG 자동 저장
- [x] **1-5** `visualize.py` — `plot_load_side()` load side 토폴로지 다이어그램 추가

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
