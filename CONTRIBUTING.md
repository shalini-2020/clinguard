# Contributing to ClinGuard

Thank you for helping. ClinGuard is safety-related software, so a few rules matter more than
usual.

## Reporting use, results and problems

- **Using or evaluating ClinGuard?** Please open an issue describing your setting, language and
  what you found, including results that were poor. This is the most useful contribution of all.
- **Bugs:** include the ClinGuard version, a minimal example and what you expected.

## Lexicons and danger rules

- Lexicon entries must come from, or be checked by, **native speakers of the dialect**.
- Danger rules and any `danger: true` entries must be **approved by a qualified clinician**.
  Name the reviewers' roles (not personal details) in the pull request.
- Use one spelling per clinical term across a lexicon.
- Run `clinguard validate` and `python scripts/evaluate_lexicon.py` and paste the output.
- Never include real patient data, names or recordings.

## Code

1. Fork, create a branch, and install with `pip install -e ".[dev]"`.
2. Add or update tests in `tests/`; run `pytest`.
3. Keep ClinGuard model-agnostic: it must not call any AI provider itself.
4. Changes to matching or danger checks: include before/after figures from
   `scripts/evaluate_lexicon.py` on at least one lexicon.

By contributing you agree that your contribution is licensed under Apache 2.0.
