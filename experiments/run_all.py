"""Score every test and write the result tables.

    python experiments/run_all.py

Reads the frozen cases in experiments/cases/ and the frozen lexicon and rules in
experiments/data/. Writes one CSV per table to experiments/results/ and a readable
summary to experiments/results/summary.md. Deterministic: same inputs, same outputs.
"""
import hashlib
import random
import statistics

from common import (ABLATION, CASES, CONFIG, LEXICON_PATH, RESULTS, RULES_PATH, SCORERS, clinguard,
                    load_lexicon, load_rules, mcnemar_exact, read_csv, same_term, wilson, write_csv)
import evaluate_lexicon as ev
import rapidfuzz

THR = CONFIG["threshold"]
summary = []


def say(line=""):
    summary.append(line)


def pct(k, n):
    return f"{100 * k / n:.1f}"


# ---------- T1: held-out wrong-term matches ----------
def t1(cls, thr=THR):
    lex = load_lexicon(cls, thr)
    E = lex.entries
    out = []                                   # per entry: "wrong" | "same" | "none"
    for i, e in enumerate(E):
        m = cls(entries=E[:i] + E[i + 1:], threshold=thr).best(e.phrase)
        out.append("none" if m is None else ("same" if same_term(m.entry.clinical_term, e.clinical_term) else "wrong"))
    return out


# ---------- T2: noisy variants ----------
def t2(cls, cases, thr=THR):
    lex = load_lexicon(cls, thr)
    hits = []
    for c in cases:
        m = lex.best(c["text"])
        hits.append(m is not None and same_term(m.entry.clinical_term, c["expected_term"]))
    return hits


def t2_seed_sweep(cls, n):
    lex = load_lexicon(cls)
    rates = []
    for seed in range(n):
        rnd = random.Random(seed)
        ok = tot = 0
        for e in lex.entries:
            for _, v in ev.variants(e.phrase, rnd):
                m = lex.best(v)
                tot += 1
                ok += m is not None and same_term(m.entry.clinical_term, e.clinical_term)
        rates.append(ok / tot)
    return rates


t2_cases = read_csv(CASES / "t2_noisy_variants.csv")
rows, t1_detail = [], {}
for name, cls in SCORERS.items():
    o = t1(cls)
    t1_detail[name] = o
    h = t2(cls, t2_cases)
    lo, hi = wilson(o.count("wrong"), len(o))
    rows.append([name, o.count("wrong"), o.count("same"), o.count("none"), len(o), pct(o.count("wrong"), len(o)),
                 f"{100 * lo:.1f}", f"{100 * hi:.1f}", sum(h), len(h), pct(sum(h), len(h))])
write_csv(RESULTS / "table1_t1_t2_scorers.csv",
          ["scorer", "t1_wrong_term", "t1_same_term", "t1_no_match", "t1_n", "t1_wrong_pct", "t1_wilson95_low", "t1_wilson95_high",
           "t2_recalled", "t2_n", "t2_recall_pct"], rows)
say("## Table 1. Held-out wrong-term matches (T1) and noisy-variant recall (T2)\n")
say("| Scorer | T1 wrong-term (of 60) | 95% interval | T2 recalled (of 178) |\n|---|---|---|---|")
for r in rows:
    say(f"| {r[0]} | {r[1]} | {r[6]}-{r[7]}% | {r[8]} |")
a, b = t1_detail["ClinGuard 0.1.1"], t1_detail["ClinGuard 0.1.2"]
fixed = sum(x == "wrong" and y != "wrong" for x, y in zip(a, b))
new = sum(x != "wrong" and y == "wrong" for x, y in zip(a, b))
say(f"\nPaired, 0.1.1 vs 0.1.2 on the same 60 phrases: {fixed} errors removed, {new} introduced; "
    f"exact McNemar p = {mcnemar_exact(fixed, new):.2g}.")
lex = load_lexicon()
E = lex.entries
wrong_rows = []
for i, (e, o) in enumerate(zip(E, b)):
    if o == "wrong":
        m = type(lex)(entries=E[:i] + E[i + 1:], threshold=THR).best(e.phrase)
        wrong_rows.append([e.phrase, e.clinical_term, m.entry.clinical_term, f"{m.score:.2f}"])
write_csv(RESULTS / "t1_remaining_wrong_matches.csv", ["phrase", "its_term", "matched_term", "score"], wrong_rows)
say("\nRemaining wrong-term matches for 0.1.2: " + "; ".join(f"{r[1]} -> {r[2]} ({r[3]})" for r in wrong_rows) + ".")

# seed sweep
n_seeds = CONFIG["t2"]["seed_sweep"]
rows = []
for name in ("ClinGuard 0.1.1", "ClinGuard 0.1.2"):
    r = t2_seed_sweep(SCORERS[name], n_seeds)
    rows.append([name, n_seeds, f"{100 * statistics.mean(r):.2f}", f"{100 * min(r):.2f}", f"{100 * max(r):.2f}"])
