# airHP Code Architecture

이 문서는 `d:\workPy\airHP` 폴더의 실제 구현을 기준으로 코드 구조와 데이터 흐름을 요약합니다.

---

## 프로젝트 목적

역브레이튼(Reverse Brayton) 냉동 사이클 시뮬레이터.
주요 연구 목표는 다음과 같습니다.

1. **기본 사이클 분석**: Simple / Recuperated Reverse Brayton 사이클의 열역학적 성능(COP, Q_cold, W_net) 계산
2. **추기(Bypass/Bleed) 사이클 설계**: 압축기 토출부에서 에어냉매를 분기하여 팽창기 전·후단에 혼합하는 구성에서, **Load HX 2차측 출구온도(T_sec_out) 목표값을 만족하는 데 필요한 추기율(x)을 역산**

### Load HX 열균형 구조

```
IM-7 (냉동 공간에서 열 흡수 후) ─── T_sec_in ──→ [Load HX] ──→ T_sec_out ──→ 챔버 복귀
                                                     ↕
                             Air (Expander 출구) ─── T_air_in (cold) ──→ T_air_out
```

- `Q_load = ṁ_sec × Cp_sec × (T_sec_in − T_sec_out)` : 실제 냉동 부하
- `T_sec_in`, `T_sec_out`, `ṁ_sec` 가 주어지면 `Q_load`가 결정됨
- Bypass는 `T_air_in`(팽창기 출구온도)을 조절하여 `T_sec_out`을 제어하는 수단

### 역산 문제 (Inverse Problem)

| 구분 | 변수 |
|------|------|
| **입력 (설계 조건)** | `T_sec_out` (목표), `T_sec_in`, `ṁ_sec` → `Q_load` 결정 |
| **출력 (계산 결과)** | 필요 추기율 `x`, COP, W_net, 전체 상태점 |
| **Solver** | `x`에 대한 외부 brentq — `T_sec_out_cycle == T_sec_out_target` 수렴 |

### 계획된 Bypass 토폴로지

| 토폴로지 | Mixer 위치 | 특징 |
|----------|-----------|------|
| **Topology A** | Expander **전단** | bypass 스트림과 회수된 냉각 공기를 고압에서 혼합 후 팽창 |
| **Topology B** | Expander **후단** | bypass 스트림을 교축(throttle) 후 팽창기 출구에서 혼합 |

```
[Topology A]
State 2 ─(1-x)→ [Aftercooler] → [Recup.hot] → State 4 ─┐
         └─(x)──────────────────────────────── State 2  ─┴→ [Mixer] → [Expander] → [LoadHX] → [Recup.cold] → State 1

[Topology B]
State 2 ─(1-x)→ [Aftercooler] → [Recup.hot] → [Expander] → State 5 ─┐
         └─(x)──→ [Throttle] ──────────────────────────── State 2t ──┴→ [Mixer] → [LoadHX] → [Recup.cold] → State 1
```

---

## Code Architecture

**1. 엔트리포인트**
1. `main.py`
   - CLI로 YAML 설정을 로드하고 `cycle_solver.solve()`를 실행합니다.
   - 콘솔 출력과 함께 결과를 CSV로 저장합니다.
1. `visualize.py`
   - 실행 결과를 T-s, P-h 다이어그램으로 저장합니다.
   - `pressure_ratio` 스윕을 수행해 COP/냉동능력/터빈출구온도 곡선을 출력합니다.

**2. 핵심 실행 흐름**
1. `main.py`/`visualize.py`가 YAML을 로드합니다.
1. `src/cycle_solver.py`의 `solve(config)`가 사이클 모듈을 동적 import 합니다.
1. `pressure_ratio`가 `null`이면 brentq로 `P_high`를 찾습니다.
   - 목표: `turbine.T_outlet_target`에 도달하는 `P_high`를 계산.
1. 사이클 실행 방식은 두 가지입니다.
   - `run_cycle()`이 있으면 해당 함수를 직접 호출.
   - 없으면 `SEQUENCE` 기반 순차 실행.
1. 계산된 `ThermodynamicState`와 `ComponentResult`를 모아 성능 지표(COP, Q_cold, W_net 등)를 계산합니다.
1. `results/{cycle}__{rp}__{Tt}__{etac}__{etat}/`에 결과 저장.

**3. 사이클 모듈**
1. `src/cycles/simple_brayton.py`
   - `SEQUENCE` 기반 4-state 단순 브레이튼 사이클.
   - `cycle_solver._run_sequence()`가 T1 고정점 반복을 수행.
