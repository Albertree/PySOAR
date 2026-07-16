# move 추상화 — pixel→object 그룹핑 탐색 + 대응-Δ 재표현 (설계)

> **목표(사용자 승인, 2026-07-17):** `arc_human/move` 전체(M2+M3+M4)를 푸는 능력. 단 harness §1-1/§2-4/§5
> 준수 — 고정 시나리오가 아니라 **규칙에 의해 활성되는 탐색**으로. 접근 = **A**(기존 `compress` 확장 +
> `resolve_cellset` 부활, dormant blob/cellset 머신 재사용).
>
> **이 스펙의 범위 = Milestone M‑1** (단일 다세포 객체 이동, M2 클래스). 선택(selection, M3/M4)은 **M‑2**로
> 분해 — 각 milestone 은 자체 spec→plan→implement. 성공 판정은 §7.

---

## 0. 배경 진단 (60문제 실측, 2026-07-17)

`arc_human/move` 60문제 solve 결과 **7/60 (11%)** 만 풀림 — M1(1×1 단일객체) 6개 전부 + M4 우연 1개.
근본 원인 3중 우회:

1. **정답 경로 `object_move` 미구현** (REFACTOR_PLAN §빈 슬롯). move 는 object 대응이 `{coordinate:DIFF,
   color:COMM}` 인데 이를 소비하는 operator 가 없어 **전부 PIXEL 잔여로 하강**.
2. **차선 머신 `compress→blob→resolve_cellset` 도달 불가.** move 는 grid 로 감싸져(`set_grid_size(KEEP) ∘
   set_grid_color(KEEP) ∘ set_grid_contents(pixel잔여)`) 저장되는데, `compressible()`/`compress` 는 **flat
   pixel program 만 파싱**한다 → `parse_program(grid_src)=None` → `needs-compress` 미설정. **60문제 전부
   `grid>pixel`, blob 경로 도달 0/60.** (직접 대조: 같은 잔여가 flat 이면 `compressible=True`.)
3. **현 유일 경로(pixel 잔여 + 픽셀별 좌표식)는 1×1 만 감당.** 다세포 객체를 낱개 픽셀로 다뤄 resolve 가
   픽셀마다 좌표식을 **독립** 도출 → 강체 평행이동을 못 잡고 2 train 에 과적합.

실패 모드 분포: **길이불일치로 generalize 중단 30 · 오답 제출 17 · resolve 실패 중단 6 · 풀림 7.**
`generalized=failed` 를 소비하는 규칙이 없어, 막히면 state-no-change impasse → 최하층이라 자식 없음 →
**답 제출 없이 종료(halt).** (60 중 36 halt.)

---

## 1. 핵심 아이디어

