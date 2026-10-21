# refscreen-fp

Code and derived data for a study of false positives of reference-existence screens on legitimate bibliographies
(arXiv cs.CV/LG/CL/NI/CR, citing papers 2019–21 and 2024–26).

Staging repository (not yet published). Contents follow an allow-list:
- `code/`: analysis scripts (Python 3.11, `requirements.txt`); every script takes `--seed` and writes to `results/`.
- `docs/`: preregistration (`PREREG_43.md`, its sha256 in `prereg_hash.txt`), amendments 1–3, the manual
  verification protocol.
- `theory/`: theorem statements and proofs with the measured numbers (§8).
- `results/`: derived tables (CSV/JSON < 50 MB) and figures. All files are final (`interim: false`).

Not included: arXiv source tarballs (not re-hosted; ids and sha256 are in the manifest of the data pipeline), API
caches, the DBLP dump. Raw data are read from `$THS_DATASETS` (see `code/ground_truth.py`).

Main entry points (from `code/`, seed 42):
```
python p1_backend_table.py --seed 42      # u_s by tier x cumulative backend (main table)
python p1_hypotheses.py --seed 42         # H1, H2
python screen_baseline.py --phase p1 --seed 42 --boot 1000   # render -> parse -> screen, H3
python p1_h4_bias.py --seed 42            # H4 + per-tier selection-bias coefficients
python p1_theory_tables.py --seed 42      # Thm 1'/2', H5, alpha-safe rules
python p1_kappa.py --pass2 <csv> --seed 42  # test-retest agreement of the manual check
```
