# rotate/flip — 픽셀 공통 좌표식 발견 (coloring만) 설계

- 날짜: 2026-07-25
- 브랜치: seokki-refactor (refactor4 기반, 코드는 `arbor/` 하위)
- 상태: 설계 확정 대기(사용자 검토 전)

## 1. 목표

`rotate`·`flip` 데이터셋을, move 와 **같은 원리**(픽셀 대응 + 공통 좌표식 탐색·검증)로, **`coloring` DSL 하나만** 써서 푼다. 회전·반전·회전축 같은 개념을 **전제하지 않고**, 같은 색 픽셀들의 좌표 변화에서 **하나의 공통 좌표식이 창발**하도록 만든다.

**범위(1차):** **단일 객체** rotate/flip 먼저 (rotate 138/216, flip 572/864 = 4-연결 성분 1개). 2객체(선택적·객체별 변환; 예 `rota000de` 는 color5 불변·color4만 회전)는 대응·선택이 얽혀 **후속으로 연기**.

**move 게이트 불변이 제약:** `arc_human/move` 60/60 은 깨지지 않아야 한다(§7).

## 2. 핵심 원리 (사용자 확정)

- **회전 중심을 먼저 찾지 않는다.** 같은 색 픽셀 대응 `pixel_i: (r_i,c_i) → (r_i',c_i')` 들의 좌표차는 제각각이지만, **모두 하나의 좌표식** `r'=F(r,c), c'=G(r,c)` 로 설명됨을 찾는다. 이 식을 편향 없이 순수 심볼 조합으로 찾으면 "축 (p,q) 회전" 같은 관계가 **결과로 창발**한다.
  - 예 (2,2)축 90°: `(2+(r-0),2+(c-0)) → (2+(c-0),2-(r-0))` = 절대좌표로 `r'=C, c'=4-R`. 중심 2는 상수(4=2·2)에 인코딩됨 — 별도로 구하지 않는다.
- **배경/전경을 고르지 않는다** (§1-4, [[no-arbitrary-filters]]: "색0=배경" 금지, "비배경 선택" 불가). 대신 **모든 픽셀을 색으로 그룹핑**해 색별 set 을 매핑한다. **균일 배경색은 어떤 좌표 매핑에도 자동 불변**(배경→배경)이라 식을 제약하는 건 구별색 셀뿐. 배경 선택이 필요 없다.
- **대응은 가설이다.** 한 색의 셀이 k 개면 입력↔출력 대응은 최대 **k! 가지 가설**(단색 4칸=4!, 전색상이 4칸=1가지). 여러 가설 중 **매핑된 모든 픽셀이 하나의 공통 좌표식을 따르는** 가설이 정답. 이 "공통 식" 제약이 모호성을 해소한다.

## 3. 현재 구현과의 간극 (왜 지금은 안 되나 — 탐색 결과)

- **대응 벽:** move 는 객체를 **정확한 평행이동 shape 일치**(`arbor/procedural_memory/operators/compress.py:120` `_norm_shape`)로만 대응 → 회전/반전 도형은 대응조차 안 됨.
- **식 벽:** 좌표식 탐색(`arbor/reasoning/antiunify.py` `_axis_matches`, `_gen_exprs`, `_COORD_TEMPLATES`)의 원자 `_ATOM_NAMES`(=`H,W,r0,c0,h,w,ar,ac,0..5`)에 **per-pixel `r,c` 가 없고**, 객체 **anchor 하나**에 대해 **축 독립**으로만 탐색 → `r'=F(r,c)`(r,c 혼합) 표현 불가, 셀별 변환 불가.
- **coloring/pixels_of 는 손댈 필요 없음** — `coloring`(`arbor/procedural_memory/dsl/transformation/__init__.py:13`)은 이미 셀 하나씩 재채색, `pixels_of`(`arbor/procedural_memory/dsl/util/__init__.py:40`)는 이미 픽셀 나열. 좌표를 만드는 **탐색부**만 자란다.

