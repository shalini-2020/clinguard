# Limitations and negative findings

This report states what the experiments in this directory do not show, and the weaknesses
they found. It is part of the results, not a disclaimer.

## What these experiments are

Five text-level tests of ClinGuard 0.1.2 on one 60-entry Ekiti Yoruba clinical lexicon and
its danger rules. They are deterministic and anyone can rerun them.

## What they do not measure

- **Clinical accuracy.** No test checks whether a note is correct or safe to act on.
- **Speech.** No audio and no speech recogniser are involved. Letter substitutions, joined
  words and padding words imitate recognition errors; they are not samples of them.
- **The LLM.** No test calls a language model. Nothing here compares ClinGuard with an
  LLM-only pipeline on the same input.
- **Real unseen speech.** "Held-out" phrases (T1) are lexicon phrases with their own entry
  removed, not new phrases collected from patients or other dialect speakers.
- **Generalisation.** One lexicon, one dialect, one set of danger rules. Many entries are
  long sentences, which stresses substring matching more than a lexicon of short terms would.

## Negative findings

1. **Off the lexicon, the danger rules miss most danger signs (T4).** When the lexicon does
   not match, keyword rules flag 14 of 30 danger-marked phrases given a faithful
   translation, and 7 of 30 given none. The 16 misses are danger signs that need clinical
   inference, not a keyword (for example swollen feet in pregnancy, or a swollen painful
   calf). Danger coverage therefore depends mainly on the lexicon.
2. **Recognition falls as speech gets freer (T3).** With four extra words around a known
   phrase, 86.5% are recognised; with six, 67.1%; with eight, 58.3%. The rest are
   abstentions, which send the utterance to the less trusted LLM path.
3. **Findings 1 and 2 compound.** Each abstention also loses the lexicon's danger coverage.
4. **A second complaint can be lost (T5).** Of 600 utterances containing a danger-marked
   and a non-danger phrase, 87 were reported with high confidence as the non-danger
   complaint alone. Best-match selection returns one entry per utterance.
5. **The danger rules cannot tell an active complaint from a negated, past or hypothetical
   one (T7).** On 40 English meanings, all 10 active complaints were flagged, but so were all
   30 negated, historical and hypothetical mentions ("I am not bleeding", "I had chest pain
   last year", "Is vomiting blood dangerous?"). Keyword rules have no notion of negation or
   time. The test sentences and labels have not been reviewed by a clinician, and Yoruba
   negation was not tested.
6. **ClinGuard's advantage depends on the threshold and on noise (T6).** When every scorer
   may choose its own threshold:
   - On clean text (extra words, no spelling noise), a partial-ratio matcher set to 0.975
     recognises 100% of known phrases at no more than 3% false matches, against 90.5% for
     ClinGuard. ClinGuard is ahead only under the strictest budget (1%).
   - With spelling noise as well, ClinGuard has the highest recall at 1% and 3% false
     matches, but a partial-ratio matcher recognises more at 5%, and plain edit-distance
     similarity recognises more when no false matches at all are allowed (65.8% against
     28.8%).
   - Plain edit-distance similarity is as precise as ClinGuard on T1 and T2 (3 against 2
     wrong-term matches; 178 against 177 variants recalled).
   The comparisons at the default threshold of 0.75 (T1, T3) overstate ClinGuard's lead over
   substring matching. With thresholds tuned on half the entries and tested on the other half
   (50 splits), the pattern holds but varies widely: with spelling noise, ClinGuard had higher
   test recall than edit distance in 40 of 50 splits at the 1% budget, and than partial ratio
   in 38 of 50 at 3% but only 22 of 50 at 5%. Test false-match rates ranged from 0% to over
   10% around each budget.
7. **The informative-word filter adds little on this lexicon.** The coverage factor alone
   gives 4 wrong-term matches; adding the filter gives 2 and loses one noisy variant.
8. **The default threshold is not the safest.** At 0.80 to 0.85 wrong-term matches fall to
   1 and 0 with no loss on T2. The default of 0.75 was set before these tests.
9. **Two wrong-term matches remain in T1,** one of which reflects an inconsistent label in
   the lexicon ("Headache" and "Head ache"). The same label caused the one T5 utterance
   that matched neither of its two phrases.

## Caveats on individual tests

- **T6** in-sample results choose each scorer's best threshold on the cases they report,
  which flatters every scorer equally; the held-out splits (Table 8) give fairer estimates.
- **Substring scorers cannot meet some budgets at any threshold** because an unknown
  utterance that contains another entry's short phrase word for word scores exactly 1.00.
- **T7** sentences are short and written in plain English; real LLM translations may phrase
  negation and time differently.
- **T3** draws padding words from other lexicon phrases. This may be harder or easier than
  real speech.
- **T4** takes the deployment's own danger list as ground truth. That list is marked as an
  initial list awaiting clinical approval. Condition B uses curated meanings, which are
  cleaner than real LLM translations, so it is an upper bound.
- **T4 contains no negated or hypothetical statements.** Its zero false-alarm count is not a
  general false-alarm rate; T7 shows the rules do raise false alarms on such statements.
- **Removing tone marks** merges words that differ only in tone. How often this merges
  clinically distinct phrases has not been measured.
- **Single author.** The method, tests and baselines were written by the same person.

## What would address these

An independent, blinded clinical evaluation on recorded speech with reference answers from
reviewers who never see system output; test phrases collected independently by native
speakers; a second lexicon in another language; and replication by another group.
