# airHP Code Architecture

이 문서는 `d:\workPy\airHP` 폴더의 실제 구현을 기준으로 코드 구조와 데이터 흐름을 요약합니다.

**Code Architecture**

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

**4. 컴포넌트 계층**
1. `src/components/compressor.py`  
   - 등엔트로피 기준 압축기 모델.
1. `src/components/turbine.py`  
   - 등엔트로피 기준 터빈 모델.
1. `src/components/hx_heat_rejection.py`  
   - Aftercooler: UA–LMTD 기반 열방출.
1. `src/components/hx_heat_absorption.py`  
   - Load HX: UA–LMTD 기반 열흡수.
1. `src/components/hx_recuperator.py`  
   - Recuperator: UA–LMTD 기반 열교환(Hot/Cold 스트림 동시 계산).
1. `src/components/hx_ua_lmtd.py`  
   - UA 스케일링과 counter-flow LMTD solver 제공.
1. `src/components/hx_base.py`  
   - 단순 온도지정형 HX 기본 로직(현재는 직접 호출되지 않음).

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
  docs/
    modeling_guide.md
    todo_list.md
  src/
    cycle_solver.py
    cycles/
      simple_brayton.py
      recuperated_brayton.py
    components/
      compressor.py
      turbine.py
      hx_base.py
      hx_heat_rejection.py
      hx_heat_absorption.py
      hx_recuperator.py
      hx_ua_lmtd.py
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

## Update: Q_load-Based Load HX (Recuperated)
- Recuperated cycle now computes Load HX outlet (State 6) from `hx_load.Q_load`.
- `hx_load.T_outlet` is ignored in recuperated mode.
- Baseline: `hx_load.Q_load = 5000 W` in `configs/recuperated_baseline.yaml`.