## 4. 설계 (단일 run·resolve 증분 확장)

### 4.1 원자·탐색공간 (primitive만)
- 원자: per-pixel **`r, c`**(픽셀 자기 절대좌표) + `H, W` + 상수 + `{+, -, *}`. **`dr,dc`(파생)·`r0,c0`(객체 bbox) 안 씀.**
- 후보 = `(row_expr, col_expr)` 쌍, 각 expr 은 위 원자의 조합(깊이 제한). **축 교차 허용** — row_expr 이 `c` 를, col_expr 이 `r` 를 쓸 수 있다(회전의 본질).
- 상수 범위: 중심 인코딩 상수가 grid 크기만큼 커질 수 있음 → 리터럴 확장 또는 `H,W` 파생으로 표현(§8 논점).

### 4.2 대응·검증 (색별 set 매핑)
1. 입력/출력 픽셀을 **색으로 그룹핑**(색 = primitive property).
2. 후보 `(F,G)` 를 각 색의 **입력 셀 집합**에 적용 → 예측 좌표 집합.
3. 예측 집합 == 그 색의 **출력 셀 집합**(set 일치)인가? — 겹침 셀 포함, **diff 아님**(단색 겹침 함정 회피).
4. **모든 색·모든 train 쌍**에 대해 같은 `(F,G)` 성립해야 생존.
5. 실현: 개념적으로는 "k! 대응 가설 중 공통 식을 따르는 것"이나, 효율 실현은 **식 공간 탐색 → set 일치 검증**(각 식이 대응을 암묵 결정, k! 열거 회피). 작은 객체는 대응 직접 열거도 가능(§8). 시도·기각 후보가 트레이스에 남아야 함(§1-5).

### 4.3 통합 (resolve additive)
- `resolve`(`arbor/procedural_memory/operators/resolve.py`)/`antiunify.py` 의 좌표 탐색을 **확장**: 기존 평행이동/anchor 후보 **+ 새 per-pixel `(F,G)` 후보**를 함께 생성→train 검증→**이기는 것 채택**.
- move 는 평행이동이 이겨 그대로 → **60/60 불변**. rotate/flip 은 per-pixel 식이 이김. **새 operator/run 없음**(§1-6).
- 대응 게이트: 단일 객체는 대응 자명(그 색/성분)이라 `_norm_shape` 평행이동-일치 요구를 이 경로에선 우회.

### 4.4 물질화·적용
- 찾은 `(F,G)` 로 예측 셀마다 `coloring` (지우기+칠하기), move 와 동일 물질화 경로. `apply_solution`(`apply_solution.py`)이 test 입력에 `execute`.

## 5. 데이터 근거
- rotate 216·flip 864 태스크, **입출력 차원 절대 불변**(제자리 변환). 성분 최대 2, 대부분 1.
- 대부분 다색(rotate 165/216, flip 655/864) → 색이 대응 제약(쉬운 축). 단색도 상당수(rotate 51, flip 209) → 색 무용, **공통 식 set-매핑이 전부 해결**.

## 6. 하네스 부합 (자가검증)
- **탐색이 보인다**: generate `(F,G)` → apply → set-compare → verify. 시도·기각 후보가 트레이스에(§1-5, §2-5).
- **손코딩 0**: 회전행렬·`dr→dc` 지름길 없이 primitive `r,c,H,W,±,*` 에서 식을 발견(§1-3, §4-1). 축·회전은 창발.
- **임의 필터 0**: "색0=배경"·"비배경 선택" 안 함(§1-4). 색 그룹핑 + 균일배경 자동불변.
- **단일 run**: `ArborAgent.run` 안, `resolve` 확장. 새 run/operator/DSL 없음(§1-6, §1-1).
- **coloring만**: 변환 DSL은 동결 `coloring` 하나.