move 된 object 는 **object 대응(`_fg_correspondence`)에서 이미 input↔output 로 매핑**되어 있다("객체가 매핑
되는가"는 이미 계산됨). 없는 것은 그 `coordinate:DIFF` 를 **완화(relax)**해 좌표차를 하나의 이동으로 재표현하는
도구다. 이를 **abstraction 단계에서 pixel 을 object 로 되묶는 탐색**으로 구현한다:

- **탐색 공간은 이미 축소돼 있다** — pair program 에 등장하는 좌표 = **변화가 있는 픽셀들(잔여)**.
- 각 잔여 픽셀 = PIXEL 노드(`{color, coordinate}` + OBJECT 소속(membership) 관계).
- **grouping = 잔여 픽셀의 property/relation 비교로 압축** (harness §2-1/§2-2):
  - **object-membership**: 이 좌표 집합이 input_grid(및 output_grid)의 한 OBJECT 에 소속되는가 → 그 객체로 묶음.
  - **color**: 같은 (칠해질) 색인가 → 색으로 묶음.
  - **coordinate 는 생략** — 그것이 곧 이동이 설명할 **DIFF** 이므로 grouping 기준으로 쓰지 않는다.
- 묶인 cellset 이 input object O 에 대응하고, 매핑된 output object O′ 이 `coordinate` 만 다르면 →
  **`arrive = (O + Δ)` 로 재표현**, `vacate = O@원위치 → 배경색`, `arrive → O의 색`(coloring 이 채움).

---

## 2. Milestone M‑1 설계 (M2: 단일 다세포 객체 이동)

### 2.1 Trigger & reachability
- `generalize` ([procedural_memory/operators/generalize.py](../../../procedural_memory/operators/generalize.py)):
  `antiunify_ast` 가 `_antiunify_ast_grid` 경로에서 **inner contents(pixel) 의 op 수 불일치**로 None 을 내면,
  그 inner 불일치를 판정(각 pair 의 `set_grid_contents` inner body 길이 비교)해 **`needs-compress` 설정**.
  → grid>pixel move 경로가 이제 `compress` 에 도달. flat-pixel 태스크는 기존 경로 그대로(무변화).
- `compress` 는 **inner contents 잔여**를 blob body 로 재작성하되 **grid 래퍼 유지**(`set_grid_contents(blob…)`).
- `program_ast._antiunify_ast_grid`: `contents` leaf 가 전 pair 에서 **blob(program) 이면** 기존 pixel 분기를
  mirror 해 `_antiunify_ast_blob` 로 재귀(현재 pixel 만 처리 → blob 추가).

### 2.2 그룹핑 = 규칙 활성 탐색 (본체)
`compress` 를 단일 고정 술어에서 **cursor 기반 그룹핑 가설 탐색**으로 (기존 `pair-idx`/3-attempt 와 동일 패턴):

- 상태에 **`grouping-idx`** cursor. `compress` 는 **predicate[grouping-idx]** 로 잔여 픽셀을 묶는다:
  1. **object-membership(input)** — `objects_of(G0)` 의 한 객체에 속한 잔여 셀 → 한 cellset.
  2. **object-membership(output)** — `objects_of(G1)` 의 한 객체에 속한 잔여 셀 → 한 cellset. *(G1 은 pair
     program/그룹핑 도출·검증에만; solution 엔 안 씀 = P5.)*
  3. **color** — 같은 칠할 색 잔여 셀 → 한 cellset.
- 각 그룹핑 후 정상 체인 재발화: `generalize`(blob anti-unify) → `resolve`. **수용 게이트 = resolve 완전 성공**
  (모든 slot 이 train-검증된 식을 얻음). 실패면 규칙이 `grouping-idx`++ 후 `compress` 재발화. 시도·기각 그룹핑은
  WM/트레이스에 남는다(§1-5). — 특권 술어 없음; **train 검증을 통과한 것**이 승자(§2-4: 태스크별 상이한 술어/step).

### 2.3 대응-Δ 재표현 (`resolve_cellset` 부활 = 정직한 object_move)
- cellset 이 input object O(membership COMM)에 대응하고 매핑된 O′ 이 `coordinate` 만 다르면:
  **`arrive = O + Δ`**, Δ 는 기존 좌표식 문법(`_gen_exprs`/`_obj_atoms`, `{H,W,r0,c0,h,w,anchor,const}` ≤2연산)
  을 **객체 앵커에 1회**(강체: 객체 전체 1 Δ) 적용해 도출. 이로써 **relative(앵커=r0+k)·absolute(앵커=const)·
  corner(앵커=H−h)** 가 한 train-검증 탐색으로 통합(현 per-pixel 과적합 해소).
- 두 잔여 cellset 매핑: `vacate = O@source → 배경색`(배경 = grid 배경-객체 색, train 검증 상수/`color@selector`;
  `0=bg` 가정 없음), `arrive = (O+Δ) → O의 색`(move 간 COMM).
- **P5:** `TASK.solution` 의 모든 항은 **G0** 유래(소스 객체 = input-only 선택자 — M2 는 "그 객체"; M3/M4 선택은
  M‑2). `objects_of(G1)`/대응은 **train 도출·검증에만**, solution 에 방출 금지.
- 소스 객체 선택자: M‑1(M2)은 단일 mono 객체라 자명. **M‑2 에서** 대응의 `coordinate:DIFF` = mover 판별 +
  mover 들의 input-side property/relational-profile anti-unify 로 test 일반화(색/크기/모양).

### 2.4 아티팩트 & 대시보드 (§2-5)
- `PAIR.program` = `grid>blob`(cellset inner body). `TASK.solution` = cellset slot → `선택자 + Δ`.
- move 리포트/대시보드([debugger/reports/program_viewer.py](../../../debugger/reports/program_viewer.py)):
  **선택된 그룹핑 술어 · 시도/기각 그룹핑 · resolved Δ · 기각된 Δ 후보**를 노출. 승자만이 아니라 탐색이 보여야 함.

---

## 3. 수용 판정 (Acceptance) & 행동보존
- **오라클:** `tests/verify_refactor.py` 골든 — easy a–h·made000b 불변(회귀 0). M2 신규 풀림은 재기준화.
- **M‑1 done =** M2 클래스가 grouping→blob→대응-Δ 경로로 풀림 + 그룹핑·Δ 탐색이 트레이스에 보임 + M1/easy 동일 +
  M3/M4 는 여전히 **정직하게 halt**(선택 미구현 = M‑2). 모든 태스크가 같은 step 수면 실패 신호(§2-4).

## 4. 신규/변경 표면 (§5 — 의식적 승인 대상)
- **변경:** `compress`(술어-cursor 탐색 + grid-wrap 도달), `generalize`(inner 불일치→needs-compress),
  `resolve_cellset`(강체 앵커-Δ, 대응 유래), `program_ast._antiunify_ast_grid`(contents=blob 재귀).
- **신규 규칙:** `grouping-idx` cursor 순회(propose*compress 가 `needs-compress ∨ resolve 미완∧그룹핑 남음`에 발화).
- **DSL 동결 유지:** 새 transformation DSL 없음(`make_grid`/`coloring` 그대로). 새 property 없음 — 기존 PIXEL
  `{color,coordinate}` + OBJECT membership + compare COMM/DIFF 재사용.

## 5. harness §7 체크 (자가검증)
- [x] 새 operator/DSL/property 임의 생성? — 새 transformation DSL·property 없음. 변경 operator 는 §5 절차로 승인.
- [x] 정답 최적변환 손박기? — Δ·그룹핑·색 전부 **후보 생성→train 적용→대조→기각/생존** 탐색. 시도·기각이 트레이스/
      대시보드에 남음(§1-3/§1-5).
- [x] 정보는 ARCKG property? — PIXEL `{color,coordinate}`·OBJECT membership·`objects_of`.
- [x] 근거는 compare COMM/DIFF? — 대응(`_fg_correspondence`), 그룹핑=property COMM(color/membership), 이동=DIFF.
- [x] program(pair)/solution(task) 구분? — pair=grid>blob(G1 사용 가능), solution=G0-only(P5).
- [x] 태스크별 상이한 탐색/step? — 그룹핑 술어·Δ 태스크별 상이.
- [x] 막히면 정직한 impasse? — 선택 미구현 M3/M4 는 halt 유지(몰래 안 메움).
- [x] 대시보드 반영? — §2.4.

## 6. Milestone 분해 (전체-move 목표 하에서)
- **M‑1 (이 스펙):** reachability + object/color 그룹핑 탐색 + 대응-Δ 재표현 → **M2** 풀림.
- **M‑2:** 객체 **선택**(mover = `coordinate:DIFF` 대응; test 일반화 = mover 들의 input-side property/relational
  profile anti-unify) → **M3(색)** → **M4(색/크기/모양)**. 자체 spec→plan→implement.
