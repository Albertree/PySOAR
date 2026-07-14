NOTE.md의 각 메모/요구사항 + 그에 대한 답변·변경 기록.
   (항목 번호는 NOTE.md와 일치. 요구사항 원문을 함께 싣고 그 아래 답변을 둔다.)


Operator Note — 현재 구현된 operator
   (arc/expr_solver.py: OPERATOR_BODIES + PRODUCTIONS)
   각 operator는 propose*X(객체 (<o> ^name X) + acceptable preference (S1 ^operator <o> +))로 제안되고,
   apply*X 규칙이 결과 flag를 o-support로 쓰며, Python body가 ARCKG/DSL 계산을 수행한다(=SOAR RHS function).

   ── 한 operator가 만드는 WME의 support 3분류 (pysoar/elaborate.py: calculate_o_support 기준 검증) ──
   매 operator는 산출 WME가 세 종류로 나뉘고, 지위가 다르다. 확장 시 새 operator도 이 분류로 같이 기록한다.

   (i)  propose*X 산출 = i-support.
        (<o> ^name X) 와 (S1 ^operator <o> +). calculate_o_support 규칙(1): goal에 operator를 제안하는
        instantiation은 i-support. → 제안 조건(propose*X의 LHS)이 깨지는 순간 함께 retract.
        ※ 이것이 apply 단계에서 보이는 "propose*X retract"의 정체 (^observed yes가 서면 propose*observe의
          부정조건 -(S1 ^observed)이 위반 → instantiation 사망 → (O1 ^name observe)·(S1 ^operator O1 +) 제거).

   (o)  apply*X 결과 flag = o-support.
        (S1 ^<result> yes). calculate_o_support 규칙(2·3): 선택된 operator((S1 ^operator <o>))를 LHS에서
        테스트하고 RHS가 state(operator 아닌 id)를 바꾸므로 application → o-support. → 지속(다음 operator가 이걸
        조건으로 발화하고, 사이클이 지나도 안 죽음).

   (b)  Python body가 wm.add로 직접 넣는 WME = 추적 안 됨(현재 진리유지 밖, base/IO-WME처럼 영속).
        elaborator의 engine_added도 instantiation results도 아니라, 어떤 truth-maintenance도 안 받는다.
        지금은 영속이라 사실상 o-support처럼 동작하지만, 엄밀히는 "untracked 직접 변경"이다.
        ⚠ 향후 operator가 *나중에 철회되어야 하는* 중간 WME(예: search의 잠정 가설, select의 후보 표시)를
          만든다면 body의 wm.add로 넣으면 안 되고 production으로 빼서 i-support를 받게 해야 한다. ← 확장 시 핵심.

1. OBSERVE
    ARCKG 계층(task→pair→grid→object)을 WM에 적재한다. 결과 flag: ^observed.
    · (i) (O ^name observe), (S1 ^operator O +)
    · (b) ARCKG 구조: (T ^example …), (T ^test …), (T ^roles …) + roles.* — body가 직접 적재(영속)
    · (o) (S1 ^observed yes)

2. COMPARE
    observe로 드러난 구조에서, target object의 입력 context(좌표·색·others)와 출력(좌표·색·크기·배경)을
    example pair별로 수집해 비교 샘플을 만든다. 이때 ARCKG의 pair/grid/object 노드를 visit하여 로드한다(P1 lazy 하강).
    결과 flag: ^compared.
    · (i) (O ^name compare), (S1 ^operator O +)
    · (b) visit한 pair/grid/object 노드 WME들(lazy load, 영속) — 샘플 자체는 kg(Python dict)에만 둠
    · (o) (S1 ^compared yes)

3. GENERALIZE
    비교 샘플에서 각 인자(position/color/size/fill)를 train 전체에 일관된 "가장 일반적인 표현식"으로 resolve한다
    (literal보다 corner-br=(H-1,W-1)·coord_of(obj)+delta·color_of(other) 등 일반식을 선호 = anti-unify 방향).
    결과 flag: ^schema-ready, 그리고 인자별 ^expr-{arg}.
    · (i) (O ^name generalize), (S1 ^operator O +)
    · (b) (S1 ^expr-{arg} <표현식명>) 인자별 — body가 직접(영속, 표시용). ※ 결과 flag로 묶이는 게 더 맞을 수도(추후 검토)
    · (o) (S1 ^schema-ready yes)

