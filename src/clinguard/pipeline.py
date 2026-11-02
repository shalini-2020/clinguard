"""ClinGuard pipeline: lexicon-first understanding with independent safety checks.

    said (text from any speech recogniser)
      -> lexicon match (trusted, curated by native speakers)
      -> or fallback translation (your own function, marked NEEDS REVIEW)
      -> danger-sign check (rules, never the AI)
      -> optional note writer (your own function), with safety banners added

ClinGuard does not call any AI provider itself. You pass in plain Python
functions for translation and note writing, so it works with any model.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .lexicon import Lexicon, Match
from .safety import DangerRules

HIGH, LOW, NONE = "high", "low", "none"


@dataclass
class Assessment:
    said: str
    meaning: str                       # English meaning (from lexicon, or fallback translation)
    clinical_term: str                 # empty if no lexicon match
    confidence: str                    # "high" (lexicon match), "low" (fallback), "none" (not understood)
    score: float                       # lexicon match score, 0.0 if none
    danger_reasons: List[str] = field(default_factory=list)
    note: str = ""                     # clinical note, if a note writer was supplied
    match: Optional[Match] = None

    @property
    def danger(self) -> bool:
        return bool(self.danger_reasons)

    @property
    def needs_review(self) -> bool:
        """True when a human must confirm before acting."""
        return self.confidence != HIGH or self.danger

    def banners(self) -> List[str]:
        out = []
        if self.danger:
            out.append("URGENT - possible danger sign detected by rule-based safety check. Escalate now.")
        if self.confidence == LOW:
            out.append("LOW CONFIDENCE - phrase not in the lexicon. Confirm with the patient before acting.")
        if self.confidence == NONE:
            out.append("NOT UNDERSTOOD - please ask the patient to repeat.")
        return out


class ClinGuard:
    def __init__(self, lexicon: Lexicon, rules: Optional[DangerRules] = None, language: str = "",
                 translate: Optional[Callable[[str], str]] = None,
                 write_note: Optional[Callable[[str, str], str]] = None):
        """
        translate(said) -> English text, used only when the lexicon has no match.
            Return "" if the speech cannot be understood.
        write_note(meaning, clinical_term) -> note text (optional).
        """
        self.lexicon = lexicon
        self.rules = rules or DangerRules()
        self.language = language
        self.translate = translate
        self.write_note = write_note

    def assess(self, said: str) -> Assessment:
        said = (said or "").strip()
        match = self.lexicon.best(said) if said else None
        if match:
            a = Assessment(said, match.entry.meaning, match.entry.clinical_term, HIGH, match.score, match=match)
        else:
            meaning = (self.translate(said) if (self.translate and said) else "") or ""
            a = Assessment(said, meaning.strip(), "", LOW if meaning.strip() else NONE, 0.0)
        a.danger_reasons = self.rules.check(
            said=said, meaning=f"{a.clinical_term} {a.meaning}",
            entry=match.entry if match else None, language=self.language)
        if self.write_note and a.confidence != NONE:
            note = self.write_note(a.meaning, a.clinical_term)
            a.note = "\n".join(a.banners() + ([""] if a.banners() else []) + [note]).strip()
        return a
