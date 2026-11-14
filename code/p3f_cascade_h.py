#!/usr/bin/env python3
"""Topic 43 / P3F (PREREG_AMENDMENT_8 (H)): complete the cascade for the 2019-21 B, S, W targets of Amendment 7 (a).

Runs only when the Addendum-2 cascade process has ended. Order, threshold, rules and the header budget stop are those of
Addendum 2 (group 3, then 5, then 6, seed-42 permutation inside a group, as in P3E/cascade_targets.csv). One call of this
script is one pass. Finished work: P3F/cascade_h_passes.json, P3F/cascade_h.log; p3e_groundtruth_refs_full.csv and
P3E/cascade_targets.csv are rewritten by p3e_complete_cascade.write_outputs from a full offline replay plus this pass.
Usage: python code/p3f_cascade_h.py [--dry]
"""
import argparse
import datetime as dt
import json
import shutil
import sys
import time
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3e_complete_cascade as cc  # noqa: E402
import refmatch as rm  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "P3F"
PASSES = OUT / "cascade_h_passes.json"
DONE = OUT / "cascade_h_done.json"
END = dt.datetime(2026, 11, 12, 23, 59, tzinfo=dt.timezone.utc)
H_BASE = 100  # pass numbers of this extension: 101, 102, ...


def cascade_running():
    for p in psutil.process_iter(["pid", "cmdline"]):
        try:
            if any("p3e_complete_cascade.py" in (c or "") for c in (p.info["cmdline"] or [])):
                return p.info["pid"]
        except (psutil.Error, TypeError):
            continue
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="count only; no request, no file written")
    args = ap.parse_args()
    cc.LOG = OUT / "cascade_h.log"
    if not args.dry:
        for _ in range(60):  # the cascade writes "complete" just before its process ends
            if not cascade_running():
                break
            time.sleep(10)
        if cascade_running():
            sys.exit(f"cascade process {cascade_running()} is still running; (H) waits for it")
    cc.install()
    cc._OA_KEY["value"] = cc.read_env_key()
    d = cc.load()
    targets = cc.build_targets(d, 42)
    rows = {r.arxiv_id + "/" + r.key: r for r in d[d.target].drop_duplicates(["arxiv_id", "key"]).itertuples()}
    rows = {k: v._asdict() for k, v in rows.items()}
    attrib = cc.load_attrib()
    results = {}
    cc.run_pass(0, list(targets.ref_id), rows, results, 42, offline=True, attrib=attrib)  # replay from the caches
    rm.OFFLINE = False
    scope = set(targets.ref_id[(targets.period == "2019-21") & targets.tier.isin(["B", "S", "W"])])
    todo = [x for x in targets.sort_values("order").ref_id if x in scope and not cc.answered(results[x])]
    n_acad_left = sum(1 for x in targets.ref_id if rows[x]["tier"] in ("J", "C", "P") and not cc.answered(results[x]))
    cc.log(f"(H): {len(todo)} of {len(scope)} B/S/W 2019-21 targets lack an answer; academic scope left {n_acad_left}")
    if args.dry:
        return
    state = json.loads(PASSES.read_text(encoding="utf-8")) if PASSES.exists() else {"passes": []}
    if not todo:
        DONE.write_text(json.dumps({"complete": True, "n_scope": len(scope), "time": cc.stamp() if hasattr(cc, "stamp") else ""}), encoding="utf-8")
        return
    if dt.datetime.now(dt.timezone.utc) > END:
        cc.log("(H): end date passed; the interval rule of Amendment 7 (a) applies to what is left")
        DONE.write_text(json.dumps({"complete": False, "n_scope": len(scope), "n_left": len(todo)}), encoding="utf-8")
        return
    gt_file = cc.DER / "p3e_groundtruth_refs_full.csv"
    bak = cc.DER / "p3e_groundtruth_refs_full.bak_before_H.csv"
    if not bak.exists():
        shutil.copyfile(gt_file, bak)
    k = H_BASE + len(state["passes"]) + 1
    info = cc.run_pass(k, todo, rows, results, 42, offline=False, attrib=attrib, deadlines={"2019-21": END})
    info["addendum"] = "Amendment 8 (H)"
    info["scope"] = "2019-21 B/S/W targets of Amendment 7 (a)"
    state["passes"].append(info)
    PASSES.write_text(json.dumps(state, indent=1), encoding="utf-8")
    cc.save_attrib(attrib)
    cc.write_outputs(d, targets, results)
    left = sum(1 for x in todo if not cc.answered(results[x]))
    cc.log(f"(H) pass {k} done: {len(todo) - left}/{len(todo)} answered in this pass; {left} left")
    if left == 0:
        DONE.write_text(json.dumps({"complete": True, "n_scope": len(scope)}), encoding="utf-8")


if __name__ == "__main__":
    main()
