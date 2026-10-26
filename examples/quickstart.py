"""ClinGuard quickstart. Run:  python examples/quickstart.py

The demo lexicon is ILLUSTRATIVE ONLY and not clinically validated.
"""
from pathlib import Path

from clinguard import ClinGuard, DangerRules, Lexicon, SuggestionStore

here = Path(__file__).parent
lexicon = Lexicon.from_file(here / "demo_lexicon.json", language="yo")


def my_translate(said: str) -> str:
    # Plug in any model or service here (LLM, MT API, ...). Return "" if not understood.
    return "My leg is swelling"


def my_note_writer(meaning: str, clinical_term: str) -> str:
    # Plug in your own note generator. Kept simple for the demo.
    return f"Symptom: {clinical_term or 'see patient report'}\nPatient report: {meaning}"


guard = ClinGuard(lexicon, DangerRules(), language="yo", translate=my_translate, write_note=my_note_writer)

for said in ["Orí mi ń fọ́ mi", "Mi ò le mí", "Ẹsẹ̀ mi ń wú"]:
    a = guard.assess(said)
    print(f"\n> {said}")
    print(f"  confidence={a.confidence} danger={a.danger} needs_review={a.needs_review}")
    print("  " + a.note.replace("\n", "\n  "))

# Human-in-the-loop learning: a nurse suggests, a reviewer approves
store = SuggestionStore(here / "_demo_store")
sid = store.submit("Ese mi n wu", "My leg is swelling", "Leg swelling (edema)", language="yo")
store.review(sid, approve=True, reviewer="Native-speaker reviewer")
guard.lexicon = lexicon.extend(store.approved_entries("yo"))
print("\nAfter approval:", guard.assess("Ẹsẹ̀ mi ń wú").confidence)
