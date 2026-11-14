# Tier sheet — guide (T001–T100)

For each row, read the bibliography entry (`bib_entry`, a BibTeX entry) or, when it is empty, the formatted item
(`bbl_item`). Decide **what kind of work the reference is**, and write one letter in `tier_human`. If the entry does
not say enough, you may search the web for the work. Judge the work itself, not the BibTeX entry type: a journal
article written as `@misc` is still a journal article.

The six tiers (definitions of the study's pre-registration, §2):

| Tier | What the work is |
|---|---|
| **P** preprint | available as a preprint (arXiv, bioRxiv, medRxiv, SSRN), or cited as one |
| **S** software / dataset / model card | a code repository, software package, dataset or model card (GitHub, GitLab, Hugging Face, Zenodo, Kaggle, …) |
| **J** journal article | an article in a journal |
| **C** conference / workshop | a paper in conference or workshop proceedings |
| **B** book / chapter / thesis | a book, a chapter of a book, or a PhD/master's thesis |
| **W** web / report / standard / other | everything else: web page, blog post, technical report, standard, patent, manual, unpublished note, … |

**Conflict order:** if more than one tier fits, take the first in the order **P > S > J > C > B > W**. For example, a
conference paper that is cited with its arXiv identifier is **P**; a dataset described in a journal article and
cited as the dataset is **S**.

Fill in: `tier_human` (one of P, S, J, C, B, W), `evidence_note` (optional, a few words), `checker` (your name or
initials), `checked_at` (date). Save the file as `results/p3e_tier_rH1.csv`. Do not open any other project file
before you have finished.
