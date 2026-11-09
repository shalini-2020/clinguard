"""
Reproducible matching evaluation for a ClinGuard lexicon.

    python scripts/evaluate_lexicon.py LEXICON.json [--language yo] [--seed 0]

Two measures, both deterministic (same lexicon + seed -> same numbers):

1. Leave-one-out wrong-term matches (false matches).
   Each entry is removed in turn and its own phrase is matched against the rest of the
   lexicon. The ideal answer is "no match" (or an entry with the same clinical term).
   A match to a DIFFERENT clinical term is a wrong-term match: the kind of error that turns
   an unknown phrase into a confident wrong note.

2. Recall on noisy variants (robustness).
   For each entry, up to three variants imitate speech-recognition noise:
     a. tone marks, accents and capitals removed, punctuation added
     b. one letter changed in one word (spelling error)
     c. two neighbouring words run together (word-boundary error)
   A variant counts as recalled when the full lexicon's best match has the entry's clinical
   term. Variants identical to the original phrase after normalisation are skipped.

Limitations: synthetic variants are a proxy for real speech-recognition output, not a
substitute for testing on real recordings. Results depend on the lexicon.
"""
import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

try:
    import clinguard
    from clinguard import Lexicon, normalize
except ImportError:  # running from a source checkout
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    import clinguard
    from clinguard import Lexicon, normalize

LETTERS = "abdefgiklmnoprstuwy"


def _same_term(a: str, b: str) -> bool:
    return a.strip().lower() == b.strip().lower()


def variants(phrase: str, rnd: random.Random) -> list:
    words = normalize(phrase).split()
    out = []
    # a. marks and case removed, punctuation added
    out.append(("no tone marks", " ".join(words).capitalize() + "."))
    # b. one letter changed in one word of 3+ letters
    long_words = [i for i, w in enumerate(words) if len(w) >= 3]
    if long_words:
        i = rnd.choice(long_words)
        w = words[i]
        j = rnd.randrange(len(w))
        new = rnd.choice([c for c in LETTERS if c != w[j]])
        changed = words[:i] + [w[:j] + new + w[j + 1:]] + words[i + 1:]
        out.append(("one letter changed", " ".join(changed)))
    # c. two neighbouring words run together
    if len(words) >= 2:
        i = rnd.randrange(len(words) - 1)
        merged = words[:i] + [words[i] + words[i + 1]] + words[i + 2:]
        out.append(("words run together", " ".join(merged)))
    return [(kind, v) for kind, v in out if normalize(v) != normalize(phrase) or kind == "no tone marks"]


def evaluate(path: str, language: str = "", seed: int = 0) -> dict:
    lexicon = Lexicon.from_file(path, language=language)
    entries = lexicon.entries
    wrong, same, abstained, wrong_examples = 0, 0, 0, []
    for i, e in enumerate(entries):
        rest = Lexicon(entries=entries[:i] + entries[i + 1:], threshold=lexicon.threshold)
        m = rest.best(e.phrase)
        if m is None:
            abstained += 1
        elif _same_term(m.entry.clinical_term, e.clinical_term):
            same += 1
        else:
            wrong += 1
            wrong_examples.append(f"{e.phrase!r} ({e.clinical_term}) -> {m.entry.clinical_term} [{m.score:.2f}]")

    rnd = random.Random(seed)
    recalled, total, by_kind, misses = 0, 0, {}, []
    for e in entries:
        for kind, v in variants(e.phrase, rnd):
            m = lexicon.best(v)
            ok = m is not None and _same_term(m.entry.clinical_term, e.clinical_term)
            total += 1
            recalled += ok
            k = by_kind.setdefault(kind, [0, 0])
            k[0] += ok
            k[1] += 1
            if not ok:
                misses.append(f"{v!r} ({e.clinical_term}) -> {m.entry.clinical_term if m else 'no match'}")
    data = Path(path).read_bytes()
    return {
        "clinguard_version": clinguard.__version__,
        "lexicon": Path(path).name,
        "lexicon_sha256": hashlib.sha256(data).hexdigest()[:16],
        "entries": len(entries),
        "threshold": lexicon.threshold,
        "seed": seed,
        "leave_one_out": {"wrong_term": wrong, "same_term": same, "no_match": abstained,
                          "wrong_examples": wrong_examples},
        "noisy_variant_recall": {"recalled": recalled, "total": total,
                                 "by_kind": {k: f"{a}/{b}" for k, (a, b) in by_kind.items()},
                                 "misses": misses},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    ap.add_argument("lexicon")
    ap.add_argument("--language", default="")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", action="store_true", help="print the full result as JSON")
    args = ap.parse_args()
    r = evaluate(args.lexicon, args.language, args.seed)
    if args.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return
    loo, rec = r["leave_one_out"], r["noisy_variant_recall"]
    print(f"ClinGuard {r['clinguard_version']} | {r['lexicon']} (sha256 {r['lexicon_sha256']}) | "
          f"{r['entries']} entries | threshold {r['threshold']} | seed {r['seed']}")
    print(f"Leave-one-out: wrong-term matches {loo['wrong_term']} / {r['entries']} "
          f"(same-term {loo['same_term']}, no match {loo['no_match']})")
    print(f"Noisy-variant recall: {rec['recalled']} / {rec['total']}  "
          + ", ".join(f"{k} {v}" for k, v in rec["by_kind"].items()))


if __name__ == "__main__":
    main()
