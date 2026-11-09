# Adapting ClinGuard to your language

ClinGuard does not know any language by itself. Its safety comes from a lexicon written by
native speakers and danger rules approved by clinicians. This guide is the order to do things
in. Budget most of your time for steps 1, 2 and 5.

## 1. Build the lexicon with native speakers

Collect the phrases patients actually say, in the dialect your users speak, not textbook
forms. For each phrase record what it means and what a clinician would write.

| field | required | notes |
|---|---|---|
| `phrase` | yes | As patients say it. Tone marks are optional: ClinGuard ignores them when matching. |
| `meaning` | yes | Plain-English meaning, as literal as possible. |
| `clinical_term` | yes | Use **one spelling per concept** across the whole lexicon ("Headache", not also "Head ache"): two spellings count as different terms. |
| `language` | no | e.g. `yo`, `ha`, `sw` |
| `department` | no | e.g. `Antenatal` |
| `danger` | no | `true` if the phrase itself is a danger sign (decided by a clinician) |

Save it as JSON (a list of objects) or CSV with a header row. Start with the 30-60 phrases you
hear most often; include several ways of saying the same thing.

## 2. Write danger rules with clinicians

Danger checks run without any AI model. Put them in a JSON file and have a clinician approve
it:

```json
{
  "clinical_terms": ["Postpartum hemorrhage", "Eclampsia"],
  "english_keywords": ["bleeding", "seizure", "cannot breathe"],
  "local_keywords": {"yo": ["warapa", "eje pupo"]}
}
```

- `clinical_terms`: matched entries with these terms are flagged (in addition to `danger: true`).
- `english_keywords`: searched in the meaning or translation. If omitted, ClinGuard uses its
  built-in **starter list**, which is for illustration only.
- `local_keywords`: searched in what the patient said, per language.

Use it from Python with `DangerRules.from_file("rules.json")` or on the command line with
`clinguard check LEXICON "text" --rules rules.json`.

## 3. Check the lexicon for clashes

```bash
clinguard validate my_lexicon.json
```

Every entry should come back as its own best match. A problem means two entries are too
similar for the matcher to tell apart: reword, merge or remove one, then validate again.

## 4. Choose the threshold

The match threshold defaults to 0.75 (`Lexicon.from_file(path, threshold=0.75)`, or
`--threshold` on the command line). It was tuned on one Yoruba lexicon.

- Too many wrong matches: raise it.
- Too many misses on slightly misspelt phrases: lower it.
- In lexicons of 10 or more entries, a match must also share a distinctive word with the
  phrase; words used in more than 20% of entries (like "my") do not count.

Tune it with step 5, not by eye.

## 5. Evaluate on your own data

1. Run the matching evaluation:
   ```bash
   python scripts/evaluate_lexicon.py my_lexicon.json --language xx
   ```
   It reports leave-one-out wrong-term matches (how often an unknown phrase is matched to the
   wrong term) and recall on synthetic noisy variants.
2. Test on **real speech-recognition output** from your setting: record speakers saying lexicon
   phrases and new phrases, transcribe them with your recogniser, and check what ClinGuard
   returns. Synthetic variants are only a proxy.
3. Before any clinical use, run a proper evaluation with independent reference answers and
   clinical reviewers, and follow your institution's approval process.

Please share what you find, including what did not work, by
[opening an issue](https://github.com/shalini-2020/clinguard/issues).

## 6. Keep it reviewed

Use `SuggestionStore` so users can propose new phrases and a named native-speaker reviewer
approves each one. Re-run steps 3 and 5 after each batch of additions.
