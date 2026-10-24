# Topic 43 — supplementary material (assembled 2026-10-24, before P3)

- `prereg/`: the pre-registration and its four amendments, with the manual verification protocol and the
  sha256 file frozen at registration time (`prereg_hash.txt`; `sha256sum -c` passes on 2026-10-24).
- `diag_audit/`: diagnostics and audits cited in the report.
  - `P1_DIAG_JC60_20261019.md`, `p1_diag*.{csv,json}`: unresolved J/C references and the normalisation fix (Amendment 2).
  - `p2_recall_drop_audit.csv`, `p2_recall_audit.json`, `p2_recall_audited.csv`: hand audit of the 15 fabricated
    references whose screen verdict changed.
- `SHA256SUMS`: hashes of every file in this folder.
Copies only; the working files stay in the topic folder / repo `results/`.