## 7. 검증 / 성공 판정
- **move 60/60 불변** (주 게이트) — resolve additive 라 평행이동 경로 무변, 재현 확인.
- **rotate/flip 단일객체 태스크 신규 해결 > 0** (현재 사실상 0). 정답률 극대화가 목표가 아니라 **원리가 도는 것**이 목표(부분 성공 허용).
- 트레이스: 서로 다른 태스크가 서로 다른 `(F,G)`·시도수를 낳는다(§2-4). 근거(찾은 식·기각 후보)가 WM/대시보드에 남는다.
- **비회귀**: 기존 objc·easy 게이트 및 import 스모크 무변.

## 8. 미해결 구현 논점 (plan 에서 확정)
- **상수 범위/표현**: 중심 인코딩 상수를 리터럴로 넓힐지, `H,W`·객체 span 파생으로 표현할지 (탐색공간 폭발 관리).
- **효율 실현**: 식-공간 탐색+set일치 vs 소규모 대응 직접 열거(k!) — 폭발 방지 상한·로그.
- **탐색공간 폭**: `_gen_exprs` 깊이·원자 추가로 후보수가 급증 → 상한·가지치기·결정적 정렬(§2-6).
- **hook 위치**: `antiunify.py`(`_gen_exprs`/`_axis_matches` per-pixel 확장) + `resolve.py` 후보 병합 지점 정확히.
- **legibility**: 찾은 `(F,G)` 를 `중심+offset` 형태로 재표현해 "축 (p,q) 회전" 관계를 WM/대시보드에 남기기.

---

## 9. 스파이크 결과 (2026-07-25) — 접근 확정: 자유 심볼 → **색별 D4 affine**

Task1 스파이크(scratchpad)로 실데이터 검증한 결론. **자유 심볼 per-pixel 탐색은 폐기**한다:
- 자유 심볼 brute-force 는 (a) **연산 벽**(ops=3 = 축당 540만 식, 수십 분), (b) **과적합**(소형 객체·train 2쌍에 수천 식이 적합, top1 test정답 8~20% ≪ 천장 40%), (c) `//` 등 필수 연산 누락 시 중심 `(r0+r1)//2` 표현 불가 — 관리 난망.
- **rotate/flip/move 는 전부 affine 강체·반사 변환**: `(r,c)→(a·r+b·c, d·r+f·c)+평행이동`, `a,b,d,f∈{-1,0,1}` 의 유효 조합 = **D4 8종**(id·rot90/180/270·flipV/H·transpose·antitr). 이 **선형계수 공간을 직접 exhaustive** 하면 0.07초/216태스크. (회전·축은 창발; 계수 탐색이라 "회전" 하드코딩 아님.)
- **색별 분해가 열쇠**: 비배경을 **색으로 그룹핑**, 각 색 셀집합 → 같은 색 출력에 **자기 D4+평행이동**(그대로=id 포함) 매핑, 색보존 set 일치 검증. 배경 가정 없음.
  - 커버리지(천장, train 일관 D4 존재): **rotate 90%(195/216), flip 88%(762/864)**. global(전체1변환) 50% + 색별 38% + 성분별 3%.
  - **단일객체 실패(구 원인)** = 사실 "위장된 다객체"(한 색 회전·다른 색 그대로) → 색별 D4 가 흡수. 진짜 비-D4 는 rotate 9·flip 46(단일객체의 ~7%).
  - **다객체** = 색이 달라 색별 D4 로 대부분 커버. 남는 소수는 성분 병합/분리.
  - 남은 neither(rotate 10%·flip 12%) = 비-D4/재채색 = **데이터 오류(사용자 후속 수정)** 또는 범위 밖.

