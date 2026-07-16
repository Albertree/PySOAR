# ARBOR — AAAI-27 논문 작업 컨텍스트 (핸드오프)

> **임시 핸드오프 문서.** 다른 디바이스로 작업을 옮기기 위해 이 세션의 리서치·설계·결정·초안
> 상태를 한 곳에 모았다. 브랜치 `seokki-paper` (base = `seokki-refactor` @ `d56f344`).
> 작성일 2026-07-16.

---

## 0. 지금 상태 한 줄
`seokki-refactor` 구조를 대상으로 AAAI-27 main track 논문의 **Intro + Related Work를 전문 작성**,
**§3–7은 문단당 한 줄 스켈레톤**(값·성능 없음)으로 초안화. 파일: [`paper/AnonymousSubmission2027.tex`](AnonymousSubmission2027.tex) + [`paper/arbor.bib`](arbor.bib).

## 1. 마감·형식 (AAAI-27)
- abstract **2026-07-21**, full paper **2026-07-28** (AoE). Montréal, 2027-02.
- **7 페이지** 본문 + 최대 9(8–9는 references만). two-column, **double-blind**, no hyperref.
- GenAI 사용 허용하되 **날조 인용 금지** → bib는 실존 확인분만, arXiv 리포트는 `@misc`.
- OpenReview 제출. Author Kit = aaai2027.sty/.bst (paper/ 에 복사됨). 로컬 TeX 미설치 → **미컴파일**.

## 2. 확정된 논문 프레이밍 (2026-07-16, 사용자 결정)
1. **Headline contribution = 소수예시 스킬획득 메커니즘** (impasse-driven descent + within-pair
   program synthesis + cross-pair anti-unification).
2. **포지셔닝 = 통제된 커리큘럼 위 메커니즘 논문, SOTA 주장 없음.** 성능은 정직히, 나중에.
3. **LLM 베이스라인 실험 없음** — data-inefficiency 문헌 인용만.
4. **키워드 = Cognitive Systems / KRR / ML: Program Synthesis·Analogy.**

기여 4개(본문 §1):
- ① impasse가 operator 시퀀스를 정하는 SOAR 커널 위 메커니즘(태스크마다 하강깊이·step 다름).
- ② frozen 2-atom DSL 위 인자=일반표현식을 generate→train대조→기각/생존으로 탐색
  ("가장 큰"·"코너"·(H−1,W−1)이 손코딩 아니라 발견·검증).
- ③ per-pair program을 structure-mapping 정렬 후 anti-unify → task-general 스키마+typed slot,
  train-only resolve.
- ④ 정직성: 정보 부족 시 explicit impasse decline, 탐색이 트레이스에 감사 가능.

## 3. 당위성 스파인 (Intro·Related가 세우는 논리 사슬 — 검토 포인트)
1. 문제를 "지식"이 아니라 **획득 효율**로 재정의 (Chollet) → 스케일로 못 메우는 축.
2. 스케일/ICL이 왜 실패 = **메커니즘 자체가 병목** (ICL=검색·SCAN/COGS·GSM-Symbolic·RL sharpens).
3. 기존 심볼릭 대안도 비용(wake-sleep·대규모 샘플링·per-task gradient·LLM-in-loop) →
   "few 예시로, training loop 없이"라는 **빈 자리**.
4. ARBOR 각 구조요소를 그 빈 자리의 해답으로 제시(§4 quadrant로 조직).
5. Related 5소절이 사슬을 뒷받침 + 마지막 문단 차별화(결정론적 SM+AU·no gradient·no LLM·auditable).

**리뷰어 예상 공격(선제 방어 필요):** "frozen 2-atom + 좌표식 brute-force가 좁은 도메인(재채색/이동)
에만 통하는 것 아니냐"는 일반성 의심. → §1에 "표현식 조합이 왜 transformation 카탈로그보다 일반적인가"
한 문장 + §4.2/§6에서 표현식 공간 범위·확장성 설득이 관건.

## 4. 섹션 구성 (7p)
- **§1 Introduction** — [전문 완료] 4문단(위 당위성 사슬) + 기여 4 + 정직한 범위.
- **§2 Related Work** — [전문 완료] 5소절: (2.1) LLM data efficiency 한계 · (2.2) systematic/
  compositional gen · (2.3) ARC 벤치마크 · (2.4) program synthesis & library learning + LLM-guided ·
  (2.5) 유추·structure mapping·anti-unification·인지아키텍처 + 차별화 문단.
