"""T7: do the danger rules distinguish an active danger sign from a negated, past or
hypothetical mention?

40 hand-written English sentences (cases/t7_negation_english.csv): 10 danger concepts,
each stated as an active complaint, negated, historical and hypothetical. They stand for
the English meaning an LLM would produce on a lexicon miss, so the rules are run with no
lexicon entry. The sentences and expected labels (active danger sign or not) were written
for this test and have NOT been reviewed by a clinician. Yoruba negation is not tested.

Writes results/table10_t7_negation.csv and prints a markdown section.
"""
from common import CASES, CONFIG, RESULTS, load_rules, read_csv, write_csv

rules, _ = load_rules()
cases = read_csv(CASES / "t7_negation_english.csv")
rows, by_form = [], {}
for c in cases:
    reasons = rules.check(said="", meaning=c["english_meaning"], entry=None, language=CONFIG["language"])
    flagged = bool(reasons)
    rows.append([c["case_id"], c["concept"], c["form"], c["english_meaning"], c["expected_active_danger"], int(flagged),
                 "; ".join(str(r) for r in reasons)])
    t = by_form.setdefault(c["form"], [0, 0])
    t[0] += 1
    t[1] += flagged
write_csv(RESULTS / "table10_t7_negation.csv",
          ["case_id", "concept", "form", "english_meaning", "expected_active_danger", "flagged", "reasons"], rows)
print("## Table 9. Negated, past and hypothetical mentions (T7)\n")
print("40 hand-written English meanings, run through the danger rules with no lexicon entry. "
      "Sentences and expected labels written for this test; not yet reviewed by a clinician.\n")
print("| Form | Sentences | Flagged as danger | Expected |\n|---|---|---|---|")
for form in ("affirmative", "negated", "historical", "hypothetical"):
    n, f = by_form[form]
    print(f"| {form} | {n} | {f} | {'all' if form == 'affirmative' else 'none'} |")
fa = sum(by_form[f][1] for f in ("negated", "historical", "hypothetical"))
na = sum(by_form[f][0] for f in ("negated", "historical", "hypothetical"))
print(f"\nFalse alarms on non-active mentions: {fa} of {na}. Active complaints missed: "
      f"{by_form['affirmative'][0] - by_form['affirmative'][1]} of {by_form['affirmative'][0]}.")
missed = [r for r in rows if r[2] == "affirmative" and not r[5]]
if missed:
    print("Missed active complaints: " + "; ".join(f"\"{r[3]}\"" for r in missed) + ".")
print()
