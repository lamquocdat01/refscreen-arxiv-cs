# Pre-registration — False positives of reference-existence screens on legitimate bibliographies (topic 43, phase P1)

Version 1.0 · written 2026-10-18, before any P1 data beyond the P0 pilot was downloaded · frozen by the sha256 recorded in
`results/prereg_hash.txt`. Any later change is made in a separate `PREREG_AMENDMENT_<n>.md`; this file is not edited.
Every analysis not listed in §7 is labelled **exploratory** wherever it is reported.

## 0. What was already seen (disclosure)

A P0 pilot (2026-10-16/18, seed 42) used 130 arXiv papers: 100 from 2024–2026 and 30 from 2019–2021 (29 usable).
- It measured a pre-LLM title-only unresolved rate of 7.18 % (k = 82, n = 1,142).
- Post hoc, the same rate was 3.55 % (27/760) on three academic BibTeX entry types, and 32–81 % on @misc/@online/@manual.
- On certified-real references it measured screen false-positive rates of 0.16–1.6 %.

The tier definitions (§2) and hypotheses H1–H2 (§5) were written **after** seeing these numbers. They are therefore
not blind to the pilot. The P0 papers are kept and form part of the P1 corpus (they count towards the quotas in §1).
The quantities pre-registered here are tested on the full P1 corpus. They are also reported with the P0 papers
removed (§7, line 1).

## 1. Corpus

- **Source:** arXiv LaTeX e-prints (`https://arxiv.org/e-print/<id>`). Primary category in {cs.CV, cs.LG, cs.CL, cs.NI, cs.CR}.
- **Selection:** papers are drawn at random from random 3-day submission windows (arXiv API listing, `random.Random(42)`).
  Requests are made at most once every 3 s. Tarballs are hashed (sha256) and are not kept.
- **Post-LLM set:** ≥ 1,000 papers from 2024–2026, i.e. 200 per field, split by year 67 / 67 / 66.
- **Pre-LLM set:** ≥ 300 papers from 2019–2021, i.e. 60 per field, split by year 20 / 20 / 20.
- **Inclusion:** a paper is kept if its e-print contains a main `.tex` with `\documentclass` and at least one `.bib` or `.bbl`.
- **Reference source:**
  - Papers with a `.bib` are used through it (*source = bib*).
  - Papers with only a `.bbl` are parsed with GROBID (*source = bbl*) and flagged as a separate branch.
- **Exclusion:** papers with `\cite` keys none of which is found in their `.bib` and no usable `.bbl`. They are counted and
  listed, not replaced.
- **Unit:** a *cited reference* = a distinct `\cite`/`\nocite` key of the paper that is found in the paper's `.bib`
  (or one `\bibitem` of the `.bbl`).

## 2. Entry tiers (machine rule, no manual assignment)

Fields are read case-insensitively after LaTeX stripping.
- "Text fields" = journal, booktitle, note, howpublished, publisher, institution, url, doi, eprint, archiveprefix.

Tier definitions:

| Tier | Rule |
|---|---|
| **P** preprint | has `eprint`, or `archiveprefix` = arXiv, or any text field matches `arxiv`, `biorxiv`, `medrxiv`, `ssrn`, `10.48550/`, `10.1101/` or `10.2139/ssrn` |
| **S** software / dataset / model card | entry type software or dataset; or entry type misc/online with url, howpublished or note matching `github`, `gitlab`, `huggingface`, `zenodo`, `kaggle` |
| **J** journal article | entry type article with a non-empty `journal` |
| **C** conference / workshop | entry type inproceedings, proceedings or conference |
| **B** book / chapter / thesis | entry type book, inbook, incollection, phdthesis, mastersthesis or thesis |
| **W** web / report / standard / other | everything else (misc, online, manual, techreport, unpublished, standard, patent, booklet, article without journal, …) |