- **§3 Background** — [스켈레톤] SOAR 커널(M1–M4 + 차등검증) · ARCKG 5계층 typed property(유일한 눈,
  lazy 하강) · recursive compare(COMM/DIFF).
- **§4 Method** — [스켈레톤] 4.1 impasse 제어 · 4.2 within-pair synthesis(인자=일반식) · 4.3 structure
  mapping · 4.4 anti-unification+resolve · 4.5 compress. (Algorithm 1 예정)
- **§5 Worked Example** — [스켈레톤] 한 태스크 트레이스: 하강→시도·기각식→(H−1,W−1) 생존→anti-unify
  →test 적용. (Figure 1)
- **§6 Demonstration & Honest Scope** — [스켈레톤] 커리큘럼 + **태스크별 하강깊이·step 분포**(탐색이
  함수에 안 숨음) + impasse-decline + 해석가능성. **성능 수치 나중에.** (Table 1, Figure 2)
- **§7 Limitations/Conclusion** — [스켈레톤] 범위 한계 + compress/relation식 확장 + 인터랙티브(ARC-AGI-3
  식) + 기여 재진술.

## 5. ⚠️ 제출 전 반드시 처리 (중요도 순)
1. **성능 숫자 재감사(최우선).** 메모리 2026-07-15 감사가 "README의 easy_a 9/9·easy 13/16은 오래된
   expr_solver 스택, flagship 2/9, anti-unification 미실행"이라 경고. `seokki-refactor`엔 AU·AST·compress가
   실재+golden-step 게이트라 진전됐으나, **§6 숫자는 이 브랜치에서 직접 돌려 확정**해야 함. 본문엔
   숫자 미기입(주석에만).
2. **익명성.** 제목/본문 `ARBOR`·`PySOAR`가 공개 저장소(Albertree/PySOAR)로 검색되면 double-blind 위배
   가능. tex 주석에 중립 제목 대안 2개 있음.
3. **인용 venue 검증.** GSM-Symbolic(ICLR 2025)·Illusion of Thinking(venue 논쟁)·Reizinger(ICML 2024) 등
   arbor.bib 주석에 확인표시. arXiv 리포트는 @misc.
4. **컴파일.** 로컬 TeX 없음 → Overleaf/MiKTeX에 paper/ 통째로 올려 1회 검증.

## 6. seokki-refactor 구조 요약 (논문이 서술하는 시스템)
- `soar/` — Soar 9.6.5 결정 사이클 fidelity 재구현. M1 preference/impasse · M2 i/o-support 진리유지 ·
  M3 PSA+substate 자동생성 · M4 chunking/backtrace. C++ Soar 차등 오라클(preference/impasse 17/17).
- `arbor/perception/arckg/` — ARCKG 5계층(TASK→PAIR→GRID→OBJECT→PIXEL), typed property, `comparison.py`
  compare(2차/n차 재귀 → COMM/DIFF). impasse(property 공백)로 lazy 하강.
- `arbor/reasoning/` — `program.py`(pair 내 synthesis), `antiunify.py`(정렬 `_align`·`resolve_slot`·
  `_resolve_cellset`·좌표식 brute-force `_gen_exprs`/`_selectors`), `program_ast.py`(typed-arg AST:
  execute/antiunify_ast/to_source), `compare_engine.py`.
- Operators(SOAR productions): observe→compare→hypothesize→synthesize→verify→generalize→apply_solution
  (+compress). 시퀀스가 태스크마다 emergent(결정 사이클이 WM 보고 선택).
- DSL frozen 2 atom: `make_grid`(캔버스) + `coloring`(셀). 일반화 = 인자를 일반 표현식으로 resolve.
- `docs/superpowers/specs/` — 최신 설계: `2026-07-15-program-ast-design.md`,
  `2026-07-16-unified-grid-flow-carrydown-design.md` 등(method 서술의 1차 근거).
- 하네스: `ARBOR_HARNESS.md`(§0.5 4칸 모델: 서술/절차 × pair/task; §1 손코딩 finder 금지; §P5 test 오라클
  금지) — method 정직성 규약의 출처.

## 7. 리서치 자료 — 인용 후보 (이 세션 조사, venue 검증본 위주)
arbor.bib에 이미 수록된 핵심 + 확장 후보. **[확정]=인용 안전, [검증]=arXiv 확실·학회 재확인, [주의]=venue 미확정.**

