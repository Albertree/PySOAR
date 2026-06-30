Operator Note
   (내가 필요하다고 보는 operator를 적어두는 곳)

1. OBSERVE
    ARCKG가 폴더 파일 구조로 있었을 때, 지정한 폴더(노드)를 확인하는 것에 해당함. 폴더를 열어서 해당 노드의 속성 (property)을 확인하고, 바로 하위에 어떤 노드들이 있는지 확인함.

2. SELECT
   생각을 조합하는 과정 및 ARC 그리드를 변형하여 문제를 해결하는 과정에서 객체나 특정 대상을 선택하는 operator로 조건으로 객체를 선택함.

3. SEARCH
   SELECT와 비슷하게 조건으로 객체를 걸러내는 작업을 하지만 

4. COMPARE
   선택한 두 객체 혹은 그룹을 비교하는 operator로 단일 객체-단일 객체를 선택하거나, 단일 객체-객체 그룹을 선택하거나, 객체 그룹-객체 그룹을 선택할 수 있다. 



수정사항 및 질문
   (dashboard.html을 보고 부족한 부분 / 수정해야 하는 부분 / 원본 soar에서 확인해야 하는 부분)
   → 답변·변경 기록은 NOTE-answer.md 참고.

0) dashboard.html의 wm, rules 각 영역 상단 바 우측에 toggle 전부 열기/전부 닫기 버튼이 있으면 좋겠음.

1) 한 step에서 전체 열기를 한 후, 다음 step에서 추가된 토글이 있는 경우, 해당 토글은 닫혀있어야하는 것이 정상.

2) 전부 열기/전부 닫기 버튼으로 통합하여 토글의 열림상태가 일부 다를 경우, 첫클릭은 일부 닫혀 있는 토글을 여는것,
   두번째 클릭은 전부 닫는 것으로 기능했으면 좋겠음.

3) rules 영역의 토글은 열려있는 것이 기본으로 되어 있는데 wm과 마찬가지로 닫힌 상태로 보여지는 것이 기본이었으면 좋겠음.

4) rules 영역 각 규칙은 if-then 구조로 되어 있는데 If + 줄바꿈, then + 줄바꿈으로 조건만 줄의 시작에 명시되도록 되었으면 좋겠음.

5) rules 영역 ... 긍정조건=아주 옅은 파랑 배경, 부정조건=아주 옅은 빨강 배경, 조건 만족 시 글자색이 조금 짙은 파랑/빨강,
   발화 규칙=녹색 테두리. 이 규칙에 맞게 표기를 수정했으면 좋겠음.

6) 공식 soar는 propose*move_block처럼 * 기호를 사용함. propose/apply와 operator name을 *로 잇는 규칙인지 검증하고
   dashboard의 -표기를 *로 바꿀 수 있는지 확인.

7) 원본 soar의 propose/apply 규칙 RHS에 무엇이 들어가는지 조사하고 규칙 표기 규칙을 정립.

8) Propose step에서 rule-fire가 있기 전에 elaboration wave가 있는지 명시하기.

9) Propose step에서 rule-fire가 quiescence 다음에 나오는 것이 맞는지 확인하고 수정.

10) Propose step에서 operator가 propose되면 +기호 wme가 wm에 추가되는데 wm 가장 상단에 추가되는 게 맞는지 확인.

11) Decide에서 operator select 시 선택되지 않은 operator들이 어떤 단계에서 사라지는지 확인.

12) Apply에서 여러 wme가 추가될 때 첫 substep만 녹색으로 보이는 문제. apply 이후 추가 substep을 하나로 합치는 게 좋겠음.

13) Apply에서 wm 변경 이후 조건이 매칭하지 않는 apply/propose rule들이 fire/retract된 이력이 있음. 조건 점검 필요.

14) Apply에서 wme 변경 시 elaboration wave가 동작해야 하는데 원본 soar의 흐름/순서를 확인해 적용.

15) propose/apply의 elaboration wave를 더 명시적으로 — 정식 결정에 의한 1차 발화와 그 이후 2차 발화를
    wave1, 2, 3… 으로 dashboard에 표기.

16) operator에 따라 달라지는 i/o-support를 operator note에 정리해 기록. 지금 dashboard에 보일 필요는 없고,
    operator를 확장하면서 i/o-support도 함께 기록·저장.

17) wave 칩이 박스라 sub-cycle인데도 큰 단계보다 먼저 눈에 띔 → 큰 단계(input/propose/decide/apply/output)를
    박스/테두리로, wave는 평문으로. cycle map의 per-wave 들여쓰기도 재고(10+ 깊어지면 가독성 저하).

18) rule retracted 단계에서 rules 영역에 여전히 "● fired"가 뜸(retract된 rule은 LHS 미충족인데 fired 표시).
    retracted면 "● retracted"로 구분 표기.
