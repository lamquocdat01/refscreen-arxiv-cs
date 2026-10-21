#!/usr/bin/env python3
"""Topic 43 / P2 / T10a condition 3: one more pass over the references still rate-limited after P1 run10
(def 1: 1 + 57, def 2: 52 + 330; PREREG_AMENDMENT_4 "What does not change").

Each such reference is re-resolved with ground_truth_p1.resolve_ref (same cascade, same threshold; S2 live, with
S2_API_KEY if it is set in the environment, keyless otherwise). The P1 files are not modified. The new statuses are
written separately and the u_s cells (period x tier x definition) are compared with the P1 cells: the main table is to
be updated only if a cell changes by >= 0.05 percentage points (Amendment 4); both versions are reported.
Outputs: $THS_DATASETS/_derived/43/p2_retry_ratelimited.csv, results/p2_retry_ratelimited.csv (cells before/after),
         results/p2_retry_ratelimited.json
Usage: python p2_retry_ratelimited.py --seed 42 [--workers 2]   (run once, at night when keyless)
"""
import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ground_truth_p1 as gt1  # noqa: E402
from ground_truth import DATA, ROOT  # noqa: E402

TIERS = ["J", "C", "P", "B", "S", "W"]


def cells(df):
    out = []
    for d in ("def1", "def2"):
        st = f"{d}_status"
        ev = df[df[st].isin(["resolved", "unresolved"])]
        for per, g in ev.groupby("period"):
            for t in TIERS + ["A"]:
                x = g[g.tier.isin(["J", "C", "P"])] if t == "A" else g[g.tier == t]
                k = int((x[st] == "unresolved").sum())
                out.append(dict(definition=d, period=per, tier=t, n=len(x), k=k, u=k / len(x) if len(x) else None,
                                n_rate_limited=int((df[(df.period == per) & ((df.tier.isin(["J", "C", "P"])) if t == "A"
                                                   else (df.tier == t))][st] == "rate-limited").sum())))
    return pd.DataFrame(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()
    full = pd.read_csv(DATA / "_derived" / "43" / "p1_groundtruth_refs_full.csv", dtype=str, keep_default_na=False,
                       low_memory=False)
    rl = full[(full.def1_status == "rate-limited") | (full.def2_status == "rate-limited")].copy()
    print(f"rate-limited refs: {len(rl)} (def1 {int((rl.def1_status == 'rate-limited').sum())}, "
          f"def2 {int((rl.def2_status == 'rate-limited').sum())}); S2 key: {'yes' if os.environ.get('S2_API_KEY') else 'no'}",
          flush=True)
    recs = []
    for r in rl.to_dict("records"):
        r = dict(r)
        r["has_arxiv"] = int(r.get("has_arxiv") or 0)
        recs.append(r)
    gt1.run_resolution(recs, args.workers, "retry", s2_live=True)
    new = pd.DataFrame(recs)
    new.to_csv(DATA / "_derived" / "43" / "p2_retry_ratelimited.csv", index=False)
    upd = full.set_index(["arxiv_id", "key"]).copy()
    nn = new.set_index(["arxiv_id", "key"])
    for c in ("def1_status", "def2_status"):
        upd.loc[nn.index, c] = nn[c].astype(str)
    upd = upd.reset_index()
    before, after = cells(full), cells(upd)
    m = before.merge(after, on=["definition", "period", "tier"], suffixes=("_p1", "_p2"))
    m["delta_pp"] = (m.u_p2 - m.u_p1) * 100
    m["update_main_table"] = m.delta_pp.abs() >= 0.05
    m["interim"] = False
    m.to_csv(ROOT / "results" / "p2_retry_ratelimited.csv", index=False)
    trans = new.groupby(["def1_status"]).size().to_dict()
    meta = dict(interim=False, seed=args.seed, s2_key=bool(os.environ.get("S2_API_KEY")), n_retried=len(new),
                def1_after=trans, def2_after=new.def2_status.value_counts().to_dict(),
                cells_changed_ge_0_05pp=int(m.update_main_table.sum()),
                max_abs_delta_pp=float(m.delta_pp.abs().max()))
    (ROOT / "results" / "p2_retry_ratelimited.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(json.dumps(meta, indent=1))
    print(m[m.update_main_table][["definition", "period", "tier", "k_p1", "n_p1", "k_p2", "n_p2", "delta_pp"]].to_string())


if __name__ == "__main__":
    main()