- **Conflict order:** P > S > J > C > B > W, i.e. the first matching rule in this order wins.
- **Academic tier:** A = J ∪ C ∪ P.
- **bbl-only references:** GROBID TEI fields are mapped as journal title → journal, meeting/monograph title → booktitle,
  `ptr`/`idno` → url/doi/eprint. TEI with only a monograph title and a publisher → B. The same rule is then applied.

## 3. Identifiers and the certified-real label

- **has_doi:** the `.bib` has a DOI, or a DOI in its url.
- **has_arxiv:** the `.bib` has an arXiv id (eprint, url or journal text).
- **certified-real:** the identifier resolves (DOI: Crossref works/<doi>, then free OpenAlex DOI lookup, then DataCite;
  arXiv: arXiv API id_list) **and** the registry title has similarity ≥ 0.9 with the `.bib` title.
- **Similarity:** max(normalised Levenshtein similarity, token Jaccard) of titles after LaTeX stripping, NFKD ASCII
  folding, lower-casing and non-alphanumerics → space. This is `refmatch.title_sim`.

## 4. Resolution definitions and states

- **def 1 (title only):** the `.bib` title is queried.
  - A title with < 10 normalised characters is *no-title* and excluded, with the count reported.
  - Backend cascade, fixed at the start of the run and recorded in the output:
    1. Crossref `query.bibliographic` (top 5);
    2. Semantic Scholar `paper/search/match`, queried if (1) does not resolve;
    3. arXiv `ti:` search (top 5), queried if (1) and (2) do not resolve;
    4. OpenAlex title search, only if `OPENALEX_API_KEY` is set at run start, queried if (1)–(3) do not resolve.
  - **resolved:** some backend returns a record with title similarity ≥ 0.9.
- **def 2 (title + first author):** def-1 resolved **and** the first `.bib` author surname (ASCII-folded) occurs as a whole
  token in the matched record's author names.
  - References with no `.bib` author, or whose matched record has no author list, are excluded from def 2.
  - The count of these exclusions is reported.
- **Three states per reference and definition:**
  - **resolved**, as above;
  - **unresolved:** every backend in the cascade answered (HTTP 200 with parseable body) and none resolved;
  - **rate-limited:** not resolved, and at least one backend in the cascade failed (HTTP 429, timeout, 5xx,
    unparseable body) after its in-run retries.
- **Retries for rate-limited references:** after the first full pass they are re-queried in up to 3 rounds, spaced
  2, 4 and 8 minutes apart.
- **Denominators:** references still rate-limited after round 3 are excluded from every denominator and counted.

## 5. Hypotheses

Notation and conventions:
- u_s = unresolved share of tier s; u_A = academic.
- Rates are pooled over references. The **primary CI** is a 95 % paper-level bootstrap (B = 1000, seed 42); Wilson 95 %
  is secondary.
- "**strong**" = the primary CI also satisfies the bound.

**H1.** u_A (def 1, 2019–2021) ∈ [0.5 %, 5 %].
- PASS if the point estimate lies in the window.
- H1-strong if the whole CI does.

**H2.** u_W ≥ 5 · u_A (def 1, 2019–2021).
- PASS if the point ratio is ≥ 5.
- H2-strong if the lower bound of the paper-bootstrap ratio CI is ≥ 5.

**H3.** On certified-real references of the render set:
- Compared rates: FP(IEEEtran v1.14, strip) ≥ 2 · FP(IEEEtran-DOI, orig).
- Screen settings: union screen, GROBID-parsed titles, render set of §6.
- PASS if the point ratio is ≥ 2.
- H3-strong if the lower bound of the paper-bootstrap ratio CI is > 1.

**H4.** FP of the title-only screen (def 1) on certified-real references < FP on manually verified existing references (§6.3).
- Both are measured on the 2019–2021 corpus.
- FP_manual is weighted by the corpus share of each tier among non-identifier references.
- PASS if the paper-bootstrap 95 % CI of FP_manual − FP_certified lies above 0.

