"""Danger-sign rules that run independently of any AI model.

A danger sign is flagged if ANY of these is true:
  * the matched lexicon entry is marked danger=True, or its clinical term is listed
  * a local-language keyword appears in what the patient said
  * an English keyword appears in the meaning / translation

The default English keywords are a STARTER LIST for illustration only.
Every deployment must have its rules reviewed and approved by clinicians.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Union

from .lexicon import Entry
from .normalize import normalize

STARTER_ENGLISH_KEYWORDS = [
    "bleeding", "losing blood", "vomiting blood",
    "not moving", "cannot feel the baby", "can't feel the baby",
    "can't breathe", "cannot breathe", "difficulty breathing", "suffocating",
    "seizure", "fits", "convulsion", "unconscious", "passing out", "fainted",
    "chest pain", "poison", "snake bite", "snake bit",
    "stroke", "cannot move", "can't move", "face drooping",
    "hurt myself", "kill myself", "suicide",
]


@dataclass
class DangerRules:
    clinical_terms: List[str] = field(default_factory=list)
    english_keywords: List[str] = field(default_factory=lambda: list(STARTER_ENGLISH_KEYWORDS))
    local_keywords: Dict[str, List[str]] = field(default_factory=dict)   # language code -> keywords

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "DangerRules":
        """JSON with any of: clinical_terms, english_keywords, local_keywords {lang: [...]}."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            clinical_terms=data.get("clinical_terms", data.get("glossary_terms", [])),
            english_keywords=data.get("english_keywords", list(STARTER_ENGLISH_KEYWORDS)),
            local_keywords=data.get("local_keywords", {}),
        )

    def check(self, said: str = "", meaning: str = "", entry: Optional[Entry] = None,
              language: str = "") -> List[str]:
        """Return the reasons a danger sign was detected (empty list = none)."""
        reasons: List[str] = []
        terms = {t.lower() for t in self.clinical_terms}
        if entry is not None and (entry.danger or entry.clinical_term.lower() in terms):
            reasons.append(entry.clinical_term)
        said_n = f" {normalize(said)} "
        for word in self.local_keywords.get(language, []) if language else _flatten(self.local_keywords):
            if f" {normalize(word)} " in said_n:
                reasons.append(f'"{word}"')
        meaning_n = f" {normalize(meaning)} "
        for word in self.english_keywords:
            if f" {normalize(word)} " in meaning_n:
                reasons.append(f'"{word}"')
        return list(dict.fromkeys(reasons))


def _flatten(d: Dict[str, Iterable[str]]) -> List[str]:
    return [w for words in d.values() for w in words]
