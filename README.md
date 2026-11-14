# refscreen-arxiv-cs

Code and derived data for "Which Data Source Decides? False Positives of Reference-Existence Checks on arXiv
Computer-Science Bibliographies" (manuscript under submission). The study measures how often reference-existence
screens flag legitimate references, on 1,298 arXiv computer-science papers (cs.CV/LG/CL/NI/CR; citing papers 2019–21
and 2024–26), and bounds what any screen can achieve.

## Contents (allow-list)
- `code/`: analysis scripts (Python 3.11, `requirements.txt`). Scripts take `--seed` and write to `results/`.
- `docs/` and `supplement/prereg/`: pre-registration `PREREG_43.md`, the manual verification protocol, Amendments 1–9,
  the addenda and the post-hoc note, with their sha256 in `prereg_hash.txt` (which documents are post hoc is stated in
  each file and in the article).
- `supplement/evidence_p3h/`: the web evidence of Amendment 9 (sheet, URLs, capture manifest, rule check, the author's
  decisions, the key).
- `theory/`: theorem statements and full proofs, with the measured numbers.
- `results/`: derived tables (CSV/JSON) behind every number of the article; all files are final (`interim: false`).
- `figures/`: figures as PDF/PNG; each has a `.sources.txt` with the sha256 of the result files it was drawn from.
- `data_manifest/`: every downloaded arXiv paper (id, category, sha256 of the e-print) and the arXiv version its
  bibliography was taken from (`manifest_src_version.csv`).
- `supplement/`: copies of the pre-registration documents and the diagnostic and audit tables, with `SHA256SUMS`.

## Reproduce the reported numbers (no network, no API key)
1. Download `refscreen-derived-v1.0.0.zip` from the GitHub release `v1.0.2` of this repository and unzip it into a
   folder `<data>`, so that the files sit at `<data>/_derived/43/` (`p1_groundtruth_refs_full.csv`,
   `p2_groundtruth_refs_full.csv`, `p3e_groundtruth_refs_full.csv`, `p2_retry_ratelimited.csv`,
   `screen_p1/screen_refs.csv`, `fake/`, `cache_p3h/`). Set `THS_DATASETS=<data>`.
2. In a fresh virtual environment: `pip install -r requirements.txt`, then `python code/reproduce.py` (or `make reproduce`).

The script reruns the main table, H1/H2, the beta-binomial fit, both H4-render variants, the theory and policy tables,
the merge of the night retry and the post-hoc recheck statistics. It then compares every number with the committed results and exits 1 on any
difference. `code/make_ms_numbers.py` turns the result files into the number macros and tables of the manuscript.

Five steps re-read the stored backend and deep-search responses or the arXiv sources, which are not redistributed:
`p3f_deep_search.py --evaluate`, `p3f_tier_validation.py`, `p3f_notfound_profile.py`, `p3g_branch_split.py` and
`p3g_bounds.py`, plus the exploratory table of `p3e_recompute.py` (`p3e_exploratory_p3e.*`). Without those inputs the
script skips them, keeps their committed outputs (which the later steps then read), prints each skip, and compares
everything else. With the release files only, the comparison then reports 0 differences (checked on 14-11-2026);
with the stored responses and the arXiv sources present, every step runs.

Not included: arXiv source files (not re-hosted), the stored database responses and the DBLP dump. The resolution and
render stages need them, so they are not part of the offline reproduction.

## Main entry points (from `code/`)
```
python p1_backend_table.py --seed 42                 # unresolved rate by tier x cumulative backend set
python p1_hypotheses.py --seed 42                    # H1, H2
python screen_baseline.py --phase p1 --seed 42       # render -> parse -> screen (H3); needs arXiv sources
python p1_h4_bias.py --seed 42                       # H4 and selection-bias coefficients
python p2_theory_final.py --seed 42                  # Theorem 1 headlines, dispersion, alpha-safe rules
python p2_recheck_pairs.py --seed 42                 # agreement of hand verification (R1/R2/R3)
python p3_recheck.py merge                           # post-hoc recheck after Amendment 5: join R1/R2/R3 + route table
python p3_recheck.py stats --seed 43                 # its agreement statistics (results/p3_recheck_stats.json)
```

## License
Code: MIT (`LICENSE`). Derived data and documents: CC BY 4.0 (`LICENSE-DATA`). Citation metadata: `CITATION.cff`.