### 확정 통합 설계 (색별 D4, resolve additive)
1. 비배경 픽셀을 **색으로 그룹핑**(§1-4 준수: 배경 미선택).
2. 각 색 그룹에 대해 **D4 8종 × placement** 를 generate → 그 색 입력셀에 apply → 같은 색 출력셀과 **set 일치**로 verify. 전 train 쌍 공통 D4 채택.
3. **placement 규칙**(test 배치): in-place 변환이므로 그룹 bbox 앵커(center 또는 top-left) 고정 — train 으로 어느 앵커가 일관인지 판정 후 test 에 적용. (§8 잔여논점 해소.)
4. `resolve` **additive**: 기존 평행이동 후보 + 색별 D4 후보를 함께 verify → 이기는 것. move 는 id+평행이동이 이겨 **60/60 불변**.
5. 물질화: 예측 셀마다 `coloring`(지우기+칠하기). `apply_solution` 이 test 실행.
6. 원자/탐색: `antiunify.py` 에 D4 선형계수(a,b,d,f) 탐색 + placement + 색그룹 루프. 단일 run.

**성공 판정(1차 통합):** move 60/60 불변 · rotate/flip 신규 해결 다수(>0, 목표 수십%) · 트레이스에 색별 D4·기각 후보 잔존 · 결정적.

## 9. 범위 밖 (하지 않음)
- **2객체 태스크**(선택적·객체별 변환) — 후속 slice.
- 전체-grid vs 객체상대 프레이밍 논쟁 — 단일객체에선 무의미(식이 좌표를 직접 줌).
- 모든 rotate/flip 태스크 정답 보장 — 부분 성공으로 원리 검증.
- move 경로 자체 재작성 — additive만.
- 새 operator/DSL/property/run 신설 — 필요 시 §5 절차로 별도 승인.

---

## 10. 정정 + 1차 통합 완료 (2026-07-25)

**§9 의 "색별 D4" 는 우회로였다 — 정정한다.** D4 8종을 직접 열거하면 변환 *종류*는 빠르게 찾지만
**placement(변환된 객체가 test 에서 어디 놓이나)** 를 input 기반 앵커(tl/br/center)로 못 정해 **실제 test 정답 ~0%**.
반면 **심볼 좌표식 탐색**(원자에 객체 bbox `r0,c0,r1,c1,h,w` 포함, 연산 `//` 포함, 일반성 tier)은 **placement 를
식 자체에 학습**(예 flip `c'=(c0+c1)-c`, 회전 `r'=c-c0`)해 test 에 일반화된다. → **§4 의 원래 방향(심볼탐색)이 옳았다.**

**확정 구현:** `arbor/reasoning/transform.py` (`solve_by_transform(train, test_input)`), 원자
`{r,c,r0,c0,r1,c1,h,w,H,W}` + 연산 `{+,-,*,//}` ≤2, 색보존 set 검증, 일반성 tier.

**1차 통합(additive fallback):** `arbor/agent.py::ArborAgent.run` 끝에서 표준경로가 정답 attempt 를 못 내면
`solve_by_transform` 을 시도해 attempt 추가. 탐색은 train 만(§P5), 채점은 최종 test 대조.

**실측 게이트(축소 clean 데이터):** move **60/60 불변**(fallback 미발동) · flip **14/24(58%)** · rotate **9/36(25%)**.

**1차 한계(후속):** (a) figure/ground=최빈색 휴리스틱(→ spelke/bounded 로 principled 화, §no-arbitrary-filters).
(b) 다색 객체 검출 미해결. (c) 탐색 ~5s/태스크(원자·연산 캐싱/가지치기로 최적화). (d) fallback 이 SOAR
operator 루프 밖(→ 후속에 resolve/operator 로 내재화, §1-1 은 §5 절차). (e) rotate 25% (90° disambiguation 개선 여지).

---

## 11. 완전 해결 (2026-07-26) — 배치 피벗 + 객체선택변환

데이터 재작성(06:01) 후 현재 clean 데이터 기준. 실패를 두 부류로 진단하고 각각 해결:

### 부류 1 — 배치(placement) 피벗: centroid → **train-검증 bbox중심**
`solve_by_linear` 이 test 피벗을 객체 centroid 로 *추측*해 1칸 오차. 수정: 피벗 규칙을 **train 정확재현으로
검증**(`_verified_pivot_rule`)해 살아남은 규칙만 test 에 적용. 강체변환 불변점 = **bbox중심**(min+max)이
우선(스파이크로 train·test 전부 정확재현 확인). generate-and-test(§1-3 준수). → rotate 24→26, 회귀 0.

