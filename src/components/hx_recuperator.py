"""
components/hx_recuperator.py
─────────────────────────────
리큐퍼레이터: 2-stream 내부 열교환 모델 (향후 확장용).

  현재 미구현 — recuperated_brayton.py 도입 시 활성화.

  입출력:
    run(state_hot_in, state_cold_in, effectiveness, m_dot)
      → tuple[ComponentResult, ComponentResult]

  부호:
    hot side  : Q_dot < 0  (고온 스트림이 열 방출)
    cold side : Q_dot > 0  (저온 스트림이 열 흡수)
    |Q_hot| = |Q_cold|  (이상적 내부 열교환)
"""

raise NotImplementedError(
    "hx_recuperator is not yet implemented. "
    "Activate when recuperated_brayton.py cycle is added."
)