write_csv(RESULTS / "t2_seed_sweep.csv", ["scorer", "seeds", "mean_recall_pct", "min_recall_pct", "max_recall_pct"], rows)
say(f"\nT2 over seeds 0-{n_seeds - 1}: " + "; ".join(f"{r[0]} mean {r[2]}% (min {r[3]}, max {r[4]})" for r in rows) + ".")

# ---------- ablation ----------
rows = []
for name, cls in ABLATION.items():
    o, h = t1(cls), t2(cls, t2_cases)
    rows.append([name, o.count("wrong"), len(o), sum(h), len(h), len(load_lexicon(cls).self_check())])
write_csv(RESULTS / "table2_ablation.csv", ["configuration", "t1_wrong_term", "t1_n", "t2_recalled", "t2_n", "self_check_problems"], rows)
say("\n## Table 2. Ablation of the two matching safeguards\n")
say("| Configuration | T1 wrong-term (of 60) | T2 recalled (of 178) |\n|---|---|---|")
for r in rows:
    say(f"| {r[0]} | {r[1]} | {r[3]} |")

# ---------- threshold sweep ----------
rows = []
for thr in CONFIG["threshold_sweep"]:
    for name in ("ClinGuard 0.1.1", "ClinGuard 0.1.2"):
        o, h = t1(SCORERS[name], thr), t2(SCORERS[name], t2_cases, thr)
        rows.append([f"{thr:.2f}", name, o.count("wrong"), len(o), sum(h), len(h)])
write_csv(RESULTS / "table3_threshold_sweep.csv", ["threshold", "scorer", "t1_wrong_term", "t1_n", "t2_recalled", "t2_n"], rows)
say("\n## Table 3. Threshold sweep\n")
say("| Threshold | 0.1.1 T1 wrong | 0.1.1 T2 | 0.1.2 T1 wrong | 0.1.2 T2 |\n|---|---|---|---|---|")
for i in range(0, len(rows), 2):
    say(f"| {rows[i][0]} | {rows[i][2]} | {rows[i][4]} | {rows[i + 1][2]} | {rows[i + 1][4]} |")

# ---------- T3: embedded phrases ----------
t3_cases = read_csv(CASES / "t3_embedded_phrases.csv")
rows = []
for name, cls in SCORERS.items():
    lex_s = load_lexicon(cls)
    tally = {}
    for c in t3_cases:
        m = lex_s.best(c["text"])
        res = "abstain" if m is None else ("correct" if same_term(m.entry.clinical_term, c["expected_term"]) else "wrong")
        t = tally.setdefault(int(c["extra_words"]), {"correct": 0, "wrong": 0, "abstain": 0})
        t[res] += 1
    for k in sorted(tally):
        t = tally[k]
        n = sum(t.values())
        rows.append([name, k, n, t["correct"], t["wrong"], t["abstain"], pct(t["correct"], n), pct(t["wrong"], n), pct(t["abstain"], n)])
write_csv(RESULTS / "table4_t3_embedded_phrases.csv",
          ["scorer", "extra_words", "n", "correct", "wrong", "abstain", "correct_pct", "wrong_pct", "abstain_pct"], rows)
ks = CONFIG["t3"]["extra_words"]
say("\n## Table 4. Embedded-phrase recall (T3): correct match, % of 1200 utterances\n")
say("| Scorer | " + " | ".join(f"k={k}" for k in ks) + " |\n|---|" + "---|" * len(ks))
for name in SCORERS:
    say(f"| {name} | " + " | ".join(r[6] for r in rows if r[0] == name) + " |")
cg = [r for r in rows if r[0] == "ClinGuard 0.1.2"]
say("\nClinGuard 0.1.2 wrong-term rate by k: " + ", ".join(f"{r[7]}%" for r in cg) + "; abstentions: " + ", ".join(f"{r[8]}%" for r in cg) + ".")

# ---------- T4: danger rules by path ----------
rules, danger_terms = load_rules()
lang = CONFIG["language"]
records = __import__("json").loads(LEXICON_PATH.read_text(encoding="utf-8"))
truth = [e.clinical_term.lower() in danger_terms for e in E]


def flagged(cond, e, rec):
    if cond == "A":
        m = lex.best(e.phrase)
        return bool(rules.check(said=e.phrase, meaning=f"{e.clinical_term} {e.meaning}", entry=m.entry if m else None, language=lang))
    if cond == "B":
        return bool(rules.check(said=e.phrase, meaning=e.meaning, entry=None, language=lang))
    return bool(rules.check(said=e.phrase, meaning="", entry=None, language=lang))