### 문제(§1·§2.1–2.3) — data inefficiency / ICL / systematic gen / ARC
- [확정] Chollet 2019, *On the Measure of Intelligence* (ARC), arXiv:1911.01547.
- [검증] Chollet+ 2025, *ARC-AGI-2*, arXiv:2505.11831 (arXiv 화이트페이퍼, 학회 아님).
- [확정] ARC Prize 2025 Technical Report, arXiv:2601.10904 (Gemini 3·Claude Opus 4.5 <24% ARC-AGI-2).
- **[확정] ARC-AGI-3** (arXiv:2603.24621, 2026-03): GPT-5.4·Gemini 3.1·Opus 4.6 **<1%**, 인간 100%.
  = "GPT-5 명시 확정 출처" 공백 메움. (아직 bib 미수록 — 추가 권장.)
- [확정] Wu+ 2025, *Fluid Intelligence Deficiency (ARC)*, NAACL 2025.
- [확정] Wang+ 2025, *Can ICL Really Generalize to OOD?*, ICLR 2025 (arXiv:2410.09695).
- [확정] Reizinger+ 2024, *Position: Understanding LLMs Requires More Than Statistical Gen*, ICML 2024.
- [주의] Mirzadeh+ 2025, *GSM-Symbolic*, ICLR 2025(재확인) / Shojaee+ 2025, *Illusion of Thinking*,
  arXiv:2506.06941(venue 논쟁).
- [확정] Yue+ 2025, *Does RL Really Incentivize Reasoning...*, NeurIPS 2025 (Best Paper Runner-Up).
- [확정] Lake&Baroni 2018 *SCAN* (ICML) · Kim&Linzen 2020 *COGS* (EMNLP) · Lake&Baroni 2023 (Nature, MLC).
- 추가 프런티어 반박(값 강함, 필요시): I-RAVEN-X(NeurIPS 2025 WS, o3-mini 86.6→17%), AgentCoMa(ACL 2026),
  MATH-Perturb(ICML 2025), Potemkin Understanding(ICML 2025), Compositional-ARC(ICLR 2026, 5.7M>frontier).

### 방법 계보(§2.4–2.5) — program synthesis / library / anti-unification / SM
- [확정] Lake+ 2015 *BPL* (Science) · Ellis+ 2021 *DreamCoder* (PLDI) · Bowers+ 2023 *Stitch* (POPL) ·
  Grand+ 2024 *LILO* (ICLR) · Stengel-Eskin+ 2024 *ReGAL* (ICML).
- [확정] Wang+ 2024 *Hypothesis Search* (ICLR) · Butt+ 2024 *CodeIt* (ICML) · Li+ 2025 *Induction+
  Transduction* (ICLR) · [검증] Akyürek+ 2024 *Test-Time Training*, arXiv:2411.07279.
- [확정] Gentner 1983 *Structure-Mapping* (Cog Sci) · Cerna&Kutsia 2023 *Anti-unification Survey* (IJCAI) ·
  Mitchell 2021 *Abstraction & Analogy* (Annals NYAS) · Newell 1990 *UTC* · Laird 2012 *Soar*.

### 연구실 공유 7편(참고, ARBOR와 가까운 경쟁/계보)
- 2504.20997 = Toward Efficient Exploration by LLM Agents (=위 exploration) · 2501.02825 = Randomly Sampled
  Language(ICLR25 WS) · 2502.07190 = Fluid Intelligence(위).
- **2505.10819 = PoE-World** (Kevin Ellis; 프로그램 전문가 world model) — **ARBOR 최근접 경쟁자**, 차별화 필수.
- **2605.03413 = Learning to Theorize the World from Observation** (Sungjin Ahn; 관찰→심볼릭 이론) — 경쟁/계보.
- 2605.14477 = Test-Time Learning with an Evolving Library (MSR; test-time 라이브러리) — Act3 비교.
- 2602.10390 = Affordances Enable Partial World Modeling with LLMs (DeepMind) — 보조.

## 8. 다음 작업 후보
- (A) §4 Method 본문 작성(antiunify.py/program_ast.py 충실 전개 + Algorithm 1).
- (B) 성능 재감사 후 §6 숫자 확정(seokki-refactor 실제 run).
- (C) §1·§2 톤·길이 조정(7p 예산) + 일반성 이음새 선제 방어 문장.
- (D) ARC-AGI-3·프런티어 반박 인용을 arbor.bib에 추가.

> 이전 세션 메모리: `.claude/.../memory/aaai27-paper-project.md` (감사·lineage·baseline),
> `arc-layer-two-sibling-repos.md`, `seokki-windows-branch.md`.
