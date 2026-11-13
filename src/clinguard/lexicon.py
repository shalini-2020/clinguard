"""Dialect lexicon: maps local-language phrases to clinical meanings.

Matching is designed for noisy speech-recognition output:
  * tone marks and accents are ignored
  * small spelling differences are tolerated (fuzzy matching)
  * length-aware scoring stops a short phrase (e.g. "it hurts") from counting
    as a full match for a long, specific sentence, and vice versa
  * coverage: a short phrase found inside a much longer utterance only explains
    part of it, so its score is reduced (e.g. "it hurts" inside "will this
    injection hurt?" is no longer a confident "acute pain" match)
  * informative words: in larger lexicons, a match must share at least one
    distinctive word with the phrase, not only very common words such as
    "my" or "me" that appear in many entries
  * on equal scores the longer, more specific phrase wins
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from collections import Counter
from typing import Dict, Iterable, List, Optional, Union

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


# A word found in more than this share of entries is "common" (like "my", "me")
COMMON_WORD_SHARE = 0.2
# The informative-word check needs enough entries for word counts to mean anything
MIN_ENTRIES_FOR_WORD_CHECK = 10


@dataclass
class Lexicon:
    entries: List[Entry] = field(default_factory=list)
    threshold: float = 0.75           # minimum score to count as a match
    _common: Optional[frozenset] = field(default=None, init=False, repr=False, compare=False)

    # ---------- loading ----------
    @classmethod
    def from_records(cls, records: Iterable[dict], language: str = "", threshold: float = 0.75) -> "Lexicon":
        """Build from dicts. Accepts ClinGuard keys (phrase, meaning, clinical_term) or the
        glossary-style keys (dialect_expression, literal_meaning, english_medical_term)."""
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
        """Similarity between what was said and a lexicon phrase (0.0 - 1.0),
        reduced when the phrase covers only part of a longer utterance."""
        t, p = normalize(text), normalize(phrase)
        if not t or not p:
            return 0.0
        if len(p) <= len(t):
            # lexicon phrase is shorter: look for it anywhere inside what was said
            s = max(fuzz.token_set_ratio(t, p), fuzz.partial_ratio(t, p)) / 100.0
            # ...but it only explains part of the utterance: scale by coverage
            coverage = min(1.0, len(p.split()) / len(t.split()))
            s *= 0.5 + 0.5 * coverage
        else:
            # patient said less than the phrase: compare the whole thing
            s = max(fuzz.ratio(t, p), fuzz.token_sort_ratio(t, p)) / 100.0
        return s

    def common_words(self) -> frozenset:
        """Words that appear in many entries and so say little about meaning."""
        if self._common is None:
            counts: Dict[str, int] = Counter()
            for e in self.entries:
                counts.update(set(normalize(e.phrase).split()))
            limit = max(2, COMMON_WORD_SHARE * len(self.entries))
            self._common = frozenset(w for w, n in counts.items() if n > limit)
        return self._common

    def _shares_informative_word(self, text: str, phrase: str) -> bool:
        """True if a distinctive word of the phrase appears (allowing small
        spelling differences or words run together) in what was said."""
        if len(self.entries) < MIN_ENTRIES_FOR_WORD_CHECK:
            return True
        common = self.common_words()
        words = [w for w in normalize(phrase).split() if w not in common and len(w) > 1]
        if not words:
            return True   # phrase made only of common words: nothing to check
        said = normalize(text).split()
        joined = "".join(said)
        for w in words:
            if w in joined or any(fuzz.ratio(w, s) >= 80 for s in said):
                return True
        return False

    def matches(self, text: str, limit: Optional[int] = None) -> List[Match]:
        """All entries scoring at or above the threshold, best first."""
        found = []
        for e in self.entries:
            s = self.score(text, e.phrase)
            if s >= self.threshold and self._shares_informative_word(text, e.phrase):
                found.append(Match(e, s))
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
