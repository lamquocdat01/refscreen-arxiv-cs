# PREREG_43 — Amendment 8 (POST-HOC): withdrawal of the human arms; automated ground truth and false-positive bounds

- **Status: POST-HOC.** Written on 2026-11-08 (about 09:15 UTC), after every P1–P3 result, after the independent review
  (Reviewer 2) of manuscript v1.2 and after cascade passes 1–4 of Amendment 7 (a). It is hashed before any key is
  decrypted, before any decoy is generated, before any sample of this amendment is drawn and before any request of the
  deep search is sent.
- **Decision:** LQD, 2026-11-08 14:32 ICT (request to drop manual review and measurement) and 15:50 ICT
  (`CP3c_DECISION_43_20261108.md`, all six questions as proposed in `PLAN_43_v4_NO_MANUAL_20261108.md` §6).
- **Unchanged files (not edited):** `PREREG_43.md` (`38378e74…`), `manual_protocol.md` (`9ab6c684…`), Amendments 1–5
  (`f9137b5f…`, `bc53f7d0…`, `27b60150…`, `593e64b5…`, `64e192ad…`), Amendment 6 (`424a8d00…`), Amendment 7
  (`df36318bd95e48dce29c4325e5dcc7e84112ecaeea65444294217a782b7d0e55`), Addendum A
  (`10f8b213472fcd79f742c8e0403d17c3b7df4f2a17660652a34f0411610c1aff`), Addendum 2
  (`e4c9f26b64c2df205de53d70f4f1b3ad7ab7d4d643c43fa533c1bd93bc1c269c`), Addendum 3
  (`30e0c789aff31278f125053de7bc68510ba69b688260621b43500b2f6f81bcc9`).

## What had been run or seen when this amendment was written

- **Cascade (Amendment 7 (a), Addenda A and 2).** Passes 1–4 had run. Academic (J/C/P) 2019–21: complete, 291/291
  targets answered. Academic 2024–26: 823/1,412 answered, 589 left; pass 5 is scheduled for 2026-11-09T00:10Z.
  Non-academic targets of 2019–21 (B/S/W): 24 of 771 answered, 747 left. State file:
  `$THS_DATASETS/_derived/43/p3e_groundtruth_refs_full.csv`, sha256 `c59897543b3ca874…`, written 2026-11-08T04:35Z.
- **Counts known from that file (distinct references, def 1).**

  | Period | J unres. | C unres. | P unres. | B unres. | S unres. | W unres. |
  |---|---:|---:|---:|---:|---:|---:|
  | 2019–21 | 126 | 69 | 16 | 61 | 59 | 719 |
  | 2024–26 (interim) | 409 | 260 | 160 | 300 | 599 | 2,459 |

  The 2024–26 counts are interim: 73 of the 829 academic unresolved references still lack an OpenAlex answer.
  The non-academic counts are likewise interim until (H) is finished.
- **Known interim results.** Every interim full-cascade rate and verdict of `results/*_p3e.*`, including the
  exploratory similarity-threshold sweep of Amendment 7 (d) 1. **The choice of the 0.80 threshold in (D) was made
  after that sweep was seen.** The reviewer's objections Q1, Q2, Q5 and Q11 were known.
- **AI rater R_B.** R_B's file `results/p3e_human_rB.csv` exists (`722c1e94…`). Only its marginal label counts (62 exists,
  5 not-exists, 1 ambiguous) had been seen. It had not been scored, and neither its rows nor its evidence were compared
  with any key.
- **No key decrypted, no decoy generated, no sample of this amendment drawn, no deep-search request sent.**

## (A) Withdrawal of the human arms

**Withdrawn:** Amendment 7 (b) as far as it concerns R_H1 and R_H2, Addendum 3 in full, and Amendment 7 (c) in full.

**Reasons.**
1. Decision of the author on 2026-11-08.
2. The only human rater available is the author, who is not independent (Reviewer 2, Q2).
3. No second human rater is available before the deadline.

