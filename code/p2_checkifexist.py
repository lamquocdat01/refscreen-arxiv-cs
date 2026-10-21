#!/usr/bin/env python3
"""Topic 43 / P2 / T10c: non-determinism of CheckIfExist (zabbonat/References-Validation @ e4605651; P0 harness
tools/scripts/run_cie.mts) -- 3 runs, one after the other, on the same input PDF; appendix material.

Input: the IEEEtran-strip render of one hallucinator P2 paper ($THS_DATASETS/_derived/43/tools/hall_p2/<id>/
IEEEtran_strip/main.pdf). Per extracted reference, the status of each run (verified / partial_match / mismatch /
not_found); a reference "differs" if the 3 statuses are not all equal. Flag = not_found or mismatch.
Outputs: $THS_DATASETS/_derived/43/tools/cie_p2/run{1,2,3}.json, results/p2_checkifexist_runs.csv (per ref),
         results/p2_checkifexist.json (summary)
Usage: python p2_checkifexist.py --paper 2403.11482 [--runs 3]
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ground_truth import DATA, ROOT  # noqa: E402

REPO = Path(r"D:\Repos\_tools43\References-Validation")
HARNESS = Path(r"D:\Repos\_tools43\harness43\run_cie.mts")
TSX = REPO / "mcp-server" / "node_modules" / ".bin" / "tsx.cmd"
FLAG = {"not_found", "mismatch"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper", default="2403.11482")
    ap.add_argument("--runs", type=int, default=3)
    args = ap.parse_args()
    pdf = DATA / "_derived" / "43" / "tools" / "hall_p2" / args.paper / "IEEEtran_strip" / "main.pdf"
    out = DATA / "_derived" / "43" / "tools" / "cie_p2"
    out.mkdir(parents=True, exist_ok=True)
    runs = []
    for k in range(1, args.runs + 1):
        js = out / f"run{k}.json"
        t0 = time.time()
        p = subprocess.run([str(TSX), str(HARNESS), str(REPO), str(pdf), str(js)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=3600, cwd=REPO / "mcp-server")
        print(f"run {k}: rc={p.returncode} {time.time() - t0:.0f}s", flush=True)
        if p.returncode:
            print(p.stderr[-1500:])
        d = json.loads(js.read_text(encoding="utf-8"))
        runs.append(d)
    n = min(len(d["results"]) for d in runs)
    rows = []
    for i in range(n):
        st = [d["results"][i]["status"] for d in runs]
        rows.append(dict(index=i + 1, input=runs[0]["results"][i]["input"][:300],
                         **{f"run{k + 1}": s for k, s in enumerate(st)},
                         differs=len(set(st)) > 1, flag_differs=len({s in FLAG for s in st}) > 1))
    df = pd.DataFrame(rows)
    df.insert(0, "interim", "False")
    df.to_csv(ROOT / "results" / "p2_checkifexist_runs.csv", index=False)
    summ = dict(interim=False, tool="CheckIfExist @ e4605651 (P0 harness)", paper=args.paper,
                input="IEEEtran strip render (main.pdf)", runs=args.runs,
                n_extracted=[len(d["results"]) for d in runs], counts=[d["counts"] for d in runs],
                runtime_s=[d["runtime_s"] for d in runs], http_requests=[d["http_requests"] for d in runs],
                n_compared=n, n_status_differs=int(df.differs.sum()), n_flag_differs=int(df.flag_differs.sum()),
                flagged_per_run=[int(sum(s in FLAG for s in df[f"run{k + 1}"])) for k in range(args.runs)])
    (ROOT / "results" / "p2_checkifexist.json").write_text(json.dumps(summ, indent=1), encoding="utf-8")
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
