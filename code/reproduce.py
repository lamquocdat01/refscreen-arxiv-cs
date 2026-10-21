#!/usr/bin/env python3
"""Topic 43: reproduce the offline part of the pipeline from the committed ground truth + API cache, and check that
the numbers match the committed ones key by key (C7(h)).

Run it in a fresh clone (the scripts write to <clone>/results/): it snapshots the committed outputs, reruns
  p1_backend_table.py, p1_hypotheses.py, p1_h5_betabinom.py --boot 200, p2_render_manual_fp.py, p2_theory_final.py
(all --seed 42; no network: every answer comes from $THS_DATASETS/_derived/43/cache), then compares
  results/numbers.json        key by key (numbers: |a - b| <= 1e-9 * max(1, |a|); other values: equal)
  the CSV outputs             cell by cell as text, after dropping the `interim` column (the P1 stamp)
and exits 1 on any difference. The render/screen and ground-truth stages need the arXiv sources and are not rerun.
Usage: python code/reproduce.py        (or: make reproduce)
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RES = HERE.parent / "results"
STEPS = [["p1_backend_table.py", "--seed", "42"], ["p1_hypotheses.py", "--seed", "42"],
         ["p1_h5_betabinom.py", "--seed", "42", "--boot", "200"], ["p2_render_manual_fp.py", "--seed", "42"],
         ["p2_theory_final.py", "--seed", "42"]]
CSVS = ["p1_backend_table.csv", "p1_h5_betabinom.csv", "p2_render_manual_fp.csv", "p2_theory_final.csv"]
JSONS = ["numbers.json", "p1_hypotheses_h1h2.json", "p1_h5_betabinom.json", "p2_render_manual_fp.json"]


def flat(d, pre=""):
    if isinstance(d, dict):
        for k, v in d.items():
            yield from flat(v, f"{pre}.{k}" if pre else str(k))
    elif isinstance(d, list):
        for i, v in enumerate(d):
            yield from flat(v, f"{pre}[{i}]")
    else:
        yield pre, d


def same(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        if a != a and b != b:  # both NaN
            return True
        return abs(a - b) <= 1e-9 * max(1.0, abs(a))
    return a == b


def main():
    snap = Path(tempfile.mkdtemp(prefix="refscreen_snap_"))
    for f in CSVS + JSONS:
        shutil.copy2(RES / f, snap / f)
    for step in STEPS:
        print(">>", " ".join(step), flush=True)
        r = subprocess.run([sys.executable, str(HERE / step[0])] + step[1:], cwd=HERE,
                           env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode:
            print(r.stdout[-2000:], r.stderr[-2000:])
            sys.exit(f"step failed: {step[0]}")
    bad = 0
    for f in JSONS:
        a = dict(flat(json.loads((snap / f).read_text(encoding="utf-8"))))
        b = dict(flat(json.loads((RES / f).read_text(encoding="utf-8"))))
        a.pop("interim", None), b.pop("interim", None)
        diff = sorted(k for k in set(a) | set(b) if k not in a or k not in b or not same(a[k], b[k]))
        print(f"{f}: {len(a)} keys, {len(diff)} differ", *(f"\n   {k}: {a.get(k)} -> {b.get(k)}" for k in diff[:10]))
        bad += len(diff)
    for f in CSVS:
        a = pd.read_csv(snap / f, dtype=str, keep_default_na=False).drop(columns="interim", errors="ignore")
        b = pd.read_csv(RES / f, dtype=str, keep_default_na=False).drop(columns="interim", errors="ignore")
        if a.shape != b.shape or list(a.columns) != list(b.columns):
            print(f"{f}: shape/columns differ {a.shape} vs {b.shape}")
            bad += 1
            continue
        na = pd.to_numeric(a.stack(), errors="coerce").unstack()
        nb = pd.to_numeric(b.stack(), errors="coerce").unstack()
        num = na.notna() & nb.notna()
        dn = ((na - nb).abs() > 1e-9 * na.abs().clip(lower=1)) & num
        dt = (a != b) & ~num
        n = int(dn.values.sum() + dt.values.sum())
        print(f"{f}: {a.size} cells, {n} differ")
        bad += n
    print("REPRODUCED: all checked numbers identical" if not bad else f"DIFFERENCES: {bad}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