1. `src/cycles/recuperated_brayton.py`
   - `run_cycle()` 제공.
   - 외부 T1 고정점 반복 + 내부 brentq로 Recuperator 열평형(T4)을 맞춤.
1. `src/cycles/bypass_a_brayton.py` *(예정)*
   - Topology A: 추기를 Expander 전단에서 혼합하는 사이클.
   - 추기율 `x` 파라미터 추가.
1. `src/cycles/bypass_b_brayton.py` *(예정)*
   - Topology B: 추기를 교축 후 Expander 후단에서 혼합하는 사이클.

**4. 컴포넌트 계층**
1. `src/components/compressor.py`
   - 등엔트로피 기준 압축기 모델.
1. `src/components/expander.py`
   - 등엔트로피 기준 팽창기 모델.
1. `src/components/hx_aftercooler.py`
   - Aftercooler(End-cooler): UA–LMTD 기반 열방출. 2차측: 물 또는 공기.
1. `src/components/hx_load.py`
   - Load HX: UA–LMTD 기반 열흡수. 2차측: IM-7.
1. `src/components/hx_recuperator.py`
   - Recuperator: UA–LMTD 기반 열교환(Hot/Cold 스트림 동시 계산).
   - *(예정)* Hot/Cold 양측 유량 독립 지정 지원 (bypass 사이클에서 불균형 발생).
1. `src/components/hx_ua_lmtd.py`
   - UA 스케일링과 counter-flow LMTD solver 제공.
1. `src/components/splitter.py` *(예정)*
   - 1 스트림 → N 스트림 분기. 질량 보존: `ṁᵢ = xᵢ · ṁ_total`.
1. `src/components/mixer.py` *(예정)*
   - N 스트림 → 1 스트림 혼합. 에너지 균형: `h_mix = Σ(ṁᵢ·hᵢ) / Σṁᵢ`.
1. `src/components/throttle.py` *(예정, Topology B용)*
   - 등엔탈피 교축: `h_out = h_in`, `P_out` 지정.

**5. 물성/데이터 모델**
1. `src/properties/__init__.py`
   - CoolProp 기반 상태 계산 래퍼.
   - `ThermodynamicState`, `ComponentResult` 데이터 클래스 정의.
1. `src/properties/im7_properties.py`
   - IM-7 액체 물성(테이블 기반, CSV 로드).
1. `src/properties/im7_liquid_properties.csv`
   - IM-7 물성 테이블.

**6. 데이터 계약(핵심 타입)**
1. `ThermodynamicState`
   - 상태: `T`, `P`, `h`, `s`, `fluid`, `label`.
1. `ComponentResult`
   - 출력: `state_out`, `W_dot`, `Q_dot`, `label`.
1. 부호 규약
   - `W_dot > 0`: 시스템이 일을 소비(컴프레서)
   - `W_dot < 0`: 시스템이 일을 생산(터빈)
   - `Q_dot > 0`: 시스템이 열을 흡수(Load HX)
   - `Q_dot < 0`: 시스템이 열을 방출(Aftercooler)

**7. 디렉터리 구조 요약**
```
airHP/
  configs/
    simple_baseline.yaml
    recuperated_baseline.yaml
    bypass_a_baseline.yaml          (예정)
    bypass_b_baseline.yaml          (예정)
  docs/
    modeling_guide.md
    todo_list.md
  src/
    cycle_solver.py
    cycles/
      simple_brayton.py
      recuperated_brayton.py
      bypass_a_brayton.py           (예정)
      bypass_b_brayton.py           (예정)
    components/
      compressor.py
      expander.py
      hx_aftercooler.py
      hx_load.py
      hx_recuperator.py
      hx_ua_lmtd.py
      splitter.py                   (예정)
      mixer.py                      (예정)
      throttle.py                   (예정, Topology B용)
    properties/
      __init__.py
      im7_properties.py
      im7_liquid_properties.csv
  main.py
  visualize.py
  results/  (실행 후 생성)
```

**8. 결과 산출물**
1. `results/<run>/state_points.csv`
   - 상태점별 T, P, h, s.
1. `results/<run>/performance.csv`
   - COP, Q_cold, W_net 등 성능 지표.
1. `results/<run>/cycle_Ts.png`
   - T–s 다이어그램.
1. `results/<run>/cycle_Ph.png`
   - P–h 다이어그램.
1. `results/<run>/cop_vs_rp.png`, `cop_vs_rp.csv`
   - 압력비 스윕 결과.
1. `results/<run>/perf_vs_bleed.png`, `perf_vs_bleed.csv` *(예정)*
   - 추기율(x) 스윕 결과: COP, Q_cold, T_expander_outlet vs. x.
