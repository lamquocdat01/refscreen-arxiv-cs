# PREREG_43 — Amendment 7, Addendum 3 (POST-HOC; procedural deviation from Amendment 7 (b), rater R_H1)

- **Status: POST-HOC procedural deviation.** Written on 2026-11-08. At that time:
  - the human-rated sheet H01–H68 had been drawn (`results/p3e_human_sheet.csv`, sha256 `b97720564dad…`);
  - the plaintext hash of its key had been logged (`b4bba6e0…`);
  - R_B had rated the sheet (`results/p3e_human_rB.csv`). Nobody had opened the key, and nothing had been scored.
  - R_H1 had not started rating, and no evidence pack existed.
  This addendum is hashed before the evidence pack is made. `PREREG_AMENDMENT_7.md` (`df36318b…`) and Addenda A
  (`10f8b213…`) and 2 (`e4c9f26b…`) are not edited.
- **Decision:** LQD, 2026-11-08.
  - R_H1 rates the sheet blind, with retrieval support: an evidence pack made by an AI sub-agent.
  - R_H1 rates in two passes. Pass 2 starts at least 12 hours after pass 1.
- **Unchanged:**
  - the sheet, its rows, order and key;
  - the rules (`results/p3e_human_rules.md`) and the protocol (`manual_protocol.md`);
  - the decision rule exists / not-exists / ambiguous;
  - R_B and R_H2 (option A/B);
  - every statistic of Amendment 7 (b), the "Reading" sentence and its threshold, and H4 on human labels;
  - the tier-rule check (c). Sheet T001–T100 is rated by hand by LQD, with no evidence pack and no other aid.

## Why (reason for the deviation)

1. **Time.**
   - Amendment 7 (b) asks R_H1 to rate 68 references by hand, running the full five-step search order of
     `manual_protocol.md` for every row. The paper should be resubmitted before the 2026-11-14 deadline of
     Amendment 7 (option A/B).
   - R_H1 rates alone, beside the remaining cascade passes, the manuscript update and the tier sheet. A fully manual
     search of 68 rows plus a second pass does not fit that time.
   - Most of the time is spent issuing queries and copying records, not judging them. The evidence pack moves the
     querying to an agent. The judgement stays with the human.
2. **The judgement stays human and blind.**
   - The pack lists only what the search services returned: candidate records and their links. It contains no label,
     no similarity score and no assessment.
   - R_H1 decides each label himself, by opening the sources. The rule of the protocol, "never ask an LLM whether a
     reference exists", is kept: no model is asked about existence, and the agent is told not to judge.
   - The agent that makes the pack is new and has no context. It reads only the sheet and the protocol. It does not
     read the rules, R_B's ratings, the key or any other project file.
3. **Two passes measure the stability of the human reading.**
   - With option B, no second human rater may be available. The test–retest agreement of R_H1 (pass 1 against pass 2,
     at least 12 h apart, with the pass-2 reason recorded for every change) is the only reliability measure for the
     human labels.

## Procedure

**Evidence pack.**
- **Agent and inputs.** One new Claude Code sub-agent with no context. It reads only `results/p3e_human_sheet.csv` and
  `manual_protocol.md`, and it receives `env/AGENT_RULES.md` verbatim.
- **Searches, for each row H01–H68:**
  - Crossref `query.bibliographic`;
  - the arXiv API;
  - OpenAlex without a key (contact `noreply@example.org`);
  - a general web search.
- **Outputs:** `results/p3e_evidence_pack.csv` and `P3E/evidence_pack.md` (one entry per row). Each entry has:
  - `row_id`;
  - the queries tried;
  - at most 3 candidate records (title, authors, year, venue, DOI/URL, source);
  - "no candidate returned by: …" for every source that returned nothing (or refused the request; the refusal is
    stated as such).
- **Forbidden in the pack:**
  - the labels exists / not-exists / ambiguous;
  - similarity or relevance scores;
  - the evaluative words likely, fake, fabricated, hallucinated, planted, synthetic, real, suspicious and mismatch;
  - any comment beyond the facts.
- **Check by the main session before release:**
  - The forbidden words are searched for by regex in all text that the agent wrote. The required count is 0.
    Bibliographic strings copied verbatim from the sheet or from a returned record are counted separately and
    reported.
  - Nothing about the OpenAlex key or the sheet key appears in the pack.
  - All 68 rows are present.
  - Any line that breaks a rule is deleted, and the deletion is logged in `P3E/P3E_LOG.md`.

**Rating by R_H1.**
- **Form.** `results/p3e_human_rH1_form.csv` is the sheet with the empty columns `label_pass1`, `evidence_url`,
  `evidence_note`, `pass1_at`, `label_pass2`, `pass2_note` and `pass2_at`. Its `checker` column is pre-filled with
  "R_H1 author (blind; retrieval-aided)". The instructions are in `P3E/HOW_TO_RATE_RH1.md`.
- **Files R_H1 may open while rating:** the sheet or form, the rules, the protocol, the evidence pack, the instruction
  file, and any web page.
- **Files and tools R_H1 must not open or use:** `results/p3e_human_rB.csv`, `keys/`, any other project file, and any
  AI assistant.
- **Each label** follows the decision rule. R_H1 opens the cited URL or record to check it himself. An entry in the
  pack is never evidence by itself.
- **Pass 1, then pass 2** at least 12 h after pass 1 ends.
  - Pass 2 reviews all 68 rows and records `label_pass2` for every row.
  - Pass 2 writes a reason in `pass2_note` for every changed label.
- **Rating used.** The R_H1 rating used in every statistic of Amendment 7 (b) is `label_pass2`.
  - `label_pass1` is used only for the intra-rater statistics: raw agreement, Cohen's κ, PABAK and Gwet's AC1 over
    3 outcomes, and the number and list of changed rows.
- **Saved file.** `results/p3e_human_rH1.csv`.
- **Scoring** runs only when `results/p3e_human_rH1.csv` (with `label_pass2` filled on all rows) and
  `results/p3e_tier_rH1.csv` both exist.

## Reporting in the paper

- **Methods (human-rated check).** One added sentence, worded as:
  > "R_H1 (the first author) rated blind with retrieval support. For each row, an AI agent that saw only the sheet
  > and the search protocol listed up to three candidate records returned by Crossref, arXiv, OpenAlex and a web
  > search, without labels or judgements. R_H1 opened the sources and assigned every label in two passes at least
  > 12 h apart; the second pass is the rating, and intra-rater agreement is reported."
- **Deviations table.** A row "R_H1 retrieval-aided, two passes (Amendment 7, addendum 3)" with the reason "rater
  time".
- **Limitations.**
  - The human labels are not fully independent of AI retrieval.
  - Human–AI agreement (R_H1–R_B) may be higher than it would be between two fully independent searches, because
    both raters relied on the same search services.
  - If option B holds, the abstract says that the only human check was made by the author, with retrieval support.
