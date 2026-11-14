# PREREG_43 — Amendment 9 (POST-HOC): web evidence of existence for the flagged .bib references of 2019–21

- **Status: POST-HOC.** Written on 2026-11-13 between 00:42 and 01:00 UTC, before any step it describes: no row has
  been drawn, no planted reference has been placed and no web search has been made for this amendment.
- **Decision:** LQD, CP3e of 2026-11-13 07:35 ICT, question 3 = A (`CP3e_DECISION_43_20261113.md`; prompt
  `PROMPT_43_P3H_EVIDENCE_CLOSURE_20261113.md`).
- **Unchanged:** `PREREG_43.md`, `manual_protocol.md`, Amendments 1–8, the four addenda of Amendment 7 and the P3G
  post-hoc note (`P3G/POSTHOC_NOTE_P3G.md`, `c2c23b6f…`). H1–H5, their criteria and their results do not change.
  Amendment 6 said that no further amendment would follow; Amendments 7–9 were written after it and are reported as
  such.

## What was known when this was written
- Every GT-3 (deep search) result, pooled and by branch. Academic references of 2019–21 unresolved under the full
  cascade: pooled U = 215 (46 found, 164 not found, 5 unanswered); `.bib` branch U = 81 in 45 papers (8 found, 72 not
  found, 1 unanswered; tiers J 63, C 17, P 1); `.bbl` branch U = 134.
- The branch split, the P1 rule of the P3G note and its outcome (`.bib` is the main branch), the two-ends bounds of
  P3G (`.bib` FP bounds 0.09 %–1.06 % at f_hi = 1.86 %; 0/198 `.bib` papers with two confirmed flags at the lower
  end), and the false-match rate of the GT-3 rule on generated family (c), 12/100.
- The labels of the human rater R_B (key opened earlier) and of the AI rater.
- The S6′ review (2026-11-12) and its closure check (`P3/R2_CLOSURE_43_20261113.md`). The closure check (N8) found
  that the paper-level lower end of the headline branch rests on 8 references found by the deep search, and that
  no flagged reference was checked against a human-read source.

## Why
The 81 flagged `.bib` references are few enough for the author to check each against one public web page. This
amendment fixes, before the search, how that evidence is gathered, how it is checked by rule, how the author confirms
it, and how its error rate is measured with planted references whose answer is known.

## (A) The set
- **Real rows:** every academic reference (tiers J, C, P) of the 2019–21 corpus whose title comes from the authors'
  `.bib` and that the full cascade leaves unresolved. The count is recomputed by `code/p3h_evidence_sheet.py` from the
  stored ground truth and logged; it is expected to be 81.
- **Planted rows: 19** references that do not exist, of family (a) of Amendments 4 (g) and 6 (`gen_a`: invented title,
  invented authors, real venue).
  - They are drawn with seed 53 from the 30 candidates of the stored family-(a) generation of 2026-10-21
    (`code/fake_refs/family_a_candidates.csv`) that were never used and never released: they were held back in P2
    because one backend call failed ("unverified"). A new generator run is not made, because the generator has no
    seed; the stored candidates are the output of the registered prompt.
  - Before placing them, `code/p3h_evidence_sheet.py` checks offline that no stored candidate of any backend
    (Crossref, arXiv and DBLP for all 30; OpenAlex and Semantic Scholar where they answered) reaches title
    similarity 0.80 for a drawn item. An item that fails is replaced by the next draw; the replacement is logged.
- **Presentation.** Every row, real or planted, is shown in one form: ID; a reference string rendered by one template
  from the fields (`{authors}. {title}. {venue}, {year}.`); title; authors (each as "Given Family", comma-separated);
  year; venue. No row carries a URL, a DOI or an arXiv id, so the two origins cannot be told apart by format.
  LaTeX markup is stripped from `.bib` fields.
- **Order and IDs.** The 100 rows are shuffled with seed 54 and numbered `E001`…`E100`.
- **Key.** `ID, origin (real/planted), source id` is written only in encrypted form (Fernet, the key file of
  `$THS_DATASETS/_derived/43/keys/`) as `p3h_evidence_key.csv.enc`. The sha256 of the plaintext is written to
  `P3H/P3H_LOG.md` before the first search. The key is opened only after the author's form exists.

## (B) The searchers
- New Claude Code sub-agents with no project context. Each receives only a batch of sheet rows (at most 17) and the
  text of rules (C) and (D). They are told not to open any local file. They are not told that planted rows exist.
  They do not see GT-3 results, R_B labels, the key, or other batches.