**H5.** In the 2019–2021 corpus (π assumed ≈ 0), the share of papers with ≥ 2 def-1 unresolved references rises with n.
It follows the stratified Thm 2′ prediction P(Σ_s Bin(n_s, u_s) ≥ 2):
- u_s is estimated leave-one-paper-out;
- n_s is the paper's own tier counts.

Papers are split into n-tertiles. PASS if both hold:
- (i) the observed shares are non-decreasing across tertiles;
- (ii) in every tertile the mean predicted probability lies inside the 95 % Wilson CI of the observed share.

## 6. Experiments

### 6.1 Ground truth, route (a)
- All corpus references get: tier, has_doi, has_arxiv, certified_real, def1_status, def2_status, backends_hit.
- Seed 42.

### 6.2 Render → strip → rescreen
- **Papers:** 100 from the 2024–2026 set, 20 per field, seed 42; this includes the 30 P0 render papers.
- **Bibliography:** each paper's cited entries are rendered.
- **Styles:** IEEEtran.bst v1.14; IEEEtran-DOI, with `_ % # &` in DOIs escaped before rendering; elsarticle-num.
  acmart is secondary, if it compiles.
- **Variants:** orig (as authored) and strip (doi, url, eprint and archiveprefix removed).
- **Extraction:** pdftotext.
- **Parsers:** GROBID (primary) and anystyle (secondary).
- **Screens:** identifier, Crossref, Semantic Scholar, union, run on the rendered strings.
- **Reported:** FP on certified-real and on manual-sample references that fall in the render set, by
  style × variant × parser × backend × tier.
- **Overlap note:** the manual sample (§6.3) is drawn from 2019–2021 and the render set from 2024–2026, so the overlap
  is empty by design. FP on the manual sample is therefore measured with the title-only screen on the `.bib` title
  (source "bib-title"), not on rendered strings.

### 6.3 Manual verification, route (b)
- **Sample:** 200 references from the 2019–2021 corpus that have neither DOI nor arXiv id.
  - Stratified across the 6 tiers: 33 per tier, plus 1 extra each for the two largest tiers.
  - Simple random sampling within each tier, seed 42.
  - A tier with fewer eligible references contributes all of them. Its remainder is split equally over the other tiers.
- **Decision rule:** fixed in `manual_protocol.md`. "Exists" = a document with the same title (case, punctuation and
  subtitle variants allowed) and ≥ 1 matching author, found via Google Scholar, DBLP, the publisher, the official site or
  Wayback.
  - Software / web: the resource, or a Wayback capture, existed with that title no later than the citing paper's date.
  - Outcomes: exists / not-found / ambiguous.
- **Record per reference:** evidence URL, time and checker.
- **Recheck:** 40 references (20 %, seed 42) are rechecked ≥ 48 h later, giving Cohen's κ on the 3 outcomes.
  - Second rater: a co-author; otherwise the same checker (reported as intra-rater).
- **Scope:** the external screen tool (hallucinator) is run on the 100 render papers. CheckIfExist is excluded as
  non-deterministic (it reports rate-limit errors as "not found").

## 7. Primary analyses (exactly these five)

1. u_s per tier × period (2019–21 vs 2024–26), def 1 and def 2, paper-bootstrap CI (primary) + Wilson; also without the P0 papers.
2. FP by style × reference source × backend on (a) certified-real and (b) the manual sample.
3. Tests of H1–H5 as stated in §5.
4. Stratified PPV-ceiling and P(false flag) tables (Thm 1′, 2′) with the measured u_s and π ∈ {0.39 %, 0.5 %}.
5. Tier-wise α-safe desk-reject rule (Prop 4′: count flags in A only, k = min{k : P(Bin(n_A, u_A) ≥ k) ≤ α},
   α ∈ {0.05, 0.01}), compared with k = 1 and k = 2 on the corpus: legitimate papers flagged per rule, by field.

Headline numbers in the paper are taken from the academic tier only, with n and the paper-level CI.