**State at withdrawal.**
- `p3e_human_key.csv.enc` (plaintext sha256 `b4bba6e0f361bc56b203fea1339fbad6c038eefbb327aced8fd563f204266fd7`) and
  `p3e_tier_key.csv.enc` (plaintext sha256 `472ee104526bec86f1f3ee4e669672ecb6e764e32f3f4e370ddcad1aa68b1e14`) **had
  never been decrypted.**
- **No human label has been read.** `results/p3e_human_rH1.csv` and `results/p3e_tier_rH1.csv` do not exist.
- The form `results/p3e_human_rH1_form.csv` has the sha256 it had when issued (below). It therefore has no filled
  cell. This was established from the hash alone; the file was not opened.

**Files issued, each withdrawn and not scored for any human arm:**

| File | sha256 |
|---|---|
| `results/p3e_human_sheet.csv` | `b97720564dadc7bd7a6756c6fafbdc15a52df0da2cf16e0ef2d9bc3479977b8d` |
| `results/p3e_human_rules.md` | `63e4b101f36f91f3e9a9f56c033e780341fa3c7258984f951190af7794deed73` |
| `results/p3e_human_rH1_form.csv` | `5ab35b0b16897cddf4641ede47b5cf6d377a0a5fda7b284e2ecb8dc917605e13` |
| `results/p3e_evidence_pack.csv` | `4869241244e73aace3194185d7e3a392ef651123530e9af58c72185a46d1b51b` |
| `P3E/evidence_pack.md` | `df091164ca4099845a2da65f1f3a63fe570cb219a7f88fbb4fab6e8facc0d173` |
| `P3E/HOW_TO_RATE_RH1.md` | `6a467f48d868cc5f3e7d67d46627f631061df290533811865feee9967610a2e1` |
| `results/p3e_tier_sheet.csv` | `2f2a9d097050ad93f351b8b6959e768c6d0130f59cb49abfc6c7b544c365bfc8` |
| `results/p3e_tier_guide.md` | `8a3a58fad1d13f21fedbb883ae9e7e2855ccce0fa98f33d06913e3e3d8bf89cc` |

If a human file appears later, only its sha256 and its number of non-empty cells are recorded. Its content is not read.

**Use.** No inference in the paper rests on labels assigned by a human or by an AI rater. The tier key is not decrypted at
any point: nothing in this amendment needs it.

## (B) AI-rater characterisation (Supplement only)

R_B (`results/p3e_human_rB.csv`, `722c1e94855fb294d0e490c08f12362bc45272491fb79cd57b3499c81a2ee763`) is scored with the
metric definitions of Amendment 6 §Statistics and §"Expected reading of family (c)". The key `p3e_human_key.csv.enc` is
decrypted for this purpose and checked against its plaintext hash; a mismatch stops the step. Amendment 6's key (plaintext
`c024336b…`) is decrypted for the V rows.

- Negative recall on `gen_a` (n = 5): rows labelled not-exists or ambiguous; also not-exists alone.
- `gen_c` (n = 5), the two ways of Amendment 6: the count of not-exists/ambiguous labels, and the count of rows whose
  `evidence_note` reports the venue or year mismatch.
- *Exists* share on the 10 real V rows.
- *Exists* share and *ambiguous* share on the 48 flagged rows.
- Clopper–Pearson 95 % for every proportion.
- PABAK and Gwet's AC1 between AI raters on V01–V20, **only if** earlier AI labels of V01–V20 exist on disk. (At the
  time of writing no such file is present, so this item is expected to be reported as "not available".)
- Limits of R_B stated with the result: DBLP was behind a bot wall during rating, and three rows were rated leniently
  according to R_B's own notes.

Reported only in the Supplement.

## (C) Ground truth

- **GT-1 (provenance).** Every reference of the 2019–21 corpus is taken to be real, consistent with the assumption
  π ≈ 0 of H5.
- **GT-2 (certified-real).** PREREG §3, unchanged.
- **GT-3 (automated deep search).** Section (D).

## (D) GT-3 deep search

**Sets.**
- **(i) `acad1921`:** every distinct academic (J, C, P) reference of 2019–21 with def-1 state *unresolved* under the full
  cascade. Official count, fixed now: **211 (J 126, C 69, P 16)**, from the state file above. This set is complete:
  every member has its OpenAlex answer.
