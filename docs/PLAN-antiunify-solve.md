# 구현 계획 — anti-unification 통합으로 easy000c–h 풀기 (Approach A)

> **승인됨**(하네스 §7, 2026-07-14). wiki `arbor-operators.md`에 설계된 미구현 operator
> **generalize · resolve · submit-solution 경로** 3개를 메인 flow에 추가. per-pair program을
> anti-unify → 변수 resolve(탐색+검증) → TASK.solution → submit(최대 3회). 매 스텝 대시보드에.

## Ground truth (설계 근거)
easy000c: 픽셀이 **(5,5)=우하단으로 이동, 색 유지**. train (1,1,c2)→(5,5,c2) · (1,4,c1)→(5,5,c1); test (4,2,c4)→(5,5,c4). 전부 6x6.
현재 flow가 이미 만드는 per-pair program (WME `PAIR.property ^program <code>`):
```
in_px = pixels_of(input_grid); P0 = in_px[SRC]; P1 = in_px[DEST]
tfg0 = input_grid
tfg1 = apply_DSL(tfg0, coloring, P0.coord, 0)      # erase source
tfg2 = apply_DSL(tfg1, coloring, P1.coord, COLOR)  # paint dest
output_grid = tfg2
```
P0: SRC=7,DEST=35,COLOR=2 · P1: SRC=10,DEST=35,COLOR=1 · Pa: `{}`(공백).
anti-unify(P0,P1): **COMM**=골격·erase색0·DEST=35 · **DIFF**=SRC(7/10)·COLOR(2/1).

## 하네스 준수(필수)
- resolve의 좌표/선택식은 **손계산 금지**(§1-3/§4-1): `{const, r0±d, c0±d, H-1, W-1, 0}` 후보 **생성→train 적용→대조→기각→생존**. 시도·기각이 트레이스에 남는다.
- **test 출력을 오라클로 쓰지 않는다**(오프라인 리포트와 결정적 차이): resolve는 **train pair로만** 검증. 살아남은 version space를 submit 3회로 시도.
- 근거는 compare COMM/DIFF에서(§2-2·P4). 매 스텝 WM/대시보드에(§2-5).

## 구조 (아티팩트 · WM 플래그)
- `TASK.solution` = TASK 노드 property WME `(T… ^solution <schema>)`. schema = 골격 코드 + slots `{name: {diff_values, resolved?}}`.
- WM 플래그: `^programs-ready`(≥2 program 물질화 시) · `^generalized`(solution 생성) · `^resolved`(모든 slot 해결) · 기존 `^answer-ready`→`submit`.

## Task 1 — generalize operator
**Files**: `procedural_memory/production_rules/generalize.json`(신규) · `procedural_memory/operators/generalize.py`(신규) · `procedural_memory/operators/__init__.py`(등록) · `arbor/reasoning/antiunify.py`(신규, 파싱·anti-unify 순수 로직).
- **propose**: `^programs-ready yes` ∧ `^generalized <x>`(neg). programs-ready는 `_materialize_pair_programs` 성공 시 세운다(program.py 수정).
- **apply body**: 존재하는 `PAIR.program`(≥2) 파싱 → 라인 정렬 → `compare(prog,prog)`로 COMM/DIFF → DIFF 슬롯 변수화 → `TASK.solution` schema WME + slot별 `(slot ^diff-values [...])` (근거) + `^generalized yes`.
- **antiunify.py**: `parse_program(code)`→구조화 단계 리스트; `antiunify(progs)`→(skeleton, slots{name:[per-pair values]}).
- **검증**: easy000c에서 `T… ^solution` WME 생성 + slots SRC/COLOR 노출. 대시보드 event에 COMM/DIFF 보임.

## Task 2 — resolve operator
**Files**: `procedural_memory/production_rules/resolve.json` · `procedural_memory/operators/resolve.py` · `arbor/reasoning/antiunify.py`(resolve 탐색 추가).
- **propose**: `^generalized yes` ∧ `^resolved <x>`(neg).
- **apply body**: 각 미해결 slot에 대해 **input-derived 후보식 생성**(SRC: fg 픽셀·pixel[k]; COLOR: color_of(fg)·const; DEST(COMM 상수라도 좌표식으로 재도출): `make_cands` r/c축) → **각 train pair G0에 적용→DIFF 값과 대조→기각/생존**(version space) → slot별 `(slot ^resolved <expr>)` + `(slot ^tried [(cand,ok)…])`(근거·시도기록) + version space 저장. 모든 slot 생존식 ≥1 → `^resolved yes`.
- **검증**: SRC→fg픽셀, COLOR→color_of(fg), DEST→{const35, (H-1,W-1)…} version space. 시도·기각이 event에.

## Task 3 — submit-solution 경로
**Files**: `procedural_memory/operators/compose.py` 또는 기존 submit 확장 · `production_rules/`.
- **propose**: `^resolved yes` ∧ `^answer-ready <x>`(neg).
- **apply body**: version space 상위 1개로 `TASK.solution`을 **Pa.G0(test 입력)에 실행**(resolved 식 대입 → coloring 실행) → test 답 격자 → `Pa.property ^program` 채움 + `ag.kg["answer"]=grid` + output-link emit + `^answer-ready yes`. 기존 `propose*submit` 발화 → 채점.
- **3회 시도**: submit 실패(오답) 시 version space 다음 후보로 재-compose (attempt 2,3). `tr.attempts`에 각 시도.
- **검증**: easy000c `correct_attempt` 채워짐(풀림). c–h 동일. a/b 여전히 풀림(상수 경로 유지). i 제외.

## 검증 (acceptance)
- easy000c–h **풀림**(correct_attempt≠None), a/b 풀림 유지, i 미해결 유지.
- 문제별 step 수가 서로 다름(§2-4) — 탐색이 트레이스에 보임(§1-5).
- 대시보드 event/WM에 generalize(COMM/DIFF)·resolve(후보 시도·기각)·submit(3-attempt) 전부 보임(§2-5).
- **golden_steps.json 갱신**: 이번엔 행동을 *의도적으로* 바꿈(풀리게) → step 수 변경이 정상. 정확성(풀림)으로 검증하고 golden 재캡처.
- 새 operator body는 Python leaf이되 **control은 rule**(propose/apply JSON), 탐색이 body 안에 숨지 않도록 후보 시도를 event로 방출.
</content>