LABELS = {"A": "A: lexicon hit", "B": "B: miss, faithful translation", "C": "C: miss, no translation"}
rows, detail = [], []
for cond in "ABC":
    pred = [flagged(cond, e, r) for e, r in zip(E, records)]
    tp = sum(p and t for p, t in zip(pred, truth))
    fp = sum(p and not t for p, t in zip(pred, truth))
    fn = sum((not p) and t for p, t in zip(pred, truth))
    tn = sum((not p) and (not t) for p, t in zip(pred, truth))
    rows.append([LABELS[cond], tp, fn, fp, tn, f"{tp / (tp + fn):.3f}", f"{tp / (tp + fp):.3f}" if tp + fp else ""])
    for e, t, p in zip(E, truth, pred):
        detail.append([cond, e.clinical_term, e.meaning, int(t), int(p)])
write_csv(RESULTS / "table5_t4_danger_rules.csv", ["condition", "flagged_tp", "missed_fn", "false_alarms_fp", "true_negatives", "recall", "precision"], rows)
write_csv(RESULTS / "t4_danger_rules_per_entry.csv", ["condition", "clinical_term", "meaning", "danger_marked", "flagged"], detail)
say("\n## Table 5. Danger-sign rules by pipeline path (T4), 30 of 60 entries danger-marked\n")
say("| Condition | Flagged (of 30) | Missed | False alarms | Recall |\n|---|---|---|---|---|")
for r in rows:
    say(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[5]} |")
say("\nDanger-marked entries missed in condition B (lexicon miss, faithful translation):\n")
for d in detail:
    if d[0] == "B" and d[3] and not d[4]:
        say(f"- {d[1]}: \"{d[2]}\"")

# ---------- T5: two complaints ----------
t5_cases = read_csv(CASES / "t5_two_complaints.csv")
from clinguard import ClinGuard  # noqa: E402
guard = ClinGuard(lex, rules, language=lang)          # no translation function
rows = []
for order in ("danger first", "danger second"):
    cs = [c for c in t5_cases if c["order"] == order]
    t = {"flagged": 0, "danger": 0, "other": 0, "none": 0, "wrong": 0}
    for c in cs:
        r = guard.assess(c["text"])
        t["flagged"] += r.danger
        if r.match is None:
            t["none"] += 1
        elif same_term(r.match.entry.clinical_term, c["danger_term"]):
            t["danger"] += 1
        elif same_term(r.match.entry.clinical_term, c["other_term"]):
            t["other"] += 1
        else:
            t["wrong"] += 1
    rows.append([order, len(cs), t["flagged"], pct(t["flagged"], len(cs)), t["danger"], t["other"], t["none"], t["wrong"]])
write_csv(RESULTS / "table6_t5_two_complaints.csv",
          ["order", "n", "danger_flagged", "danger_flagged_pct", "best_match_danger_entry", "best_match_other_entry", "no_match", "wrong_entry"], rows)
say("\n## Table 6. Two complaints in one utterance (T5)\n")
say("| Order | Utterances | Danger flagged | Best match: danger entry | Other entry | A third entry | No match |\n|---|---|---|---|---|---|---|")
for r in rows:
    say(f"| {r[0]} | {r[1]} | {r[2]} ({r[3]}%) | {r[4]} | {r[5]} | {r[7]} | {r[6]} |")
third = []
for c in t5_cases:
    r = guard.assess(c["text"])
    if r.match is not None and not same_term(r.match.entry.clinical_term, c["danger_term"]) and not same_term(r.match.entry.clinical_term, c["other_term"]):
        third.append(f"{c['order']}: matched \"{r.match.entry.clinical_term}\" for a pair of \"{c['danger_term']}\" and \"{c['other_term']}\"")
say("\nUtterances matched to a third entry: " + ("; ".join(third) if third else "none") + ".")

# ---------- T6: recall against false matches (separate script) ----------
import subprocess, sys  # noqa: E402
t6 = subprocess.run([sys.executable, str(RESULTS.parent / "t6_risk_coverage.py")], capture_output=True, text=True, check=True)
summary.extend(t6.stdout.rstrip().splitlines())
t7 = subprocess.run([sys.executable, str(RESULTS.parent / "t7_negation.py")], capture_output=True, text=True, check=True)
summary.append("")
summary.extend(t7.stdout.rstrip().splitlines())

# T5 detail: every utterance accounted for
say("")

# ---------- header ----------
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()[:16]
head = ["# ClinGuard experiment results", "",
        "Generated by `python experiments/run_all.py`. Do not edit by hand.", "",
        f"- ClinGuard {clinguard.__version__}, RapidFuzz {rapidfuzz.__version__}",
        f"- Lexicon: {len(E)} entries, {len({e.clinical_term.lower() for e in E})} distinct clinical terms, SHA-256 `{sha(LEXICON_PATH)}`",
        f"- Danger rules: SHA-256 `{sha(RULES_PATH)}`",
        f"- Threshold {THR}; cases: T2 {len(t2_cases)}, T3 {len(t3_cases)}, T5 {len(t5_cases)}, T6 noisy 1200, T7 40",
        "- Text-level tests only. See `../LIMITATIONS.md`.", ""]
(RESULTS / "summary.md").write_text("\n".join(head + summary) + "\n", encoding="utf-8")
print("\n".join(head + summary))