4. COMPOSE
    두 개의 frozen transformation(make_grid + coloring)으로 test 입력에 답을 조립한다.
    인자가 미해결이면 declined. 결과 flag: ^answer-ready (또는 ^declined), 답은 ^io.output-link(I3)에 ^answer로.
    · (i) (O ^name compose), (S1 ^operator O +)
    · (b) (I3 ^answer <grid>) output-link에 직접(IO WME) — 또는 실패 시 (S1 ^declined yes)
    · (o) (S1 ^answer-ready yes)

5. SUBMIT
    완료 표시. 결과 flag: ^done. (계산 없음 — apply*submit 규칙만으로 ^done을 씀.)
    · (i) (O ^name submit), (S1 ^operator O +)
    · (b) 없음 (body 없음)
    · (o) (S1 ^done yes)

   ※ 아직 없는(향후) operator: select(다객체 중 선택), search(effect로 DSL 탐색), descend(tier 하강) 등.
     operator에 인자가 필요해지면 propose*X의 RHS에 Action("<o>","arg",...)를 추가하면 (<o> ^name X ^arg ...)로 객체에 붙는다.
     이들은 위 (b) 경고가 직접 걸리는 첫 사례가 될 것: search의 잠정 가설/select의 후보는 i-support여야 철회된다.


수정사항 및 질문

0) [요구] dashboard.html의 wm, rules 각 영역 상단 바 우측에 toggle 전부 열기/전부 닫기 버튼이 있으면 좋겠음.
   [변경] 두 패널 헤더 우측에 "⇕ all" 버튼 추가(toggleAll). 구현 완료.

1) [요구] 한 step에서 전체 열기를 한 후, 다음 step에서 추가된 토글이 있는 경우, 해당 토글은 닫혀있어야하는 것이 정상.
   [변경] 열림 상태를 노드 id로 추적(wmOpen / ruleOpen Set). "전체 열기"는 그 시점에 존재하는 토글의 id만 set에
   넣으므로, 다음 step에서 새로 생긴 토글은 set에 없어 닫힌 채로 시작함. 구현 완료.

2) [요구] 전부 열기/전부 닫기 버튼으로 통합하여 토글의 열림상태가 일부 다를 경우, 첫클릭은 일부 닫혀 있는 토글을 여는것,
   두번째 클릭은 전부 닫는 것으로 기능했으면 좋겠음.
   [변경] toggleAll = "하나라도 닫혀 있으면 전부 열기, 전부 열려 있으면 전부 닫기" 단일 버튼. 구현 완료.

3) [요구] rules 영역의 토글은 열려있는 것이 기본으로 되어 있는데 wm과 마찬가지로 닫힌 상태로 보여지는 것이 기본이었으면 좋겠음.
   [변경] 기본 닫힘으로 변경(ruleOpen Set, 기본 비어있음=닫힘). 발화한 규칙은 닫혀 있어도 녹색 테두리 + "● fired"로 식별 가능. 구현 완료.

4) [요구] rules 영역 각 규칙은 if-then 구조로 되어 있는데 If + 줄바꿈, then + 줄바꿈으로 조건만 줄의 시작에 명시되도록 되었으면 좋겠음.
   [변경] IF / THEN 라벨을 각각 한 줄로, 그 아래 각 조건/액션을 자기 줄(.condline)에 표기. 구현 완료.

5) [요구] rules 영역 ... 긍정조건=아주 옅은 파랑 배경, 부정조건=아주 옅은 빨강 배경, 조건 만족 시 글자색이 조금 짙은 파랑/빨강,
   발화 규칙=녹색 테두리. 이 규칙에 맞게 표기를 수정했으면 좋겠음.
   [답변/검증] 이미 그 규칙대로 구현되어 있음(.cond.pos=옅은 파랑 배경 / .cond.neg=옅은 빨강 배경 / .sat=진한 글자 /
   .rule.on=녹색 테두리). 기본 글자색은 회색(미충족). 재생성으로 적용 확인.

