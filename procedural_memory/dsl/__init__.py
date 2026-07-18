"""
DSL — ARBOR 그리드 풀이 DSL (Slice 1).

두 얼굴:
  · 실행 본체 (procedural) = 이 패키지의 함수들
  · 선언적 명세 (semantic 라이브러리 씨앗) = registry.SPECS

종류:
  · transformation — coloring (동결 원자 하나)
  · property       — pair_count, grid_count, size, color, contents (to_json 노출)
  · util           — pairs_of, grids_of, objects_of, role_of, filter_  (날 것 항해)
  · selection      — select, elements_at  (조건 맞는 요소 찾기; 범위 지정·객체 선택 공용)
  · relation (C)   — compare(두 노드 또는 scope pairwise), verdict  (비교 = 공통점·차이점)
"""

from procedural_memory.dsl.registry import SPECS, spec, body

# 서브모듈 import = @dsl 데코레이터 실행 → SPECS 등록
import procedural_memory.dsl.util            # noqa: F401,E402
import procedural_memory.dsl.property        # noqa: F401,E402
import procedural_memory.dsl.transformation  # noqa: F401,E402
import procedural_memory.dsl.selection       # noqa: F401,E402
import procedural_memory.dsl.relation        # noqa: F401,E402

__all__ = ["SPECS", "spec", "body"]
