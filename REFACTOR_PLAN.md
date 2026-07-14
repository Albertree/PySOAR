# PySOAR → ARBOR in-place 모듈화 리팩터 — 설계 + 실행 계획

> **정본(canonical).** flat `arc/` 모놀리스를 **SOAR 인지 아키텍처**로 in-place 재편한다. 규칙은 **JSON 실물**,
> DSL은 **4범주 + 두 얼굴**, 메모리는 **SOAR 4종 의미**로. 근거 = ARBOR_HARNESS.md + /wiki(arbor-modules·
> arbor-soar-memory-mapping·arbor-dsl-taxonomy·arbor-operators·arbor-solve-flow·arbor-skill-loop·
> arbor-execution-trace P1–P7). **행동보존**: 리팩터 전/후 step 수 완전 일치가 acceptance gate.

## 승인된 결정
- **위치**: 현재 PySOAR **in-place** (git 연속) · **ARCKG vendor**(self-contained) · **rule = operator 단위 JSON**.
- **semantic = ARCKG 아님**: ARCKG는 perception(눈)/영속 WM. 진짜 semantic = **DSL 추상 라이브러리**(spec as data, 성장).
- **DSL 두 얼굴**: body→procedural, spec→semantic. 비교·anti-unify는 spec에만 작용.
- **DSL 4범주**: transformation(RHS)=**딱 2개 동결**(make_grid·coloring) / property·util=성장 / relation=**compare 엔진 도출**(카탈로그 아님).
- **규칙 2종**: production rule(operator propose/apply) ≠ activation rule(DSL 선택). 스키마는 `{condition, action}` 보존.
- **operator 레벨 무관**: 레벨=arg. `descend`/`submit`=impasse/goal 사이클 메커니즘(operator 아님).

## 7원리 (모든 모듈이 지켜야 함, arbor-execution-trace)
P1 계층 하강은 필요(막힘)로 · P2 비교는 동일 레벨 · P3 정답엔 이유(값<이유) · P4 이유는 비교결과에서 ·
P5 변수 출처는 G0(test엔 G1 없음) · P6 2개씩 비교 · P7 모든 정보 symbolic dict+JSON.

---

## 목표 구조
```
soar/                       # SOAR CORE (무수정 PSA) — 구 pysoar/: decide·wm·elaborate·preference·production·agent·chunk
arbor/
  perception/               # 눈: symbolic·계층 필터
    arckg/                  #   5계층 노드 (task·pair·grid·object·pixel) [vendored]
    comparison.py           #   compare() 재귀 COMM/DIFF·2차 relation
    nav.py  perception.py   #   arckg 탐색(index/cursor/lca/edge) · 객체검출(objects_of/fg_correspondence)
  operators/                # 일반(레벨 무관) operator 참조 (body는 procedural)
  reasoning/                # leaf 알고리즘 (control은 규칙에)
    compare_engine.py       #   relation 도출 (compare→refine→aggregate)
    program.py              #   PAIR.program (search+verify)
    antiunify.py            #   program들 → TASK.solution
    structure_map.py        #   2차 compare 대응(roles)
    skill.py                #   discover→generalize→reuse [forward slot]
  agent/                    # build_arckg · focus(inject_focus/setup_focus_agent)
  engine/                   # trace/event-stream(debugger 기반) + descent 드라이버 (구 fine_trace)
procedural_memory/          # LTM-절차 (JSON 실물 + Python body)
  production_rules/*.json   #   operator propose/apply = {condition, action} (operator 단위 1파일)
  activation_rules/         #   DSL 선택 규칙 [forward slot]
  operators/*.py            #   operator 실행 body — 이름으로 규칙과 결선
  dsl/                      #   변환 DSL body, 4범주
    transformation/         #     ★ 딱 2개 동결: make_grid.py, coloring.py
    property/  relation/  util/
    registry.py             #   @dsl: body→procedural, spec→semantic (두 얼굴)
  loader.py                 #   JSON 규칙 → 커널 Production (역 _rules_manifest)
semantic_memory/            # LTM-의미 = DSL 추상 라이브러리 (spec as data)
  ontology.json             #   type 온톨로지 · operator spec(signature/arg-schema) · composition grammar
  learned_skills/           #   anti-unify 증착 고차 DSL [forward slot, 지금 빔]
episodic_memory/            # LTM-일화 = 풀이 trace (task별 JSON) [이미 존재]
env/                        # ARC 환경: 문제 제공·채점·3회 제출 (구 environment/dataset/survey/make_tasks)
debugger/                   # 전체흐름 상시 모니터 + 단발 HTML (구 visualizer)
oracle/                     # C++ Soar 차등 오라클 [이미 존재]
legacy/                     # 옛 스택·프로토타입 격리 (보존)
```