### 부류 2 — 객체선택변환: 색-varying 다객체
색이 쌍마다 바뀌어 색별 exact 매칭 불가. `object_transform_candidates`:
1. **대응**: pair 내 in↔out 성분을 `(색 COMM ∧ area COMM)` greedy 로 잇는다(shape/pos DIFF 여도 = 부분일치).
2. **mover 식별**: 대응쌍 중 shape 바뀐 1개 = mover(제자리 D4), 나머지 정지.
3. **선택 규칙**: mover 를 지목하는 **불변 property**(색 또는 area 가 train 쌍 전체에서 상수)를 structure
   mapping 으로 도출(area 우선). test 객체를 그 규칙으로 선택.
4. **transform**: 공통 D4(교집합) + train-검증 피벗을 제자리 적용.
5. **중의성**: 공통 D4 여럿·규칙 여럿·후보객체 여럿이면 **후보 ≤3 생성**(객체 라운드로빈), attempt 로 제출
   (any-correct; §P5 탐색은 train, 판정은 최종 채점). rota000s(공통D4 2), flip000u(규칙 2), rota00ai(후보객체 2).

**최종 게이트(현재 clean 데이터):** move **60/60 불변** · rotate **36/36** · flip **24/24**. 결정적.

**주의(운영):** program_report 리포트 경로는 `run_solve(use_cache=True)` 이고 캐시 키가 task 내용 해시뿐이라
**솔버 로직을 바꾸면 캐시가 낡는다**. 리포트 재생성 전 `clear_cache()` 필수(안 하면 옛 결과 표시).

---

## 12. 오프셋 형식 재구성 (2026-07-26) — 축·2배·소수점 제거

사용자 통찰: **소수점(/2)·2배좌표·피벗은 변환을 "회전축(고정점)"으로 표현할 때만 생기는 부산물**이다.
픽셀 이동식을 오프셋 형식으로 다루면 전부 정수다.

**핵심 사실:** 픽셀 대응에서 직접 읽는 오프셋 `(dr,dc)`는 **항상 정수**(비정사각 mover 포함 실측 확인).
`/2`는 그 오프셋을 고정점 `p=(I−M)⁻¹·offset` 으로 역표현할 때만 나온다 — det(I−M)로 나누므로 반 칸 가능.

**재구성:** `_pivots2`·`_pivot_named`·`_PIVOT_ORDER`·`_verified_pivot_rule`·`_apply_pivot`(2배좌표 machinery)를
**전부 삭제**하고 `_place_inplace(cells, M)` 하나로:
- M(D4 선형부) 적용 → **bbox중심 보존**하도록 정수 평행이동. 오프셋 = `((r0+r1)−(tr0+tr1))//2` 등.
- 반 칸 이동 필요(`num % 2 != 0`, 예 h−w 홀수)면 **격자 미적중 → None 기각**(사용자 규약).
- 소수점·피벗·2배좌표·축 언어 없음. 이동식 `(r,c)→(a·r+b·c+e, d·r+f·c+g)` 의 e,g 를 '중심 보존' 으로 결정.

**축은 유도만:** 회전축(점)·대칭축(선)은 식의 고정집합 `(r,c)=변환(r,c)` 를 풀어 **역산**(det≠0→점, det=0→선).
반 칸 축(예 세로 거울 `c=15/2`, 7·8칸 사이)도 기하학적으로 실재하며, *적용*엔 불필요하고 *해석*에만 쓴다.

**h−w 홀수 확장:** 제자리(축=객체중심)면 반 칸 → 기각. 축이 **입력의 다른 근거**(마커·타 객체·격자선)로
지정되면 오프셋이 그 축을 인코딩해 정수 적중 가능 — 후속 자유회전 slice 의 문.

**게이트(재구성 후, HASHSEED 무관 결정적):** move 60/60 · rotate 36/36 · flip 24/24. 현행 커버와 완전 동일.
