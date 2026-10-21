# Generation prompt — family (a) "fabricated title" (PREREG_AMENDMENT_4 (g))

- **Generator:** Claude Code session, model `claude-opus-5-5`, 2026-10-21.
- **Seeding:** the generator has no seed and no temperature control, so the text below is not reproducible by seed.
  Reproducibility therefore comes from the stored output (`family_a_candidates.csv`), not from regeneration.
- **Seed 42 is used downstream:**
  - to draw the 100 used rows from the candidates that pass the non-existence check;
  - to assign rows to the hallucinator mix.
- The prompt was given verbatim:

```
Write 130 bibliography entries that look like ordinary computer-science references cited by an arXiv paper in
cs.CV, cs.LG, cs.CL, cs.NI or cs.CR (26 per field), but whose TITLE is invented: it must not be the title of any real
publication you know of. Rules:
- Title: 6-16 words, the register of a real paper title (method name optional, "Towards ...", "...: A Survey", etc.).
  Do not reuse a real title with one word changed; do not use joke or impossible topics.
- Authors: 1-4 plausible full names (mixed origins), "Given Family" form, separated by " and ". Do not use names of
  real well-known researchers in that subfield, and never "John Doe"/"Jane Smith".
- Venue and year: a real venue that publishes the field (journal or conference) and a year 2015-2025, or
  "arXiv preprint" with an arXiv-style id that you invent (YYMM.NNNNN).
- tier: J (journal), C (conference/workshop), or P (arXiv preprint); about 40 % J, 40 % C, 20 % P.
Output CSV columns: cand_id,field,tier,title,authors,venue,year,arxiv_id
```

- **Check before use** (`p2_fake_refs.py check`):
  - Every candidate is queried on all five backends: Crossref, arXiv `ti:` (forced for every candidate), DBLP offline,
    OpenAlex and S2.
  - A candidate is **excluded** if its best title similarity is ≥ 0.8 on any backend.
  - It is also excluded if any backend failed to answer and the remaining backends cannot rule out a match. That case
    is recorded as `unverified` and counted.