6) [요구] 공식 soar는 propose*move_block처럼 * 기호를 사용함. propose/apply와 operator name을 *로 잇는 규칙인지 검증하고
   dashboard의 -표기를 *로 바꿀 수 있는지 확인.
   [답변] 맞음. Soar 관례는 production 이름을 <problem-space>*<role>*<operator>[*<variant>]로 '*'로 이음
   (예: blocks-world*propose*move-block, blocks-world*apply*move-block*remove-old-ontop). 단 '*'는 아키텍처가
   강제하는 문법이 아니라 명명 "관례"(이름은 임의 문자열 가능).
   [변경] 규칙명을 propose-X/apply-X → propose*X/apply*X로 변경(arc/expr_solver.py). 대시보드에 그대로 반영됨.

7) [요구] 원본 soar의 propose/apply 규칙 RHS에 무엇이 들어가는지 조사하고 규칙 표기 규칙을 정립.
   [정립]
     · propose*X RHS = (1) operator 객체 생성: (<o> ^name X [^arg ...]),  (2) acceptable preference: (<s> ^operator <o> +).
       (operator 비교가 필요하면 compare 규칙이 따로 (<s> ^operator <o> >|=|- ...)를 만든다.)  전부 i-support.
     · apply*X RHS = 선택된 operator를 테스트((<s> ^operator <o>)(<o> ^name X))하고 state를 영구 변경(WME 생성/제거).
       o-support. 외부 행동이면 ^io.output-link에 명령을 만든다.
     · 우리 표기 = propose*X(객체+acceptable) / apply*X(결과 flag, o-support) / 무거운 계산은 Python operator body
       (= SOAR의 RHS-function: 결정 사이클은 순수 유지, 계산만 외부 함수로).

8) [요구] Propose step에서 rule-fire가 있기 전에 elaboration wave가 있는지 명시하기.
   [답변] propose phase는 "elaboration을 quiescence까지" 도는 것이고, 규칙 발화 자체가 elaboration wave다. 우리 solver엔
   proposal보다 먼저 도는 state-elaboration 규칙이 (아직) 없어서 첫 wave가 곧 operator proposal이다.
   [변경] 각 발화/철회 라벨에 "(wave N)" 표기를 붙여 wave 구조를 명시.

9) [요구] Propose step에서 rule-fire가 quiescence 다음에 나오는 것이 맞는지 확인하고 수정.
   [답변] 아니오. 발화는 quiescence "전"(=elaboration wave 중)에 일어난다. quiescence는 더 이상 발화/철회가 없는
   고정점(=끝). 따라서 현재 순서(발화들 → quiescence)가 정확함. 변경 없음.

10) [요구] Propose step에서 operator가 propose되면 +기호 wme가 wm에 추가되는데 wm 가장 상단에 추가되는 게 맞는지 확인.
    [답변] SOAR WM은 순서 없는 "집합(set)"이라 "가장 상단"이라는 개념 자체가 없다. 대시보드의 줄 순서는 표시용 정렬일 뿐.
    acceptable preference (S1 ^operator O1 +)가 WM에 올라오는 것은 맞음(이미 반영). 위치는 의미 없음 → 변경 없음.

11) [요구] Decide에서 operator select 시 선택되지 않은 operator들이 어떤 단계에서 사라지는지 확인.
    [답변] selection 자체로는 사라지지 않는다. 선택 안 된 operator의 acceptable preference는 그 proposal이 유지되는 동안
    (i-support) WM에 남아 있고, proposal의 조건이 깨질 때 retract된다. 선택된 것은 아키텍처가 bare (S1 ^operator O)로 설치하며,
    선택된 것의 acceptable preference도 proposal이 살아있는 동안 공존한다. 우리 solver는 사이클당 후보가 1개라, observe의 후보
    (S1 ^operator O1 +)는 apply에서 ^observed yes가 set되어 propose*observe가 retract되는 "그 시점"에 사라진다
    (selection과 동시도, 임의의 다음 단계도 아니라 = proposal 철회 시점). → _sync_candidates가 이를 그대로 반영(트레이스).

12) [요구] Apply에서 여러 wme가 추가될 때 첫 substep만 녹색으로 보이는 문제. apply 이후 추가 substep을 하나로 합치는 게 좋겠음.
    [변경] operator body가 추가하는 WME 전부를 한 step("+ X body → N WMEs added")으로 합침. 한 step이라 변경분 전체가
    함께 녹색으로 보임. 구현 완료.

