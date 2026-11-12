"""T6: recall on known phrases against false matches on unknown phrases, across thresholds.

Each utterance is scored twice: against the full lexicon (its phrase is known) and with
its own entry removed (its phrase is unknown, as in T1). For each scorer and threshold:

  known recall        = share of known utterances matched to the correct clinical term
  unknown false match = share of unknown utterances matched to a wrong clinical term
  coverage            = share of all utterances that get any match
  selective risk      = share of those matches whose clinical term is wrong

Two case sets: clean (T3 utterances, extra words only) and noisy (T6: one transcription-
noise variant plus extra words). Each scorer is allowed its own best threshold, so the
comparison does not depend on the default of 0.75. Thresholds are chosen on the same
cases, which flatters every scorer equally.

Writes results/table7_risk_coverage.csv and results/table8_recall_at_false_match.csv,
and prints a markdown section for results/summary.md.
"""
import functools

from common import CASES, CONFIG, RESULTS, SCORERS, load_lexicon, normalize, read_csv, same_term, write_csv

C = CONFIG["t6"]
THRESHOLDS = [round(C["thresholds"]["start"] + C["thresholds"]["step"] * i, 3) for i in range(C["thresholds"]["count"])]
KS = set(C["extra_words"])
SETS = {
    "clean": [c for c in read_csv(CASES / "t3_embedded_phrases.csv") if int(c["extra_words"]) in KS and int(c["seed"]) < C["seeds"]],
    "noisy": read_csv(CASES / "t6_noisy_embedded.csv"),
}
E = load_lexicon().entries
LEN = [len(normalize(e.phrase)) for e in E]


PER = {}


def curve(cls, cases):
    full = cls(entries=E, threshold=0.0)
    held = [cls(entries=E[:i] + E[i + 1:], threshold=0.0) for i in range(len(E))]
    score = functools.lru_cache(maxsize=None)(cls.score)
    rows = []
    for c in cases:
        i, text = int(c["entry_index"]), c["text"]
        cand = []
        for j, e in enumerate(E):
            s = score(text, e.phrase)
            if s >= THRESHOLDS[0]:
                cand.append((s, LEN[j], j, full._shares_informative_word(text, e.phrase),
                             j != i and held[i]._shares_informative_word(text, e.phrase)))
        cand.sort(reverse=True)            # highest score first, ties to the longer phrase
        rows.append((c["expected_term"], cand))
    per = []                       # per utterance: (entry, [known_ok per thr], [unknown_wrong per thr])
    for (term, cand), c in zip(rows, cases):
        ko, uw = [], []
        for thr in THRESHOLDS:
            f = next((x for x in cand if x[0] >= thr and x[3]), None)
            h = next((x for x in cand if x[0] >= thr and x[4]), None)
            ko.append(f is not None and same_term(E[f[2]].clinical_term, term))
            uw.append(h is not None and not same_term(E[h[2]].clinical_term, term))
        per.append((int(c["entry_index"]), ko, uw))
    PER[(cls.__name__, id(cases))] = per
    out = []
    for thr in THRESHOLDS:
        k_ok = k_wrong = u_wrong = u_same = 0
        for term, cand in rows:
            f = next((x for x in cand if x[0] >= thr and x[3]), None)
            h = next((x for x in cand if x[0] >= thr and x[4]), None)
            if f is not None:
                k_ok += same_term(E[f[2]].clinical_term, term)
                k_wrong += not same_term(E[f[2]].clinical_term, term)
            if h is not None:
                u_same += same_term(E[h[2]].clinical_term, term)
                u_wrong += not same_term(E[h[2]].clinical_term, term)
        n = len(rows)
        answered = k_ok + k_wrong + u_same + u_wrong
        out.append(dict(threshold=thr, n=n, known_correct=k_ok, known_wrong=k_wrong, unknown_wrong=u_wrong,
                        unknown_same_term=u_same, known_recall=100 * k_ok / n, unknown_false=100 * u_wrong / n,
                        coverage=100 * answered / (2 * n),
                        risk=100 * (k_wrong + u_wrong) / answered if answered else 0.0))
    return out


table, best = [], []
for set_name, cases in SETS.items():
    for name, cls in SCORERS.items():
        pts = curve(cls, cases)
        for p in pts:
            table.append([set_name, name, f"{p['threshold']:.3f}", p["n"], p["known_correct"], p["known_wrong"],
                          p["unknown_wrong"], p["unknown_same_term"], f"{p['known_recall']:.1f}",
                          f"{p['unknown_false']:.1f}", f"{p['coverage']:.1f}", f"{p['risk']:.1f}"])
        for budget in C["false_match_budgets_pct"]:
            ok = [p for p in pts if p["unknown_false"] <= budget]
            b = max(ok, key=lambda p: (p["known_recall"], -p["threshold"])) if ok else None
            best.append([set_name, name, budget, f"{b['threshold']:.3f}" if b else "",
                         f"{b['known_recall']:.1f}" if b else "", f"{b['unknown_false']:.1f}" if b else ""])
        d = next(p for p in pts if abs(p["threshold"] - CONFIG["threshold"]) < 1e-9)
        best.append([set_name, name, "default", f"{d['threshold']:.3f}", f"{d['known_recall']:.1f}", f"{d['unknown_false']:.1f}"])

write_csv(RESULTS / "table7_risk_coverage.csv",
          ["case_set", "scorer", "threshold", "utterances", "known_correct", "known_wrong", "unknown_wrong",
           "unknown_same_term", "known_recall_pct", "unknown_false_match_pct", "coverage_pct", "selective_risk_pct"], table)