- **(ii) `acad2426`:** the same definition for 2024–26, fixed when the cascade of Addendum 2 has finished or at
  2026-11-12T23:59Z. A reference still lacking a cascade answer at that time is not in (ii) and is reported separately.
- **(iii) `decoy`:** section (E).
- **(iv) `posctl`:** section (F).
- **(v) `nonacad1921` (exploratory):** every distinct B, S and W reference of 2019–21 unresolved under the cascade.
  A reference that (H) later resolves is dropped from (v) at reporting time.

**Query string.**
- A reference's `.bbl` item, when the citing paper's source has one for its cite key, taken from
  `ground_truth.bbl_items` (LaTeX commands removed by `refmatch.strip_latex`), whitespace collapsed.
- Otherwise the string built from the `.bib` fields with the fixed template, verbatim:
  **`"{authors}. {title}. {venue}, {year}."`**
  - `authors` = the `author` field after `strip_latex`, with " and " replaced by ", ";
  - `title` = the reference's title;
  - `venue` = the first non-empty of `journal`, `booktitle`, `publisher`, `howpublished`, `institution`;
  - `year` = the `year` field, or the first four digits of `date`.
  - A missing field is omitted together with its punctuation.
- The string is cut at 500 characters (the limit the registered code applies to a Crossref query).

**Reference fields used by the rule.**
- `title`: the title column of the ground-truth file (`.bib` title, or the GROBID-parsed title for a `.bbl`-only reference).
- Surnames: `refmatch.bib_surnames` on the author column. For a `.bbl`-only reference this is GROBID's first-author surname
  only.
- Year: the `.bib` year. For a `.bbl`-only reference: the `(YYYY)` of the natbib `\bibitem[…]` label, else biblatex
  `\field{year}`, else the last token matching 19xx/20xx after URLs, DOIs, arXiv identifiers and page ranges are removed.
  If none is found the reference has no year.

**Sources, in this order; the search stops at the first source with a candidate that meets the rule:**
1. Crossref: `query.bibliographic=<query string>`, `rows=5`, `select=DOI,title,subtitle,issued,author,type`.
2. DBLP dump offline (`code/dblp_offline.py`, same release as Amendment 3), top 5 by title similarity. Run only when
   free RAM ≥ 6 GB.
3. arXiv API: `search_query=all:<normalised title>`, `max_results=5`.
4. Semantic Scholar: `paper/search?query=<normalised title>&limit=5&fields=title,year,authors,venue,publicationTypes,externalIds`.
5. OpenAlex: `search=<normalised title>`, `per-page=5`.

Candidate titles are compared with `refmatch.title_sim`. Among candidates of one source that meet the rule, the one
with the highest similarity is recorded.

**Match rule.** A candidate matches if all hold:
- title similarity ≥ 0.80;
- at least one `.bib` surname (ASCII-folded) occurs as a whole token in the candidate's author names;
- |`.bib` year − candidate year| ≤ 1.

A reference with no author drops the second condition and needs similarity ≥ 0.90. A reference with no year drops the
third condition and needs similarity ≥ 0.90. A candidate with no author list or no year cannot meet the corresponding
condition when the reference has that field.

**Tier S and W.** The first http(s) URL found in `url`, `howpublished` or `note` (for a `.bbl`-only reference, in the
item text) is checked.
- *found* if a HEAD request returns 2xx or 3xx (redirects are not followed; if HEAD is refused, a GET with streaming that is
  closed without reading the body), timeout 15 s, **or** the Wayback CDX API returns a capture with status 200 and a
  timestamp not later than the arXiv version date of the citing paper (`src_version_date`, `data_manifest/manifest_src_version.csv`).
- A live URL shows that a resource exists at that address, not that it is the cited document. This limit is reported.
- A reference without a URL goes through the title rule above.

**Tier B.** Same title rule.