## focus_solver.py (1520줄) 분해 맵
| 현재 함수/블록 | → 목적지 |
|---|---|
| `index_arckg`·`_cursor`·`_focus_group`·`_siblings`·`_receipt_leaves`·`_lca`·`_short`·`_edge_name`·`_load_props` | `arbor/perception/nav.py` |
| `_store_receipt`·`_agree`·`_compare2`·`_compare`·`_store_relation` | `arbor/reasoning/compare_engine.py` |
| `_obj_cc`·`objects_of`·`_fg_correspondence` | `arbor/perception/perception.py` |
| `_op_observe`+`_imbalance_goal`+`_build_agenda` | `procedural_memory/operators/observe.py` |
| `_op_compare`+비교 헬퍼(`_wm_vals`·`_compare_pixels`·`_do_compare_kind`·`_score_frac`·`_compare_objects`·`_cross_grids`·`_compare_peers`·`_predict_test_output`) | `procedural_memory/operators/compare.py` |
| `_op_select` | `procedural_memory/operators/select.py` |
| `_op_synthesize`+grid/color search(`_size_expr_search`·`_size_apply`·`_grid_decide`·`_dec`·`_color_map_search`·`_global_recolor_program`·`_colorset`·`_grid_prop_value`·`_grid_property_hypotheses`) | `procedural_memory/operators/synthesize.py` (+ 탐색부 → `arbor/reasoning/program.py`) |
| `_op_hypothesize` | `procedural_memory/operators/hypothesize.py` |
| `_op_coloring`·`_recolor_pending` | `procedural_memory/operators/coloring.py` |
| `_materialize_pair_programs`·`_pixel_residual_program` | `arbor/reasoning/program.py` |
| `_op_verify` | `procedural_memory/operators/verify.py` |
| `_op_set_grid_size`·`_op_set_grid_color` | `procedural_memory/operators/grid_slots.py` |
| `OPERATOR_BODIES` | `procedural_memory/operators/__init__.py` |
| `PRODUCTIONS`+빌더(`_propose`·`_apply`·`_propose_named`·`_apply_state`·`_propose_nonode`)·`OP_DOCS` | **JSON 변환** → `procedural_memory/production_rules/*.json` + `procedural_memory/loader.py` |
| `inject_focus`·`setup_focus_agent` | `arbor/agent/focus.py` |
| `_cycle_tree`·`_dash_data`·`_rules_manifest`·`_safe_dash_data`·`make_dashboard` | `debugger/build.py` |
| `_load_made_and_real`·`_load_survey`·`SURVEY_AGI` | `arbor/env/survey.py` |

## 그 밖 arc/ 파일
`fine_trace.py`→`arbor/engine/trace.py` · `dashboard.py`→`debugger/dashboard.py` · `expr_solver.py`→`procedural_memory/dsl/util/expr.py` · `dsl.py`→`procedural_memory/dsl/` · `thinking_ops.py`·`solve_ops.py`→`procedural_memory/operators/`(활성 확인 후; 아니면 legacy) · `environment.py`·`dataset.py`·`grid.py`·`make_tasks.py`·`make_made_tasks.py`·`memory.py`→`arbor/env/` · `abstraction*.py`·`easy_concepts.py`·`easy_generalize_cd.py`→`arbor/reasoning/`(현행 anti-union 경로 vs 실험 구분) · 리포트/viz(`*_report.py`·`*_viz.py`)→`debugger/reports/` · `solver.py`·`soar_solver.py`·`select_solver.py`·`solve.py`·`relation_solve.py`·`show.py`·`run.py`→`legacy/`

## JSON 규칙 스키마 (operator 단위 1파일)
`procedural_memory/production_rules/observe.json`:
```json
{
  "operator": "observe",
  "doc": "focus 노드의 property 를 ARCKG 에서 읽어 WM 에 적재(관측).",
  "propose": [{
    "name": "propose*observe",
    "conditions": [
      {"id": "<s>", "attr": "type",  "value": "state"},
      {"id": "<s>", "attr": "focus", "value": "<f>"},
      {"id": "<f>", "attr": "seen",  "value": "yes", "negated": true}
    ],
    "actions": [
      {"id": "<s>", "attr": "operator", "value": "<o>", "pref": "+"},
      {"id": "<o>", "attr": "name",     "value": "observe"},
      {"id": "<o>", "attr": "node",     "value": "<f>"}
    ]
  }],
  "apply": [{ "name": "apply*observe", "conditions": [], "actions": [] }]
}
```
- `loader.py`: `production_rules/*.json` 로드 → 커널 `Production` 리스트 + `OP_DOCS`. `apply` body는 `procedural_memory/operators/<op>.py`에서 이름으로 결선.
- 대시보드: `_rules_manifest`(Production→dict round-trip) 제거, **loader가 읽은 JSON을 그대로 전달** → 화면=파일.
- 기존 `procedural_memory/rules.json`(옛 문자열-triple 스키마)은 이 구조화 스키마로 **정본 통일**, `learned_chunks`는 activation/skill forward 슬롯으로 이관.