- Per reference: at most 6 WebSearch queries and 6 WebFetch calls. At most three searcher agents run at the same
  time, which keeps each host below one request per second.
- Output per row: ID, at most one URL (the best evidence found), its class (1–4 below), a short note, or "none".
- The searcher's own judgement that a reference exists is not used as evidence. Only the rule of (D) and the author
  of (E) decide.

## (C) Accepted evidence
One public URL of one of these classes:
1. the article page of the publisher or of the proceedings;
2. a repository (arXiv, institutional repository, HAL, Zenodo, …);
3. a library catalogue or a subject bibliography (DBLP, ACL Anthology, WorldCat, a national library, …);
4. a page of an author or group with the PDF or a publication entry.

Not accepted: a search-results page; a "[CITATION]" entry that only records a citation; the reference list of another
work; a page generated by AI. The public pages of Crossref, DBLP, arXiv, Semantic Scholar and OpenAlex count as web
pages; their APIs are not used.

## (D) Capture and rule check
- **Web rules.** Only Claude Code's WebSearch and WebFetch are used; no browser headers, cookies, user-agent changes
  or proxies. For each host the capture step first reads `robots.txt`. A host whose `robots.txt` disallows the page
  for ClaudeBot, anthropic-ai, Claude-Web or Claude-User (named groups, or the `*` group when no named group exists),
  or that returns a bot-block page or refuses the fetch, is not fetched automatically: the row is **needs_browser**.
- **Capture.** A separate sub-agent, given only the list of URLs (no reference data), fetches each URL once with
  WebFetch and returns, verbatim where the tool shows them: `citation_title`, `citation_author`,
  `citation_date`/`citation_publication_date`, `DC.title`, `DC.creator`, `DC.date`; otherwise the displayed title,
  author list and year of the main work on the page. The text is stored in
  `$THS_DATASETS/_derived/43/cache_p3h/` with the URL, its UTC time and its sha256. The text is what the fetch tool
  returns after its own conversion; this is a limitation (H).
- **Rule** (`code/p3h_evidence_check.py`, offline on the cache). Page title = `citation_title`, else `DC.title`, else
  the displayed title. Similarity = `refmatch.title_sim(sheet title, page title)`. Surname match = at least one
  surname of the sheet authors (lower case, accents removed) occurs in the page's author text.
  - **PASS:** similarity ≥ 0.90 and a surname match.
  - **NEAR:** 0.80 ≤ similarity < 0.90, a surname match, and page year within ±1 of the sheet year.
  - **FAIL:** a URL was captured and neither holds; also a URL of a refused kind (search results).
  - **NONE:** the searcher returned no URL. **needs_browser:** as above.
  - Stored per row: URL, class, page title, similarity, matched surnames, page year, content sha256, UTC time.

## (E) Author confirmation
- The author opens the URL of every PASS, NEAR and needs_browser row in a browser and records `y` (the page is the
  cited work), `n`, or `?`. He is blind to the key and does not open `keys/`.
- A reference is **confirmed** when the rule gives PASS **and** the author writes `y`. NEAR + `y` is reported
  separately and is **not** confirmed. needs_browser + `y` is confirmed with the class "author-opened".

## (F) Measures
- On the planted rows: the share confirmed (false confirmation), with a Clopper–Pearson 95 % interval, for the rule
  alone (PASS) and for rule + author (confirmed).
- On the real rows: C = the number confirmed, with the counts by state; cross-tabulated with GT-3 (found / not found /
  unanswered) and with the R_B labels where a row is shared.

## (G) Use
- New lower end of the `.bib` branch, 2019–21: a flagged reference counts as real if GT-3 found it **or** it is
  confirmed here. Recomputed with the formulas of P3G: the lower FP bound (f_hi = 1.86 % for the remaining
  not-found rows), the share of papers with ≥ 1, 2, 3 flags, k_emp, and the PPV ceiling at the lower end.
- The upper end does not change.
- If any planted row is confirmed, the false-confirmation rate is reported verbatim and the lower end is given both
  with and without the web evidence.
- Every result carries the label "post hoc; web evidence retrieved by an AI agent, checked by rule, confirmed by the
  author; one URL per reference released". H1–H5 do not change.

## (H) Limitations stated in advance
- Only the `.bib` branch of 2019–21 is covered.
- The author is the only person who confirms.
- Web pages can change after the retrieval date; the sha256 and UTC time of every capture are kept for that reason.
- The captured text is the fetch tool's rendering of the page, not the raw HTML.
- 19 planted rows bound the false-confirmation rate only coarsely (0/19 gives a 95 % upper limit of 17.6 %).
