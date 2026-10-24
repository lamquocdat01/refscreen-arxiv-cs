# refscreen-fp

Code and derived data for "Which Backend Decides? False Positives of Reference-Existence Screens on Legitimate
Computer-Science Bibliographies" (submitted to *Scientometrics*). The study measures how often reference-existence
screens flag legitimate references, on 1,298 arXiv computer-science papers (cs.CV/LG/CL/NI/CR; citing papers 2019–21
and 2024–26), and bounds what any screen can achieve.

## Contents (allow-list)
- `code/`: analysis scripts (Python 3.11, `requirements.txt`). Scripts take `--seed` and write to `results/`.
- `docs/`: pre-registration `PREREG_43.md`, the manual verification protocol, Amendments 1–5, and their sha256 in
  `prereg_hash.txt` (Amendment 5 is post hoc).
- `theory/`: theorem statements and full proofs, with the measured numbers.
- `results/`: derived tables (CSV/JSON) behind every number of the article; all files are final (`interim: false`).
- `figures/`: figures as PDF/PNG; each has a `.sources.txt` with the sha256 of the result files it was drawn from.
- `data_manifest/`: every downloaded arXiv paper (id, category, sha256 of the e-print) and the arXiv version its
  bibliography was taken from (`manifest_src_version.csv`).
- `supplement/`: copies of the pre-registration documents and the diagnostic and audit tables, with `SHA256SUMS`.

## Reproduce the reported numbers (no network, no API key)
1. Download the derived reference-level files from Zenodo ([DOI to be inserted]) and place them so that they sit at
   `$THS_DATASETS/_derived/43/` (`p1_groundtruth_refs_full.csv`, `p2_retry_ratelimited.csv`,
   `screen_p1/screen_refs.csv`).
2. In a fresh virtual environment: `pip install -r requirements.txt`, then `python code/reproduce.py` (or `make reproduce`).

The script reruns the main table, H1/H2, the beta-binomial fit, both H4-render variants, the theory and policy tables,
and the merge of the night retry. It then compares every number with the committed results and exits 1 on any
difference. `code/make_ms_numbers.py` turns the result files into the number macros and tables of the manuscript.

Not included: arXiv source files (not re-hosted), raw database responses and the DBLP dump. The resolution and
render stages need them, so they are not part of the offline reproduction.

## Main entry points (from `code/`)
```
python p1_backend_table.py --seed 42                 # unresolved rate by tier x cumulative backend set
python p1_hypotheses.py --seed 42                    # H1, H2
python screen_baseline.py --phase p1 --seed 42       # render -> parse -> screen (H3); needs arXiv sources
python p1_h4_bias.py --seed 42                       # H4 and selection-bias coefficients
python p2_theory_final.py --seed 42                  # Theorem 1 headlines, dispersion, alpha-safe rules
python p2_recheck_pairs.py --seed 42                 # agreement of hand verification (R1/R2/R3)
python p3_recheck.py kappa --seed 43                 # post-hoc recheck after Amendment 5
```

## License
To be added at release (proposed: MIT for code, CC BY 4.0 for derived data).
