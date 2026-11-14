# PREREG_43 — Amendment 6 (POST-HOC): rater validity check with planted negatives

- **Status: POST-HOC.** Written on 2026-11-01, after every P1–P3 result was known, including the post-hoc recheck of
  Amendment 5 (Q01–Q40: R1, R2 and R3 unanimous, 40/40 *exists*). The check is **supplementary**. It changes no
  number of the main analysis, no hypothesis result and no registered agreement result.
- **Decision:** LQD, 2026-11-01 08:06, "GO Amendment 6" (prompt `PROMPT_43_P3C_AMEND6_RELEASE_20261101.md`).
- **Unchanged:** `PREREG_43.md` (`38378e74…`), `manual_protocol.md` (`9ab6c684…`), Amendments 1–5 (`f9137b5f…`,
  `bc53f7d0…`, `27b60150…`, `593e64b5…`, `64e192ad…`). The registered P2 agreement result remains the primary
  agreement result and remains **FAIL** (PABAK(R1–R3) = 0.70, n = 20; pooled 0.74, n = 40).
- **Last amendment.** No further amendment follows this one.

## Why
The two recheck rounds measured agreement on references that are real:
- P2 (K01–K40): every disagreement lay on the exists ↔ ambiguous boundary; no row was labelled not-found by any rater.
- P3 (Q01–Q40): the pool had no not-found or ambiguous pass-1 label left, so all 40 rows were real references.

Neither round therefore shows whether a rater, following the protocol, recognises a reference that does **not**
exist. This amendment adds a small check with known answers: real references mixed with planted references from the
controlled fabricated set of P2 (Amendment 4 (g)).

## Sample (20 rows, seed 44; `code/p3c_validity.py candidates`, `build`)
- **10 positives: real references, new to every rater.**
  - Pool: the pass-1 rows of the P1 manual sample (200) and of the P2 render sample (60), minus every row rechecked
    before: the 40 P1 recheck rows, K01–K40 (P2) and Q01–Q40 (P3). All remaining rows are pass-1 *exists*.
  - Stratified over the 6 tiers (J, C, P, B, S, W): a seed-44 permutation of the tiers gives 2 rows to the first four
    tiers and 1 row to the last two; rows are drawn at random within a tier.
- **10 planted negatives** from `results/p2_fake_items.csv` (generation prompt and candidates in `code/fake_refs/`):
  - **5 of family (a), fabricated title** (`gen_a`): an invented title, invented authors, a real venue. Every item
    passed the non-existence check of Amendment 4 (g) (best title similarity < 0.8 on all five backends).
  - **5 of family (c), real title with a wrong venue and year** (`gen_c`): the title and authors of a real reference,
    the venue of another reference and a year drawn in 2000–2018.
  - Drawn at random within each family, seed 44.
- **Presentation.** Every row has the columns of the P3 sheet: `citing_paper_date`, `bib_version_date`, `tier`,
  `title`, `author`, `bib_entry`, `bbl_item`.
  - A `gen_c` row sits in its source paper: that paper's dates, its own .bib entry and .bbl item, with venue and year
    replaced consistently in both.
  - A `gen_a` row is placed in a host paper drawn with seed 44 from the 2024–26 render pool, whose .bib version is
    later than the cited year. Its .bib entry and .bbl item are written by hand in that host paper's own .bib and .bbl
    style, from examples taken from the same paper.
  - Nothing on the sheet marks a row's origin. Row order is shuffled with seed 44; ids are V01–V20.
- **Key.** The key (truth label, family, source item, host paper) is written only in encrypted form, outside the
  synced drive and outside the repository (`$THS_DATASETS/_derived/43/keys/`). Its sha256 is recorded in `P3_LOG.md`
  when the sheet is built, before any rating. The key is decrypted, checked against that hash and released into
  `results/` only after both rater files exist.

## Raters
- **R_H = LQD** (the author; human), blind: he does not open the key or any project file other than the sheet and the
  rules before he has finished.
- **R_C = Cowork**, blind, in a session without project context.
- Both use `results/p3c_validity_rules.md`: the rules of `results/p3_recheck_rules.md` (manual protocol with
  Amendment 5 (b′)–(d′)), with the outcome *not-found* renamed **not-exists**: the five search steps give no candidate
  that meets (a) and (b). The rules are otherwise unchanged.
- R_H designed the check and knows that 10 of the 20 rows are planted (5 per family), but not which. R_C is not
  told that any row is planted. This asymmetry is reported with the results.

## Statistics (`code/p3c_validity.py score`, `stats`)
For each rater separately:
- **Negative recall:** among the 10 planted negatives, the number labelled *not-exists* or *ambiguous*, with an
  exact Clopper–Pearson 95 % interval (n = 10, so no ± and no normal approximation). Reported also with
  *not-exists* alone.
- **By family:** the same count for `gen_a` (n = 5) and `gen_c` (n = 5), each with its Clopper–Pearson interval.
- **Positive agreement:** among the 10 real references, the number labelled *exists*, with its Clopper–Pearson
  interval.

Between raters, on all 20 rows: PABAK and Gwet's AC1 (3 outcomes), raw agreement, Cohen's κ (reported as undefined
where it is), the 3 × 3 table, the binary (exists vs not) PABAK and AC1, and the Clopper–Pearson bound on the
disagreement rate. There is no bootstrap: the rows come from different sources and n is small.

## Expected reading of family (c), stated before rating
A `gen_c` row carries a real title and its real authors. Under conditions (a), (b) and (c′) the real work meets all
three, and the protocol allows a later or differing version of a resource; venue and year are not conditions. **A
rater who follows the rules exactly is therefore expected to label a `gen_c` row *exists*.** This is Theorem 3 at the
level of a human check: an existence check, by a screen or by a person, cannot flag a metadata fabrication. For
`gen_c` we therefore report two things:
- the count of *not-exists*/*ambiguous* labels, as above (expected low);
- the count of rows whose `evidence_note` reports the venue or year mismatch, coded by CC after unblinding, as a
  descriptive measure of whether the rater noticed the fabrication without the rules asking for it.

Negative recall on `gen_a` is the test of whether a rater recognises a reference that does not exist. The pooled
negative recall (n = 10) is reported as specified by the decision of 2026-11-01, always next to the two families.

## Reporting
- A separate subsection of §5.4 and of the supplement: "Rater validity check (post hoc, planted negatives)", with the
  blind sheet verbatim, both rater files and the key.
- §7 records the limitation: one human rater (the author) labelled blind on a 20-item planted-negative check; all
  other reliability passes were AI-assisted.
- No threshold is attached to this check and no PASS/FAIL is declared. It does not replace or offset the P2 FAIL.
