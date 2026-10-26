import json

import pytest

from clinguard import (HIGH, LOW, NONE, ClinGuard, DangerRules, Entry, Lexicon,
                       SuggestionStore, normalize)
from clinguard.cli import main

RECORDS = [
    {"phrase": "Ori n fo mi", "meaning": "My head is aching", "clinical_term": "Headache"},
    {"phrase": "O dun mi", "meaning": "It is paining me", "clinical_term": "Acute pain"},
    {"phrase": "Se ni ma n remi bi eniwipe mi o ni imi okon mi dun lemolemo bi mo ba ti nrin",
     "meaning": "I am weak and breathless when walking", "clinical_term": "Severe anemia"},
    {"phrase": "Mi o le mi", "meaning": "I cannot breathe", "clinical_term": "Dyspnea", "danger": True},
]


@pytest.fixture
def lex():
    return Lexicon.from_records(RECORDS, language="yo")


def test_normalize_strips_tone_marks():
    assert normalize("Orí mi ń fọ́ mi!") == "ori mi n fo mi"


def test_tone_marked_speech_matches(lex):
    m = lex.best("Orí ń fọ́ mi")
    assert m and m.entry.clinical_term == "Headache" and m.score == 1.0


def test_short_phrase_does_not_hijack_long_sentence(lex):
    long = RECORDS[2]["phrase"]
    assert lex.best(long).entry.clinical_term == "Severe anemia"


def test_long_sentence_does_not_hijack_short_phrase(lex):
    assert lex.best("O dun mi").entry.clinical_term == "Acute pain"


def test_self_check_clean(lex):
    assert lex.self_check() == []


def test_beagrace_style_keys_supported():
    lx = Lexicon.from_records([{"dialect_expression": "Ara mi n jo", "literal_meaning": "my body is burning",
                                "english_medical_term": "Burning sensation"}])
    assert lx.best("ara mi n jo").entry.clinical_term == "Burning sensation"


def test_csv_loading(tmp_path):
    p = tmp_path / "lex.csv"
    p.write_text("phrase,meaning,clinical_term,danger\nAra mi gbona,My body is hot,Fever,false\n", encoding="utf-8")
    assert Lexicon.from_file(p).best("Ara mi gbóná").entry.clinical_term == "Fever"


def test_pipeline_high_confidence(lex):
    a = ClinGuard(lex).assess("Ori n fo mi")
    assert a.confidence == HIGH and not a.danger and not a.needs_review


def test_pipeline_fallback_marked_low(lex):
    a = ClinGuard(lex, translate=lambda s: "My leg is swelling").assess("ese mi n wu")
    assert a.confidence == LOW and a.needs_review


def test_pipeline_not_understood(lex):
    a = ClinGuard(lex, translate=lambda s: "").assess("xyz")
    assert a.confidence == NONE and a.needs_review


def test_danger_from_entry_flag(lex):
    a = ClinGuard(lex).assess("Mi ò le mí")
    assert a.danger and "Dyspnea" in a.danger_reasons


def test_danger_from_english_keyword_without_ai_lexicon_match(lex):
    a = ClinGuard(lex, translate=lambda s: "She is bleeding heavily").assess("unknown words")
    assert a.danger


def test_danger_from_local_keyword(lex):
    rules = DangerRules(local_keywords={"yo": ["warapa"]})
    a = ClinGuard(lex, rules, language="yo", translate=lambda s: "something").assess("o ni warapa")
    assert a.danger


def test_no_false_alarm_on_blood_pressure(lex):
    a = ClinGuard(lex, translate=lambda s: "I check my blood pressure").assess("abc")
    assert not a.danger


def test_note_gets_banners(lex):
    a = ClinGuard(lex, write_note=lambda m, t: "NOTE").assess("Mi o le mi")
    assert a.note.startswith("URGENT") and a.note.endswith("NOTE")


def test_learning_loop(tmp_path, lex):
    store = SuggestionStore(tmp_path)
    sid = store.submit("Ese mi n wu", "My leg is swelling", "Leg swelling", language="yo")
    assert len(store.pending()) == 1
    with pytest.raises(ValueError):
        store.review(sid, approve=True, reviewer="")
    store.review(sid, approve=True, reviewer="Reviewer A")
    assert store.pending() == []
    learned = lex.extend(store.approved_entries("yo"))
    assert learned.best("Ẹsẹ̀ mi ń wú").entry.source == "learned"
    with pytest.raises(KeyError):
        store.review(sid, approve=False, reviewer="Reviewer A")


def test_learning_rejected_not_added(tmp_path, lex):
    store = SuggestionStore(tmp_path)
    sid = store.submit("abc def", "wrong", language="yo")
    store.review(sid, approve=False, reviewer="R")
    assert store.approved_entries() == []


def test_cli_check_and_validate(tmp_path, capsys):
    p = tmp_path / "lex.json"
    p.write_text(json.dumps(RECORDS), encoding="utf-8")
    assert main(["check", str(p), "Mi o le mi"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["danger"] is True and out["confidence"] == "high"
    assert main(["validate", str(p)]) == 0
