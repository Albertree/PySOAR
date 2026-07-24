from arbor.soar.wm import WorkingMemory


def test_journal_none_by_default_no_error():
    wm = WorkingMemory()
    assert wm.journal is None
    wm.add("S1", "x", 1)          # journal=None 이어도 안전
    wm.remove("S1", "x", 1)


def test_journal_records_only_real_mutations():
    wm = WorkingMemory()
    log = []
    wm.journal = log
    wm.add("S1", "x", 1)          # 신규 → 기록
    wm.add("S1", "x", 1)          # 중복 → 무기록(WM 셋 의미)
    wm.remove("S1", "x", 1)       # 존재 → 기록
    wm.remove("S1", "x", 1)       # 이미 없음 → 무기록
    assert log == [("+", ("S1", "x", 1)), ("-", ("S1", "x", 1))]
