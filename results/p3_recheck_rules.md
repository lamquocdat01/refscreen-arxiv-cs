# Recheck rules for `p3_recheck_sheet.csv` (manual_protocol.md + PREREG_AMENDMENT_5 (b′)–(d′))

Give this file and `manual_protocol.md` to the rater. Fill the empty columns of the sheet and do nothing else.

## Search order
Stop at the first conclusive hit:
1. Search for the exact title in quotes on Google Scholar, then on DBLP (for CS venues).
2. Check the publisher or venue site named in the entry.
3. For software, a dataset or a model: open the URL in the entry. Otherwise search GitHub, Hugging Face, Zenodo
   or Kaggle.
4. For a web page, report or standard: open the URL in the entry.
   - If the URL is dead, use the Wayback capture closest to `bib_version_date`, and not after it.
   - For a standard, check the standards body's catalogue.
5. Run a general web search for the title in quotes plus the first author's surname.

Search engines and fetched pages are the only evidence. Never ask an LLM whether a reference exists.

## Input columns
- `citing_paper_date`: arXiv v1 date of the citing paper. Information only.
- `bib_version_date`: date of the arXiv version that the .bib entry was taken from. **This is the reference date
  for condition (c).**
- `title`, `author`, `bib_entry`: the reference as parsed. Any of these can be empty.
- `bbl_item`: the same reference as typeset in the citing paper's own .bbl, if one exists. Use it as part of the
  entry (it may contain a URL, venue or full title that the .bib lacks).

## Decision rule
**exists** when a document or resource is found that meets all three conditions:
- **(a) Title:** the same title, up to case, punctuation, a dropped or added subtitle after ":" or "—", or at most
  2 word differences. A translation does not count. A resource cited only by its URL counts as identified by that URL.
- **(b) Author:** at least 1 author surname matches.
  - For software or web resources without persons, the owning organisation or repository owner counts as the author.
  - **(b′)** Suppose the entry names an organisation but the resource sits under a personal account. The personal
    owner counts as that organisation **only if** the repository README, or the paper that accompanies the resource,
    names that organisation.
- **(c′) Date:** the resource existed no later than **`bib_version_date`**.
  - For a web resource, a Wayback capture or an in-page date proves this.
  - A later version of the same resource is accepted.

**not-found** when the five search steps give no candidate that meets (a) and (b).

**ambiguous** in any of these cases:
- a candidate meets only one of (a) and (b);
- the resource is cited too vaguely to identify;
- (a) and (b) are met but (c′) fails.

## Recording
| Column | Content |
|---|---|
| `exists` | exists / not-found / ambiguous |
| `evidence_url` | the URL that decided the outcome (the Wayback URL for archived pages); empty for not-found |
| `evidence_note` | at most 1 line: which condition failed, or which variant was accepted |
| `checker` | rater id and how the rating was done, e.g. "R3 Cowork (blind)" |
| `checked_at` | ISO-8601 UTC timestamp |

Do not open any other file of the project: no earlier sheets, samples, results or reports.
