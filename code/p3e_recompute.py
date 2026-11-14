#!/usr/bin/env python3
"""Topic 43 / P3E (PREREG_AMENDMENT_7 (a), "Use"): recompute every derived number on the completed ground truth with
the unchanged earlier scripts, without overwriting any earlier output.

How: a work copy outside the synced drive ($THS_DATASETS/_derived/43/p3e_work/) gets code/, results/, data_manifest/
and figures/ of the topic, and a private data root whose _derived/43/ holds the completed ground truth
(p3e_groundtruth_refs_full.csv, written by p3e_complete_cascade.py) under both names the scripts read
(p1_groundtruth_refs_full.csv, p2_groundtruth_refs_full.csv) plus screen_p1/screen_refs.csv. results/p1_groundtruth.csv
and results/p1_groundtruth.json of the copy are rebuilt from the completed ground truth (ground_truth_p1 columns and
summarise()). The earlier pipeline then runs in the copy (all --seed 42, offline):
  p1_backend_table (p1 and p2_backend_table_retry names), p1_hypotheses, p1_h4_bias, p1_theory_tables,
  p1_h5_betabinom --boot 200, p1_period_compare, p2_theory_final, p3d_theory_fix, p3_revision_checks, p2_figures,
  p3e_exploratory
Outputs copied back with the suffix _p3e: results/<stem>_p3e.<ext> for every file in OUTPUTS, figures/<F>_p3e.{pdf,png,
sources.txt} (sidecar paths rewritten to the _p3e names), and results/numbers.json gains, for every top-level key k of
the recomputed numbers.json, the key "k_p3e" (earlier keys untouched); numbers.tex is regenerated.
Usage: python code/p3e_recompute.py [--keep]
"""
import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = Path(os.environ.get("THS_DATASETS", r"D:\Datasets"))
DER = DATA / "_derived" / "43"
W = DER / "p3e_work"
WDATA = W / "data"
WDER = WDATA / "_derived" / "43"
STEPS = [["p1_backend_table.py", "--seed", "42"],
         ["p1_backend_table.py", "--seed", "42", "--input", "{WDER}/p2_groundtruth_refs_full.csv",
          "--name", "p2_backend_table_retry"],
         ["p1_hypotheses.py", "--seed", "42"], ["p1_h4_bias.py", "--seed", "42"],
         ["p1_theory_tables.py", "--seed", "42"], ["p1_h5_betabinom.py", "--seed", "42", "--boot", "200"],
         ["p1_period_compare.py", "--seed", "42"], ["p2_theory_final.py", "--seed", "42"],
         ["p3d_theory_fix.py", "--seed", "42"], ["p3_revision_checks.py", "--seed", "42"],
         ["p2_figures.py", "--seed", "42"], ["p3e_exploratory.py", "--seed", "42"]]
OUTPUTS = ["p1_groundtruth.csv", "p1_groundtruth.json", "p1_backend_table.csv", "p1_backend_table.json",
           "p2_backend_table_retry.csv", "p2_backend_table_retry.json", "p1_hypotheses_h1h2.json",
           "p1_h4_bias.csv", "p1_h4_bias.json", "p1_theory_tables.csv", "p1_theory_headlines.json", "p1_h5.csv",
           "p1_alpha_rules.csv", "p1_h5_betabinom.csv", "p1_h5_betabinom.json", "p1_paper_u.csv",
           "p1_period_compare.csv", "p1_period_compare.json", "p2_theory_final.csv", "p3d_theory_fix.csv",
           "p3d_theory_fix.json", "p3_revision_checks.json", "p3e_exploratory.json", "p3e_exploratory.csv"]
FIGS = ["F1_four_verdicts", "F2_roc_backend", "F2b_roc_backend_original_labels", "F3_ppv_ceiling", "F4_pff_vs_n",
        "F5_fp_style", "F6_u_by_tier"]
GT_COLS = ["arxiv_id", "set", "period", "field", "year", "key", "entrytype", "tier", "ref_source", "has_doi",
           "has_arxiv", "certified_real", "def1_status", "def2_status", "backends_hit", "s2_pending", "oa_skipped",
           "p0_paper"]


def p3e_name(f):
    p = Path(f)
    return f"{p.stem}_p3e{p.suffix}"


def _rm(path):
    def onerr(fn, p, _):  # read-only entries copied from the drive
        os.chmod(p, stat.S_IWRITE)
        fn(p)
    if path.exists():
        shutil.rmtree(path, onerror=onerr)


