"""Shared helpers for the ClinGuard experiments: paths, scorers and metrics."""
import csv
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))        # use the checkout, not an installed copy
sys.path.insert(0, str(ROOT / "scripts"))

from rapidfuzz import fuzz  # noqa: E402
import clinguard  # noqa: E402
from clinguard import Lexicon, normalize  # noqa: E402
from clinguard.safety import DangerRules  # noqa: E402

CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
LEXICON_PATH = HERE / CONFIG["lexicon"]
RULES_PATH = HERE / CONFIG["danger_rules"]
CASES, RESULTS, FIGURES = HERE / "cases", HERE / "results", HERE / "figures"


def same_term(a: str, b: str) -> bool:
    return a.strip().lower() == b.strip().lower()


# ---------- scorers ----------
def _plain(fn):
    return staticmethod(lambda text, phrase: fn(normalize(text), normalize(phrase)) / 100.0)


def _length_aware(text, phrase):
    """ClinGuard 0.1.1 scoring: length-aware, no coverage factor."""
    t, p = normalize(text), normalize(phrase)
    if not t or not p:
        return 0.0
    if len(p) <= len(t):
        return max(fuzz.token_set_ratio(t, p), fuzz.partial_ratio(t, p)) / 100.0
    return max(fuzz.ratio(t, p), fuzz.token_sort_ratio(t, p)) / 100.0


class _NoFilter(Lexicon):
    def _shares_informative_word(self, text, phrase):
        return True


class EditDistance(_NoFilter):
    score = _plain(fuzz.ratio)


class TokenSet(_NoFilter):
    score = _plain(fuzz.token_set_ratio)


class Partial(_NoFilter):
    score = _plain(fuzz.partial_ratio)


class ClinGuard011(_NoFilter):
    score = staticmethod(_length_aware)


class CoverageOnly(_NoFilter):
    """Current score (with coverage factor), informative-word filter removed."""


class FilterOnly(Lexicon):
    """0.1.1 score (no coverage factor), informative-word filter kept."""
    score = staticmethod(_length_aware)


SCORERS = {                       # name -> Lexicon class
    "Edit-distance ratio": EditDistance,
    "Token-set ratio": TokenSet,
    "Partial ratio": Partial,
    "ClinGuard 0.1.1": ClinGuard011,
    "ClinGuard 0.1.3": Lexicon,   # the library, unmodified
}
ABLATION = {
    "Neither (0.1.1)": ClinGuard011,
    "Informative-word filter only": FilterOnly,
    "Coverage factor only": CoverageOnly,
    "Both (0.1.3)": Lexicon,
}


def load_lexicon(cls=Lexicon, threshold=None):
    thr = CONFIG["threshold"] if threshold is None else threshold
    base = Lexicon.from_file(LEXICON_PATH, language=CONFIG["language"], threshold=thr)
    return cls(entries=base.entries, threshold=thr)


def load_rules():
    d = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    rules = DangerRules(clinical_terms=d["glossary_terms"], english_keywords=d["english_keywords"],
                        local_keywords={CONFIG["language"]: d["yoruba_keywords"]})
    return rules, {t.lower() for t in d["glossary_terms"]}


# ---------- metrics ----------
def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"),) * 2
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def mcnemar_exact(b, c):
    """Two-sided exact McNemar p-value from the two discordant counts."""
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(0, min(b, c) + 1)) / 2 ** n)


# ---------- files ----------
def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, header, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
