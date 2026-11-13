# ClinGuard

[![tests](https://github.com/shalini-2020/clinguard/actions/workflows/tests.yml/badge.svg)](https://github.com/shalini-2020/clinguard/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/clinguard)](https://pypi.org/project/clinguard/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24090330.svg)](https://doi.org/10.5281/zenodo.24090330)

**Safety-first building blocks for clinical voice AI in low-resource languages and dialects.**

Mainstream speech and translation tools work poorly for many of the world's languages and
dialects. In healthcare, a misunderstood symptom can become a wrong note, and a wrong note can
harm a patient. ClinGuard gives developers the safety layer around their AI: a native-speaker
lexicon that grounds meaning, rule-based danger-sign checks that never depend on the AI, clear
confidence levels, and a human-reviewed learning loop.

ClinGuard is **model-agnostic**. It does not call any AI provider. Plug in any speech recogniser,
translator or note generator as plain Python functions.

```bash
pip install clinguard
```

## Why

| Problem | What ClinGuard does |
|---|---|
| Speech recognition writes dialect speech with varying tone marks and spellings | Normalises tone marks and accents; tolerant, length-aware fuzzy matching |
| A short phrase like "it hurts" can hide inside an unrelated question | **Coverage-aware scoring**: a phrase that explains only part of what was said scores lower; matches must share a distinctive word, not just "my" or "me" |
| General translators misread dialect phrases | **Lexicon first**: meaning comes from a glossary curated by native speakers |
| AI output can look confident when it is wrong | Every result carries a confidence level: `high` (lexicon), `low` (fallback), `none` |
| Emergencies must never be missed because of an AI error | **Rule-based danger-sign check**, independent of any model |
| Lexicons are never complete | **Human-in-the-loop learning**: users suggest, a trusted reviewer approves, with a full audit trail |

## Quick start

```python
from clinguard import ClinGuard, DangerRules, Lexicon

lexicon = Lexicon.from_file("my_lexicon.json", language="yo")

guard = ClinGuard(
    lexicon,
    DangerRules(local_keywords={"yo": ["warapa"]}),   # rules reviewed by your clinicians
    language="yo",
    translate=my_translate,      # optional: your model, used only when the lexicon has no match
    write_note=my_note_writer,   # optional: your note generator
)

a = guard.assess("Orí mi ń fọ́ mi")      # text from any speech recogniser
a.confidence      # "high"
a.clinical_term   # "Headache"
a.danger          # False
a.needs_review    # False
a.banners()       # [] or e.g. ["URGENT - possible danger sign ...", "LOW CONFIDENCE ..."]
```

See [`examples/quickstart.py`](examples/quickstart.py) for a runnable demo.

## Lexicon format

JSON (a list of objects) or CSV with a header row:

| field | required | meaning |
|---|---|---|
| `phrase` | yes | what the patient says, in the local language or dialect |
| `meaning` | yes | plain-English meaning |
| `clinical_term` | yes | the term a clinician would record |
| `language` | no | language code, e.g. `yo`, `ha`, `sw` |
| `department` | no | context, e.g. `Antenatal` |
| `danger` | no | `true` if this phrase is a danger sign |

Check a lexicon for clashing entries before deploying:

```bash
clinguard validate my_lexicon.json
clinguard check my_lexicon.json "Mi ò le mí" --language yo
```

## Human-in-the-loop learning

```python
from clinguard import SuggestionStore

store = SuggestionStore("lexicon_reviews/")
sid = store.submit("Ese mi n wu", "My leg is swelling", "Leg swelling (edema)", language="yo")
store.review(sid, approve=True, reviewer="Native-speaker reviewer")   # reviewer name is required
lexicon = lexicon.extend(store.approved_entries("yo"))
```

Suggestions and decisions are stored in append-only JSON Lines files, so every change to the
lexicon can be traced to a person and a time.

## Adapting ClinGuard to your language

See [docs/ADAPTING.md](docs/ADAPTING.md): building a lexicon with native speakers, writing
danger rules with clinicians, choosing a threshold, checking for clashes, and evaluating on
your own data before any use.

## Evaluation

What has been measured so far is **matching behaviour on a lexicon**, not clinical accuracy.
Reproduce it with:

```bash
python scripts/evaluate_lexicon.py path/to/lexicon.json --language yo
```

Results on a 60-entry Ekiti Yoruba clinical lexicon
([`experiments/data/ekiti_yoruba_lexicon.json`](experiments/data/ekiti_yoruba_lexicon.json),
sha256 prefix `6a3ac864d6bdabda`), seed 0:

| Measure | 0.1.1 | 0.1.3 |
|---|---|---|
| Leave-one-out wrong-term matches (lower is better) | 32 / 60 | 2 / 60 |
| Recall on synthetic noisy variants | 176 / 178 | 177 / 178 |

- Of the two remaining wrong-term matches, one is a lexicon inconsistency ("Headache" vs
  "Head ache" as clinical terms for the same concept) and one is a genuine error: "Ara mi dun mi"
  (chest pain) matched "Acute pain".
- Noisy variants are synthetic (tone marks removed, one letter changed, two words run
  together); recall varies slightly with the random seed (176-177 / 178 for seeds 0-3).
  They are a proxy for speech-recognition errors, not a substitute for real recordings.
- A blinded clinical evaluation with nurses, comparing a ClinGuard-based pipeline with the
  same LLM on its own, is in preparation. No clinical results are available yet.

## Research and validation

Evidence is listed by kind, and only once it exists.

| Kind | Status |
|---|---|
| Technical evaluation | Five reproducible text-level tests with four baseline scorers, an ablation and a threshold sweep: [experiments/](experiments/README.md). Negative findings are in [experiments/LIMITATIONS.md](experiments/LIMITATIONS.md). |
| Independent clinical evaluation | Not yet done. A blinded nurse evaluation is designed and awaits facility authorisation. |
| External replication | None yet. |
| Deployment | Integrated in a healthcare startup's clinical voice app, used in simulated sessions with no real patients. No clinical deployment. |
| Publications | None yet. |

## Limitations

- **Coverage:** meaning comes from the lexicon. Phrases it does not contain go to your
  fallback translator and are marked low confidence.
- **One complaint per assessment:** `assess` returns the best single lexicon match. If a
  speaker mentions several complaints, only one is interpreted; applications should handle the
  rest (for example by asking the user, or an extra fallback check).
- **Speech recognition:** ClinGuard works on text. Badly transcribed speech can still match
  the wrong entry or nothing at all.
- **Danger rules:** the built-in English keywords are a starter list. Local danger rules must
  be written and approved by clinicians for each setting.
- **Thresholds and word checks** were tuned on one Yoruba lexicon; other languages and
  lexicon sizes may need different settings (see the adaptation guide).
- **Not clinically validated** and not a medical device (see the safety notice below).

## Used in

- **A healthcare startup's clinical voice app**: ClinGuard grew out of, and powers the safety
and lexicon layer of, a voice app that turns Ekiti Yoruba patient speech into structured nurse
handoff notes. Since November 2026 it is in a **simulated-use pilot** at a partner facility
(nurses acting out patient scenarios, no real patients), with a formal blinded evaluation in
preparation. The app and ClinGuard were developed by the same author, so this is a first
deployment, not independent adoption.

Using or evaluating ClinGuard in your project, including results that did not work well?
Please [open an issue](https://github.com/shalini-2020/clinguard/issues) to tell us.

## Safety notice

ClinGuard is a toolkit, not a medical device. The built-in English danger keywords are a starter
list for illustration only. Every deployment must have its lexicon and danger rules reviewed and
approved by qualified clinicians, and a clinician must review AI-assisted output before it is used
in care. The example lexicon is illustrative and not clinically validated.

## Contributing

Issues and pull requests are welcome, especially lexicons and danger-sign rules for new
languages, reviewed by native speakers and clinicians. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Citing

If you use ClinGuard in research, please cite it. Each release is archived on Zenodo:

- All versions (always resolves to the latest): [10.5281/zenodo.24090330](https://doi.org/10.5281/zenodo.24090330)
- Version 0.1.3 (the version evaluated in the experiments package): [10.5281/zenodo.24200952](https://doi.org/10.5281/zenodo.24200952)

> Sivasamy, S. (2026). *ClinGuard: safety-first building blocks for clinical voice AI in
> low-resource languages and dialects* [Computer software]. Zenodo.
> https://doi.org/10.5281/zenodo.24090330

Citation metadata is also in [CITATION.cff](CITATION.cff) (GitHub shows a "Cite this repository" button).

## Changelog

- **0.1.3 (13 Nov 2026)**: Documentation and packaging release; matching behaviour is
  unchanged from 0.1.2 and every reported result reproduces exactly. Adds the reproducible
  experiments package (`experiments/`), describes the host application generically, and
  renames the experiment data files to `ekiti_yoruba_lexicon.json` and `danger_rules.json`
  (contents unchanged).
- **0.1.2 GitHub release and Zenodo archive (9 Nov 2026)**: Package code identical to the
  0.1.2 package on PyPI, plus documentation and tooling added afterwards: reproducible evaluation script (`scripts/evaluate_lexicon.py`), limitations,
  adaptation guide, citation file, contributing guide and automated tests. The 0.1.2 noisy-variant
  figures below were measured on a variant set that was not saved; they are replaced by the
  reproducible figures in the Evaluation section (the leave-one-out figures reproduce exactly).
- **0.1.2**: Fewer false matches. A short lexicon phrase found inside a longer
  utterance is scored by how much of the utterance it explains, and (in
  lexicons of 10+ entries) a match must share a distinctive word. On a
  60-entry Ekiti Yoruba lexicon, leave-one-out wrong-term matches fell from
  32 to 2 (reproducible, see Evaluation). As originally reported, recall on noisy
  variants was 176/179 (was 178/179); see the note above. Source files
  restored to the repository.
- **0.1.1**: First public release.

## License

Apache License 2.0. Created by Shalini Sivasamy.