**State of each reference.**
- *found*: recorded with source, similarity, whether the author and year conditions held, record id, record type.
- *not found*: every source answered and none has a matching candidate.
- *unanswered*: no matching candidate and at least one source failed after back-off.
- *Unanswered* references **count in R** (conservative for the lower bound) and are reported separately.
- A request is tried up to 3 times with exponential back-off. A later pass (`--resume`) asks only requests with no
  stored answer. States are computed at reporting time from the stored answers.
- For arXiv and Semantic Scholar: after 25 consecutive failed requests the pass stops asking that source; the next
  pass is at least 60 minutes later, at most 3 passes per source and set.

**Search-depth breakdown** of each *found* reference, first match in this order:
1. *full string:* source is Crossref and the matched DOI is not among the candidates of the cascade's stored Crossref title query for
   that reference;
2. *threshold band:* similarity in [0.80, 0.90);
3. *source or candidate beyond the cascade's top:* the match has similarity ≥ 0.90 and comes from an endpoint the cascade
   did not use for that reference (arXiv `all:`, S2 `paper/search`, OpenAlex `search`);
4. *DBLP only:* source is DBLP with similarity ≥ 0.90. The cascade asks the same offline index with the same title and
   threshold, so this class is expected to be empty or nearly so; it is reported as measured.

Item (4) concerns academic references. S/W references found by URL or Wayback are reported as their own class, "URL".

**OpenAlex budget.**
- Priority within a UTC day: (1) the cascade of Addendum 2; (2) section (H); (3) GT-3.
- GT-3 calls OpenAlex only when that day's cascade set and (H) set are finished or have reached their reserve.
- It stops when `X-RateLimit-Remaining` < 500.
- The credits used per `search` call are recorded from the headers of the first call. They may differ from those of
  `filter=title.search`.
- No GT-3 request is sent after 2026-11-12T23:59Z. A reference whose OpenAlex request was never sent is *unanswered*.

**Conduct.** Crossref ≤ 2 requests/s; arXiv and keyless S2 ≤ 1 request per 3 s; OpenAlex ≤ 1 request/s; Wayback and URL
checks ≤ 1 request/s. Contact string `noreply@example.org`. S2 uses `S2_API_KEY` if set (not set when this was written).
The OpenAlex key is read from `.env` only, never printed, logged or stored; cache keys are those of the request without the
key. New answers are stored only in `$THS_DATASETS/_derived/43/cache_p3f/<source>/`.

## (E) False-match rate

**D-splice decoys, n = 200, seed 49** (`code/p3f_deep_search.py`; `results/p3f_decoys.csv`, sha256 logged before any
decoy request).
- Pool: distinct academic references of 2019–21 with def-1 state resolved or unresolved, ≥ 6 normalised title tokens.
- Consecutive disjoint pairs (A, B) from the seed-49 permutation of the pool, sorted by (arxiv_id, key) before permuting.
  A pair is skipped if A and B come from the same paper, or if A has no surname or no year (a decoy must test the looser
  branch of the rule).
- Decoy title = the first ⌈|A|/2⌉ normalised tokens of A followed by the last ⌊|B|/2⌋ normalised tokens of B. Surnames, year
  and venue are those of A.
- A decoy with similarity ≥ 0.80 to title A or to title B is discarded and the next pair is used, until 200 are kept.
- The query string is the `.bib` template above.

**`gen_a` family:** the 5 planted `gen_a` rows of Amendment 6, as a separate family. Query string: their `.bbl` item.

**Estimates.**
- f̂ = decoys *found* / decoys answered (found or not found); f_hi = Clopper–Pearson upper 95 % bound.
- Reported separately for D-splice and for `gen_a`.
- The bounds of (G) use **the D-splice f_hi, or the f_hi of the pooled decoys if that is larger.**

Decoys that are spliced titles may be easier to reject than fabrications written by an LLM; the `gen_a` rate is reported
beside them for this reason.

## (F) Positive control

100 distinct certified-real references of 2019–21, drawn with seed 50 (`random.Random(50).sample` over references sorted by
(arxiv_id, key)). DOI, URL and eprint are removed: the template is used, or the `.bbl` item with `http(s)://…`, `doi:…`,
`10.xxxx/…`, `arXiv:…`, `abs/…` and bare arXiv identifiers deleted. GT-3 is then run. Recall with a Clopper–Pearson interval.
Descriptive only.

