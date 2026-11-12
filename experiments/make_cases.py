"""Generate the synthetic test cases and freeze them as CSV files in experiments/cases/.

The frozen files are committed. Run this only to check that they can be regenerated
(python experiments/make_cases.py --check) or after changing config.json or the lexicon.

T1 (held-out phrases) and T4 (danger rules by path) use the lexicon entries directly and
need no synthetic cases.
"""
import random
import sys

from common import CASES, CONFIG, load_lexicon, normalize, read_csv, write_csv
import evaluate_lexicon as ev   # scripts/evaluate_lexicon.py: the published variant generator

lex = load_lexicon()
E = lex.entries


def t2_cases(seed):
    rnd = random.Random(seed)
    rows = []
    for i, e in enumerate(E):
        for kind, text in ev.variants(e.phrase, rnd):
            rows.append([f"T2-{len(rows) + 1:03d}", i, e.clinical_term, kind, text])
    return rows


def t3_cases():
    rows = []
    for k in CONFIG["t3"]["extra_words"]:
        for s in range(CONFIG["t3"]["seeds"]):
            rnd = random.Random(1000 * k + s)
            for i, e in enumerate(E):
                own = normalize(e.phrase).split()
                pool = [w for o in E if o is not e for w in normalize(o.phrase).split() if w not in set(own)]
                extra = [rnd.choice(pool) for _ in range(k)]
                cut = rnd.randint(0, k)
                rows.append([f"T3-{len(rows) + 1:05d}", i, e.clinical_term, k, s, " ".join(extra[:cut] + own + extra[cut:])])
    return rows


def t6_cases():
    """Noisy and embedded: one transcription-noise variant of the phrase, then k extra words."""
    rows = []
    for k in CONFIG["t6"]["extra_words"]:
        for s in range(CONFIG["t6"]["seeds"]):
            rnd = random.Random(50000 + 1000 * k + s)
            for i, e in enumerate(E):
                vs = ev.variants(e.phrase, rnd)
                kind, v = rnd.choice(vs) if vs else ("none", e.phrase)
                own = set(normalize(e.phrase).split())
                pool = [w for o in E if o is not e for w in normalize(o.phrase).split() if w not in own]
                extra = [rnd.choice(pool) for _ in range(k)]
                cut = rnd.randint(0, k)
                rows.append([f"T6-{len(rows) + 1:05d}", i, e.clinical_term, k, s, kind,
                             " ".join(extra[:cut] + [normalize(v)] + extra[cut:])])
    return rows


def t5_cases():
    from common import load_rules
    _, danger_terms = load_rules()
    D = [i for i, e in enumerate(E) if e.clinical_term.lower() in danger_terms]
    N = [i for i, e in enumerate(E) if e.clinical_term.lower() not in danger_terms]
    pairs = [(a, b) for a in D for b in N]
    random.Random(CONFIG["t5"]["seed"]).shuffle(pairs)
    rows = []
    for a, b in pairs[:CONFIG["t5"]["pairs"]]:
        for order in ("danger first", "danger second"):
            first, second = (a, b) if order == "danger first" else (b, a)
            rows.append([f"T5-{len(rows) + 1:04d}", a, b, E[a].clinical_term, E[b].clinical_term, order,
                         f"{E[first].phrase} {E[second].phrase}"])
    return rows


FILES = {
    "t2_noisy_variants.csv": (["case_id", "entry_index", "expected_term", "kind", "text"], lambda: t2_cases(CONFIG["t2"]["seed"])),
    "t3_embedded_phrases.csv": (["case_id", "entry_index", "expected_term", "extra_words", "seed", "text"], t3_cases),
    "t6_noisy_embedded.csv": (["case_id", "entry_index", "expected_term", "extra_words", "seed", "noise", "text"], t6_cases),
    "t5_two_complaints.csv": (["case_id", "danger_entry", "other_entry", "danger_term", "other_term", "order", "text"], t5_cases),
}

if __name__ == "__main__":
    check = "--check" in sys.argv
    ok = True
    for name, (header, make) in FILES.items():
        rows = [[str(x) for x in r] for r in make()]
        if check:
            frozen = [[r[h] for h in header] for r in read_csv(CASES / name)]
            same = frozen == rows
            ok &= same
            print(("identical " if same else "DIFFERENT ") + name, len(rows), "cases")
        else:
            write_csv(CASES / name, header, rows)
            print("wrote", name, len(rows), "cases")
    sys.exit(0 if ok else 1)