def prepare(src_gt=None):
    _rm(W)
    for sub in ("code", "results", "data_manifest", "figures"):
        base = shutil.ignore_patterns("__pycache__", "interim")
        shutil.copytree(ROOT / sub, W / sub, ignore=lambda dp, names: set(base(dp, names)) | set(
            n for n in names if __import__("package_exclude").excluded(n)))  # never .env / key material
    (W / "results" / "interim").mkdir(exist_ok=True)
    WDER.mkdir(parents=True)
    src = Path(src_gt) if src_gt else DER / "p3e_groundtruth_refs_full.csv"
    for name in ("p1_groundtruth_refs_full.csv", "p2_groundtruth_refs_full.csv"):
        shutil.copyfile(src, WDER / name)
    (WDER / "screen_p1").mkdir()
    shutil.copyfile(DER / "screen_p1" / "screen_refs.csv", WDER / "screen_p1" / "screen_refs.csv")
    # results/p1_groundtruth.{csv,json} of the copy from the completed ground truth
    sys.path.insert(0, str(W / "code"))
    os.environ["THS_DATASETS"] = str(WDATA)
    import ground_truth_p1 as g  # noqa: E402 (imported from the copy, data root = the private one)
    df = pd.read_csv(src, dtype={"arxiv_id": str, "key": str}, low_memory=False)
    for c in ("has_doi", "has_arxiv", "certified_real", "s2_pending", "oa_skipped", "p0_paper", "dblp_missing"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    df[GT_COLS].rename(columns={"arxiv_id": "paper_id"}).to_csv(W / "results" / "p1_groundtruth.csv", index=False)
    pdf = pd.read_csv(W / "results" / "p1_groundtruth_papers.csv", dtype={"arxiv_id": str})
    p0 = set((W / "data_manifest" / "p0_papers.txt").read_text().split())
    out = g.summarise(df, pdf, 42, p0)
    out.update(smoke_test=False, limit=0, retry_rounds=True,
               label="P3E: completed cascade (PREREG_AMENDMENT_7 (a)); built by code/p3e_recompute.py")
    out.pop("generated", None)
    (W / "results" / "p1_groundtruth.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


def run():
    env = {**os.environ, "THS_DATASETS": str(WDATA), "PYTHONIOENCODING": "utf-8", "P3E_CACHE_ROOT": str(DER)}
    for st in STEPS:
        args = [a.replace("{WDER}", str(WDER)) for a in st[1:]]
        print(">>", st[0], " ".join(st[1:]), flush=True)
        r = subprocess.run([sys.executable, str(W / "code" / st[0])] + args, cwd=W / "code", env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode:
            print(r.stdout[-3000:], r.stderr[-3000:])
            sys.exit(f"step failed: {st[0]}")


def copy_back():
    res = ROOT / "results"
    for f in OUTPUTS:
        shutil.copyfile(W / "results" / f, res / p3e_name(f))
    for fg in FIGS:
        for ext in (".pdf", ".png"):
            if (W / "figures" / f"{fg}{ext}").exists():
                shutil.copyfile(W / "figures" / f"{fg}{ext}", ROOT / "figures" / f"{fg}_p3e{ext}")
        side = W / "figures" / f"{fg}.sources.txt"
        if side.exists():
            t = side.read_text(encoding="utf-8")
            for f in OUTPUTS + ["p2_recall.csv", "p2_recall_audited.csv", "p2_render_manual_fp.csv"]:
                if f in OUTPUTS:
                    t = t.replace(f"results/{f}", f"results/{p3e_name(f)}")
            t = t.replace(f"{fg} (seed", f"{fg}_p3e (seed", 1)
            (ROOT / "figures" / f"{fg}_p3e.sources.txt").write_text(t, encoding="utf-8")
    # numbers.json: add k_p3e for every top-level key of the recomputed file; earlier keys are not touched
    nums = json.loads((res / "numbers.json").read_text(encoding="utf-8"))
    new = json.loads((W / "results" / "numbers.json").read_text(encoding="utf-8"))
    for k in [k for k in nums if k.endswith("_p3e")]:
        del nums[k]
    for k, v in new.items():
        if not k.endswith("_p3e"):
            nums[f"{k}_p3e"] = v
    (res / "numbers.json").write_text(json.dumps(nums, indent=1, default=float), encoding="utf-8")
    sys.path.insert(0, str(HERE))
    import p2_theory_final as p2  # noqa: E402
    p2.RES = res
    p2.write_tex(nums)
    print(f"copied {len(OUTPUTS)} result files and {len(FIGS)} figures with suffix _p3e; numbers.json keys: "
          f"{sum(1 for k in nums if k.endswith('_p3e'))} with _p3e, {sum(1 for k in nums if not k.endswith('_p3e'))} earlier")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="keep the work copy")
    ap.add_argument("--input", default=None, help="testing only: another ground-truth file; nothing is copied back")
    args = ap.parse_args()
    prepare(args.input)
    run()
    if args.input:
        print("test run on", args.input, "- outputs left in", W)
        return
    copy_back()
    if not args.keep:
        _rm(W)


if __name__ == "__main__":
    main()
