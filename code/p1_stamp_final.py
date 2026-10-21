#!/usr/bin/env python3
"""Topic 43 / P1: mark the main (non-interim) outputs in results/ as final: "interim": false.

JSON: a top-level "interim" key is added when missing (an existing value is left alone and reported if true).
CSV: a first column "interim" = False is added when missing. Only results/p1_*.{json,csv} written on or after
--since (local time) are touched; results/interim/ is never touched.
Usage: python p1_stamp_final.py --since "2026-10-20 21:45"
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ground_truth_p1 import ROOT  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True)
    args = ap.parse_args()
    t0 = datetime.strptime(args.since, "%Y-%m-%d %H:%M").timestamp()
    for f in sorted((ROOT / "results").glob("p1_*")):
        if f.suffix not in (".json", ".csv") or f.stat().st_mtime < t0:
            continue
        if f.suffix == ".json":
            d = json.loads(f.read_text(encoding="utf-8"))
            if not isinstance(d, dict):
                print(f"skip (not an object): {f.name}")
                continue
            if "interim" in d:
                print(f"{f.name}: interim={d['interim']} (kept)")
                continue
            f.write_text(json.dumps({"interim": False, **d}, indent=1, ensure_ascii=False, default=float),
                         encoding="utf-8")
        else:
            # read every cell as text: a float parse turns arXiv ids 2401.10 -> 2401.1 and re-rounds floats
            d = pd.read_csv(f, dtype=str, keep_default_na=False)
            if "interim" in d:
                print(f"{f.name}: interim column present (kept)")
                continue
            d.insert(0, "interim", "False")
            d.to_csv(f, index=False)
        print(f"stamped interim=false: {f.name}")


if __name__ == "__main__":
    main()