## DSL 두 얼굴 registry
`@dsl` 데코레이터가 한 DSL을 두 곳에 등록: **body**(호출 가능 함수)→`procedural_memory/dsl/<cat>/`, **spec**(name·in/out type·arg schema·category)→`semantic_memory/ontology.json`. 비교·anti-unify·merge는 **spec에만** 작용. transformation은 `make_grid`·`coloring` 딱 2개로 동결. step-일치를 위해 body 실행은 불변, spec은 additive.

---

## 실행 단계 (각 단계 = 커밋; 각 단계 종료 = step-일치 오라클 통과)

### P0 — 오라클 + 브랜치 [비파괴]
- [ ] 리팩터 브랜치 분기 (`seokki` 기준 `seokki-refactor`).
- [ ] `tests/golden_steps.json` 에 현재 easy_a 9태스크 step 수 캡처 (골든). `python3 arc/focus_solver.py` 산출 n_steps 사용.
- [ ] 검증: 재캡처 시 동일. 커밋.

### P1 — 스캐폴드 + ARCKG vendor [additive, 삭제 없음]
- [ ] `soar/`(=pysoar 재노출), `arbor/{perception,operators,reasoning,agent,engine,env}`, `procedural_memory/{production_rules,operators,dsl,activation_rules}`, `semantic_memory/learned_skills`, `debugger/{reports}`, `legacy/` 패키지 골격 생성(`__init__.py`).
- [ ] `~/Desktop/ARC-solver/ARCKG/*` → `arbor/perception/arckg/` vendor. sys.path 훅 제거(10파일)는 P2에서 결선하며 처리.
- [ ] 검증: `python3 -c "import arbor, soar"` + 기존 진입점 여전히 동작. step-일치. 커밋.

### P2 — focus_solver 분해 [모듈 이동, PRODUCTIONS는 Python 유지]
- [ ] 분해 맵대로 함수 이동 (perception·operators·reasoning·agent·engine·env). 옛 `arc.focus_solver.X` 는 얇은 재노출 shim으로 임시 유지.
- [ ] vendored ARCKG로 import 재결선(외부 sys.path 훅 제거).
- [ ] 검증: **step-일치**(golden). 대시보드 재생성 diff 0. 커밋.

### P3 — production rule → JSON + loader
- [ ] `PRODUCTIONS`·`OP_DOCS` → `production_rules/*.json`(operator 단위). `loader.py` 작성(JSON→Production).
- [ ] 솔버·대시보드가 loader에서 로드. `_rules_manifest` round-trip 제거.
- [ ] `procedural_memory/rules.json` 스키마 통일.
- [ ] 검증: **step-일치** + 대시보드 rules 패널 리팩터 전과 동일. 커밋.

### P4 — DSL 4범주 + 두 얼굴 registry
- [ ] DSL을 `dsl/{transformation,property,relation,util}/`로 분류(transformation=make_grid·coloring 동결). `registry.py`의 `@dsl`가 spec을 `semantic_memory/ontology.json`에 additive 방출.
- [ ] 검증: **step-일치**(body 실행 불변). ontology.json 생성 확인. 커밋.

### P5 — 메모리 의미·visualizer/debugger·legacy·진입점
- [ ] episodic writer 훅 지점 명세(슬롯), semantic library 스캐폴드, `activation_rules/`·`skill.py`·`object_move` 슬롯 문서화(구현 X, 하네스 §7).
- [ ] `debugger/`(dashboard+reports) 정리, 옛 6스택 `legacy/` 격리, `arc/` 재노출 shim 제거.
- [ ] 진입점(`run.py`/`-m debugger.build`)·CLAUDE.md·docs 갱신.
- [ ] 검증: step-일치 + 리포트 재생성 diff 0(설명 가능한 것만). 커밋.

## 검증 (acceptance)
- easy_a 9태스크 step 수 = golden 완전 일치 (매 단계).
- (확장) survey 17태스크 step 일치 = 최종 gate (system_a 방식).
- `focus_dashboard.html` rules 패널이 리팩터 전과 동일.
- 리포트(pixel/obj/program) 재생성 diff 0 또는 설명 가능한 차이만.

## 빈 슬롯 (이번 리팩터 아님, 별도 로드맵 — 하네스 §1-1/§7)
`activation_rules/` 메커니즘 · `semantic/learned_skills/` 성장 · `skill.py`(discover→generalize→reuse) ·
`object_move` 발동규칙(color/coord DIFF를 한 규칙 search로 분기 = Synthesizer) · anti-unify 증착 지점 ·
상시 라이브 debugger 모니터. 각 슬롯은 빈 구조·문서만 두고 구현은 의논 후.
</content>
