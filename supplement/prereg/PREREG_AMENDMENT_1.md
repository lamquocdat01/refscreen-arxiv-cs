# PREREG_43 — Amendment 1: backend order and Semantic Scholar schedule (execution detail)

- **Date:** 2026-10-18, written before the restarted run (`ground_truth_run6`) and before any route-(a) result of the
  full corpus was computed. The original `PREREG_43.md` (sha256 `38378e7453d67fed42fcabd26d6f65a0a4fd6cbbc333a10272873de8918ccfb5`)
  is unchanged.
- **Reason:** without an API key the Semantic Scholar (S2) public pool answered most `paper/search/match` calls with
  HTTP 429. The first full run spent ~7.5 s per reference in S2 back-off (3,500 of 12,751 references of the 2019–21 set
  after 7.4 h; projected > 5 days for the corpus). No `S2_API_KEY` or `OPENALEX_API_KEY` is available.
- **What was seen when the change was made:** only throughput figures and the 84-reference smoke test of the new
  code (2 papers). No full-corpus u_s, FP or hypothesis test had been computed.

## What changes (PREREG §4 "Backend cascade" and the retry schedule)

1. **Round 1** (every reference of the 2019–21 set, then the 2024–26 set). Backends are asked in this order. The first
   one that resolves stops the cascade.
   1. Crossref `query.bibliographic` (top 5, polite pool: User-Agent + `mailto=noreply@example.org`, ≤ 10 req/s,
      back-off on 429/5xx).
   2. S2 `paper/search/match` **from stored answers only** (answers already on disk from the first run; no new S2
      request in round 1).
   3. arXiv `ti:` search (top 5, 1 req / 3 s), **only for references with an arXiv id or in tier P**. The original
      cascade queried it for every unresolved reference.
   4. OpenAlex title search on the keyless pool (≤ 1 req/s; `api_key` used automatically if `OPENALEX_API_KEY` is set).
      The first HTTP 429, or budget/quota refusal, stops all further OpenAlex calls for the run. Affected references
      carry `oa_skipped = 1`.
2. **Round 2.** It runs after round 1 of both sets. It re-runs the same cascade on every reference that is not
   resolved and not no-title, with **live S2 calls**: 1 req/s, 2 tries per call, `x-api-key` used automatically if
   `S2_API_KEY` is set. Stored answers of the other backends are reused.
3. **Retry rounds for rate-limited references** (PREREG §4) follow round 2: up to 3 rounds, spaced 2, 4 and 8 minutes,
   with live S2.

## Missing backends

- **OpenAlex.** In the original protocol OpenAlex was used only with a key. A reference whose OpenAlex call was skipped
  is therefore judged on Crossref + S2 (+ arXiv where it applies), which is the original keyless cascade. It is
  *unresolved* if those all answered without a match.
- **arXiv for non-P references.** A reference outside tier P and without an arXiv id is *unresolved* if Crossref and S2
  answered without a match. Its arXiv `ti:` search is not part of its cascade.

## What does NOT change

- **def 1** (title similarity ≥ 0.9) and **def 2** (def 1 + first `.bib` author surname).
- **The three states** resolved / unresolved / rate-limited, plus no-title.
- **Denominators:** rate-limited references are excluded after the 3 retry rounds.
- **Everything else:** tiers, identifiers and the certified-real label; hypotheses H1–H5, sample sizes, the manual
  protocol and the five primary analyses.
- **def 2 author lists:**
  - for arXiv and OpenAlex matches, the author list is read from the stored search answer, with no new request;
  - before this amendment, OpenAlex matches had no author list.

## Interim output (not a primary analysis)

`results/p1_groundtruth_round1_<set>.json` holds u_s after round 1 of a set. It is labelled
"round 1, before S2 (provisional)". There, a reference with no stored S2 answer counts as unresolved when the other
backends answered (`n_s2_pending` reported). The primary u_s are those after round 2 and the retry rounds.

## Sensitivity (exploratory, reported)

- u_s with and without OpenAlex hits.
- u_s restricted to non-P references with arXiv answered vs. not.
- Number of references with `oa_skipped = 1`.

Code: `code/refmatch.py`, `code/ground_truth_p1.py` (backups of the pre-amendment versions kept outside the repo).
Log: `D:\Datasets\_derived\43\logs\ground_truth_run6.log`.