## (G) Bounds

For each tier and period: N = registered def-1 denominator (rows with state resolved or unresolved); U = rows unresolved
under the full cascade; F = rows of U *found* by GT-3; R = rows of U not found or unanswered. Duplicate (paper, key) rows are
kept, as in the registered denominators, and take the state of their distinct reference.

**2019–21.**
- X_hi = R / (1 − f_hi).
- **FP ∈ [max(0, U − X_hi)/N, U/N].**
- Paper-level bootstrap for both ends (B = 1000, seed 42), with f_hi held fixed.
- N includes references that may not exist. The resulting bias is at most X_hi/N; that number is printed.

**2024–26.** U/N, F/U and R/N, where R/N is an upper bound on "does not exist or cannot be found". The difference of R/N
between the two periods with a paper-level bootstrap interval. Exploratory.

## (H) Cascade completion extension

After the academic references of 2024–26 are finished and before 2026-11-12T23:59Z, the 2019–21 B, S and W targets of
Amendment 7 (a) that lack an answer (747 at the time of writing) are asked with the order, threshold and rules of
Addendum 2: group 3, then 5, then 6, seed-42 permutation within a group, same header stop, new answers in `cache_p3e/`. Whatever
is unfinished at the end date keeps the interval rule of Amendment 7 (a). This serves H2.

## (I) Tier-rule validation

**Set:** references resolved by the cascade or found by GT-3, compared by the type of the matched record:

| Source | → J | → C | → P | → B | → S | → W |
|---|---|---|---|---|---|---|
| Crossref `type` | journal-article | proceedings-article | posted-content | book, book-chapter, monograph, edited-book, dissertation | dataset, component | report, standard, other |
| DBLP | article (not CoRR) | inproceedings | journals/corr | book, incollection, phdthesis | — | — |
| OpenAlex (`type` + `primary_location.source.type`) | article + journal | article + conference | preprint, or source type repository | book, book-chapter | dataset | all other |
| arXiv | — | — | every record | — | — | — |

- A record is taken from the first backend of its hits in cascade order. A record type outside this table, and records from
  Semantic Scholar, are excluded and counted.
- Crossref search answers stored by the cascade carry no `type`. Types for matched DOIs are fetched once by batch
  (`filter=doi:…`, `select=DOI,type`, ≤ 2 requests/s) into `cache_p3f/crossref/`. The validation script then runs offline.
- Reported: agreement, Cohen's κ, the confusion matrix; **version mismatches** (machine P against record J/C, or the
  reverse) counted apart; agreement without the version mismatches.
- Limits: only resolved references; S and W are rare in registries.

## (J) H4

- **Registered H4** is reported as registered, with the label "manual arm AI-assisted; reliability criterion failed; not
  used for inference".
- **H4-auto (exploratory).** Compare FP_certified (registered H4, full cascade) with the bounds of the FP on academic
  references **with neither DOI nor arXiv id** in 2019–21.
  - Weights: H4's corpus shares of tiers among references with neither DOI nor arXiv id, restricted to J, C, P and
    renormalised.
  - Lower and upper ends: the (G) formulas per tier with N, U, R restricted to those references, and the same f_hi.
  - Paper-level bootstrap, B = 1000, seed 42.
  - **Supports** H4 if the CI of (FP_nonID,lower − FP_certified) lies above 0; **contradicts** if the CI of (FP_nonID,upper
    − FP_certified) lies below 0; otherwise **undetermined**.

## (K)

No change to H1–H5 definitions or PASS/FAIL rules. No change to def 1, def 2, the 0.9 similarity threshold of the registered
cascade, the tier rule, the identifier rule or the certified-real label.

## Reporting

A new row in the protocol table of the paper (Amendment 8, post hoc, written after review and after the interim rates were
known). GT-3 is stated as a device for bounding the false-positive rate, with its false-match rate and its recall; it is not
a validated labelling of existence.