write_csv(RESULTS / "table8_recall_at_false_match.csv",
          ["case_set", "scorer", "false_match_budget_pct", "threshold", "known_recall_pct", "unknown_false_match_pct"], best)

# ---------- held-out thresholds: tune on half the entries, test on the other half ----------
import random  # noqa: E402
import statistics  # noqa: E402
H = C["heldout_splits"]
rng = random.Random(H["seed"])
splits = []
for _ in range(H["repeats"]):
    idx = list(range(len(E)))
    rng.shuffle(idx)
    cut = int(len(idx) * H["tune_share"])
    splits.append(set(idx[:cut]))


def rates(per, entries, t):
    sel = [p for p in per if p[0] in entries]
    n = len(sel)
    return 100 * sum(p[1][t] for p in sel) / n, 100 * sum(p[2][t] for p in sel) / n


held_rows, held_summary = [], {}
for set_name, cases in SETS.items():
    for name, cls in SCORERS.items():
        per = PER[(cls.__name__, id(cases))]
        for budget in C["false_match_budgets_pct"]:
            test_recall, test_false, reached = [], [], 0
            for k, tune in enumerate(splits):
                test = set(range(len(E))) - tune
                ok = [(rates(per, tune, t)[0], THRESHOLDS[t], t) for t in range(len(THRESHOLDS)) if rates(per, tune, t)[1] <= budget]
                if not ok:
                    held_rows.append([set_name, name, budget, k, "", "", ""])
                    continue
                reached += 1
                _, thr, t = max(ok, key=lambda x: (x[0], x[1]))
                r, f = rates(per, test, t)
                test_recall.append(r)
                test_false.append(f)
                held_rows.append([set_name, name, budget, k, f"{thr:.3f}", f"{r:.1f}", f"{f:.1f}"])
            held_summary[(set_name, name, budget)] = (reached, test_recall, test_false)
write_csv(RESULTS / "table9_heldout_thresholds.csv",
          ["case_set", "scorer", "false_match_budget_pct", "split", "threshold_tuned", "test_recall_pct", "test_false_match_pct"], held_rows)

budgets = C["false_match_budgets_pct"]
print(f"\n## Table 7. Recall on known phrases at a fixed false-match rate on unknown phrases (T6)\n")
print(f"Each scorer uses its own best threshold. {SETS['noisy'].__len__()} noisy and {len(SETS['clean'])} clean utterances, "
      "each scored as known and as unknown. Thresholds are chosen on the same cases. Full curves: `table7_risk_coverage.csv`.\n")
for set_name in SETS:
    print(f"**{set_name.capitalize()}**" + (" (one transcription-noise variant plus extra words)" if set_name == "noisy" else " (extra words only)") + "\n")
    print("| Scorer | " + " | ".join(f"Recall at <= {b}% false matches" for b in budgets) + " | At threshold 0.75 (recall / false) |")
    print("|---|" + "---|" * (len(budgets) + 1))
    for name in SCORERS:
        r = [x for x in best if x[0] == set_name and x[1] == name]
        cells = [f"{x[4]}% (thr {x[3]})" if x[4] else "not reached" for x in r if x[2] != "default"]
        d = next(x for x in r if x[2] == "default")
        print(f"| {name} | " + " | ".join(cells) + f" | {d[4]}% / {d[5]}% |")
    print()

print(f"## Table 8. Thresholds tuned on half the entries, tested on the other half ({H['repeats']} random splits)\n")
print("Recall and false-match rate on the test half: mean, with the range across splits. "
      "\"Not reached\" means the budget could not be met on the tuning half. Per-split values: `table9_heldout_thresholds.csv`.\n")
for set_name in SETS:
    print(f"**{set_name.capitalize()}**\n")
    print("| Scorer | " + " | ".join(f"Budget {b}%: test recall / test false" for b in budgets) + " |")
    print("|---|" + "---|" * len(budgets))
    for name in SCORERS:
        cells = []
        for b in budgets:
            reached, r, f = held_summary[(set_name, name, b)]
            if not r:
                cells.append("not reached")
            else:
                cells.append(f"{statistics.mean(r):.1f} ({min(r):.1f}-{max(r):.1f}) / {statistics.mean(f):.1f} ({min(f):.1f}-{max(f):.1f})"
                             + (f", {reached} of {len(splits)} splits" if reached < len(splits) else ""))
        print(f"| {name} | " + " | ".join(cells) + " |")
    print()
cg = "ClinGuard 0.1.2"
for set_name in SETS:
    for b in budgets:
        line = []
        for name in SCORERS:
            if name == cg:
                continue
            wins = ties = total = 0
            for k in range(len(splits)):
                a = next(x for x in held_rows if x[0] == set_name and x[1] == cg and x[2] == b and x[3] == k)
                o = next(x for x in held_rows if x[0] == set_name and x[1] == name and x[2] == b and x[3] == k)
                if a[5] == "":
                    continue
                total += 1
                if o[5] == "" or float(a[5]) > float(o[5]):
                    wins += 1
                elif float(a[5]) == float(o[5]):
                    ties += 1
            line.append(f"{name} {wins}/{total}" + (f" (+{ties} ties)" if ties else ""))
        print(f"- {set_name}, budget {b}%: ClinGuard 0.1.2 has higher test recall than " + "; ".join(line) + " splits.")
print()
