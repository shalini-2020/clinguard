"""Dialect lexicon: maps local-language phrases to clinical meanings.

Matching is designed for noisy speech-recognition output:
  * tone marks and accents are ignored
  * small spelling differences are tolerated (fuzzy matching)
  * length-aware scoring stops a short phrase (e.g. "it hurts") from counting
    as a full match for a long, specific sentence, and vice versa
  * on equal scores the longer, more specific phrase wins
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable, List, Optional, Union

from rapidfuzz import fuzz

from .normalize import normalize


@dataclass(frozen=True)
class Entry:
    """One lexicon entry."""
    phrase: str                       # what the patient says, in the local language/dialect
    meaning: str                      # plain-English meaning
    clinical_term: str                # term a clinician would record
    language: str = ""                # e.g. "yo", "ha", "sw"
    department: str = ""              # optional context, e.g. "Antenatal"
    danger: bool = False              # True if this phrase is a danger sign
    source: str = "curated"           # "curated" or "learned"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Match:
    entry: Entry
    score: float                      # 0.0 - 1.0


@dataclass
class Lexicon:
    entries: List[Entry] = field(default_factory=list)
    threshold: float = 0.75           # minimum score to count as a match

    # ---------- loading ----------
    @classmethod
    def from_records(cls, records: Iterable[dict], language: str = "", threshold: float = 0.75) -> "Lexicon":
        """Build from dicts. Accepts ClinGuard keys (phrase, meaning, clinical_term) or the
        BeaGrace-style keys (dialect_expression, literal_meaning, english_medical_term)."""
        entries = []
        for r in records:
            phrase = r.get("phrase") or r.get("dialect_expression") or ""
            if not phrase.strip():
                continue
            entries.append(Entry(
                phrase=phrase.strip(),
                meaning=(r.get("meaning") or r.get("literal_meaning") or "").strip(),
                clinical_term=(r.get("clinical_term") or r.get("english_medical_term") or "").strip(),
                language=(r.get("language") or language or "").strip(),
                department=(r.get("department") or "").strip(),
                danger=str(r.get("danger", "")).lower() in ("true", "1", "yes"),
                source=(r.get("source") or "curated").strip(),
            ))
        return cls(entries=entries, threshold=threshold)

    @classmethod
    def from_file(cls, path: Union[str, Path], language: str = "", threshold: float = 0.75) -> "Lexicon":
        """Load a .json (list of objects) or .csv (header row) lexicon file."""
        path = Path(path)
        if path.suffix.lower() == ".csv":
            with path.open(encoding="utf-8-sig", newline="") as f:
                records = list(csv.DictReader(f))
        else:
            records = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_records(records, language=language, threshold=threshold)

    def extend(self, entries: Iterable[Entry]) -> "Lexicon":
        """Return a new lexicon with extra entries (e.g. reviewer-approved phrases)."""
        return Lexicon(entries=self.entries + list(entries), threshold=self.threshold)

    def to_records(self) -> List[dict]:
        return [e.to_dict() for e in self.entries]

    def __len__(self) -> int:
        return len(self.entries)

    # ---------- matching ----------
    @staticmethod
    def score(text: str, phrase: str) -> float:
        """Similarity between what was said and a lexicon phrase (0.0 - 1.0)."""
        t, p = normalize(text), normalize(phrase)
        if not t or not p:
            return 0.0
        if len(p) <= len(t):
            # lexicon phrase is shorter: look for it anywhere inside what was said
            s = max(fuzz.token_set_ratio(t, p), fuzz.partial_ratio(t, p))
        else:
            # patient said less than the phrase: compare the whole thing
            s = max(fuzz.ratio(t, p), fuzz.token_sort_ratio(t, p))
        return s / 100.0

    def matches(self, text: str, limit: Optional[int] = None) -> List[Match]:
        """All entries scoring at or above the threshold, best first."""
        found = [Match(e, self.score(text, e.phrase)) for e in self.entries]
        found = [m for m in found if m.score >= self.threshold]
        found.sort(key=lambda m: (m.score, len(normalize(m.entry.phrase))), reverse=True)
        return found[:limit] if limit else found

    def best(self, text: str) -> Optional[Match]:
        top = self.matches(text, limit=1)
        return top[0] if top else None

    # ---------- quality checks ----------
    def self_check(self) -> List[str]:
        """Problems where an entry does not come back as its own best match.
        Run this after adding phrases, to catch clashes between entries."""
        problems = []
        for e in self.entries:
            top = self.best(e.phrase)
            if top is None or top.entry.clinical_term != e.clinical_term:
                got = top.entry.clinical_term if top else "no match"
                problems.append(f'"{e.phrase}" -> expected {e.clinical_term!r}, got {got!r}')
        return problems