13) [요구] Apply에서 wm 변경 이후 조건이 매칭하지 않는 apply/propose rule들이 fire/retract된 이력이 있음. 조건 점검 필요.
    [답변] 대부분은 정상이다. ^observed yes가 set되면 (a) propose*compare가 fire(observed=yes로 조건 충족 → 다음 operator
    제안), (b) propose*observe가 retract(부정조건 -(S1 ^observed) 위반)된다 — 둘 다 올바른 truth-maintenance.
    문제로 보였던 apply*observe의 fire→retract는, propose*observe가 retract되며 operator 객체 (O1 ^name observe)가
    사라져 apply*observe의 instantiation 매칭이 끊긴 것. 단 그 결과 ^observed yes는 o-support라 WM에서 안 사라지므로
    "WM 변화 없는" 무해한 retract였음. (apply 규칙 조건 자체는 정상.)
    [변경] WM을 실제로 바꾸지 않은 fire/retract는 트레이스에서 숨김 → 이 noise 제거.

14) [요구] Apply에서 wme 변경 시 elaboration wave가 동작해야 하는데 원본 soar의 흐름/순서를 확인해 적용.
    [답변/적용] SOAR apply phase = 선택된 operator를 테스트하는 apply 규칙이 발화해 state를 o-support로 변경 → 그 변경이
    i-support elaboration(및 다음 operator의 proposal)을 wave로 재계산(retract/fire) → 더 변화 없을 때까지(quiescence) 반복.
    우리 구현도 동일: apply body(계산) → apply*X(결과 flag, o-support) → elaboration wave(다음 propose*Y fire, 이전
    propose*X retract) → quiescence. (위 8·13 변경으로 wave/순서가 트레이스에 그대로 드러남.)

15) [요구] propose/apply에서 일어나는 elaboration wave를 더 명시적으로 — 정식 결정에 의한 1차 발화와 그 이후 2차
    발화를 wave1, 2, 3… 으로 표기.
    [변경 v1] 8번의 라벨 문자열 "(wave N)"을 구조적 필드(event.wave)로 분리. (fine_trace.py: emit(wave=), elaborate가
    wave 전달, apply body=wave 1)
    [변경 v2 — 박스가 sub-cycle을 더 도드라지게 하던 문제 수정] wave를 박스/칩이 아니라 평문으로 바꾸고, 큰 단계를 박스로:
      · cycle map에서 input/propose/decide/apply/output 큰 단계 줄 = 테두리 박스(.maprow.phase border+bg) = 풀이의 구조.
      · 그 아래 이벤트 줄은 고정 16px 들여쓰기 한 단계만. wave는 박스 없이 "wave N · " 평문(muted)으로 prefix.
      · per-wave 들여쓰기 제거 — wave가 10+ 깊어져도 평평한 목록으로 읽힘(사용자 지적: 깊은 cascade 가독성).
      · 하단 이벤트바에도 "wave=N" 평문. (dashboard.py: .maprow.phase 박스, .wtext 평문, wave-sec/wchip 삭제)
    예) easy000a cycle 1 apply 박스 아래:  wave 1 observe body → wave 1 apply*observe → wave 2 propose*compare(fire)
        → wave 2 propose*observe(retract).

16) [요구→완료] rules 패널 fire/retract 미구분 버그 수정 (지난 턴 "미해결"이던 것).
    [문제] renderRules가 event.kind를 안 보고 r.name===e.rule이면 무조건 "● fired"(초록)를 붙여, retract step에서도
    철회된 규칙이 "● fired"로 보였다. 철회는 LHS가 깨져 일어나므로 그 규칙 조건은 회색(미충족)으로 그려지는데 배지는
    "fired"라 자기모순 → 위화감.
    [변경] renderRules가 status를 계산(kind=='rule-retract'→'retract', 'rule-fire'→'fire')해 ruleCard에 넘김.
    fire = 초록 테두리 + "● fired"(기존), retract = 빨강 테두리(.rule.off) + "● retracted"(.retracttag). 이제 철회 step은
    "빨강 테두리 ● retracted + 조건 회색(LHS 깨짐)"으로 일관되게 읽힌다. rules 툴팁에도 설명 추가. (dashboard.py)

──
[메모] 파일 인코딩: dashboard.py에 한글 툴팁이 길어져 Python 3.9 토크나이저가 긴 줄에서 UTF-8 sniff에 실패
("Non-UTF-8 ... no encoding declared")하던 것을, 상단에 `# -*- coding: utf-8 -*-` 선언 추가로 해결.
