#!/usr/bin/env python3
"""Topic 43 / P3G: collect the post-hoc P3G results into results/numbers.json under keys ending in _p3g (earlier keys
untouched), plus two registered-reporting items that need no new analysis:
  nonacad_interval_2024_26_p3g  B/S/W 2024-26 under the full cascade as an interval (Amendment 7 / Table 4: references
                                that OpenAlex never answered count as resolved (lower) or unresolved (upper))
  audit_split_p3g               the recall-drop audit by labelled set and audit label, with the auditor recorded
Offline. Usage: python code/p3g_numbers.py
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ground_truth_p1 as gt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"


def J(f):
    return json.loads((RES / f).read_text(encoding="utf-8"))


def nonacad_interval():
    d = pd.read_csv(gt.DERIVED / "p3e_groundtruth_refs_full.csv", dtype=str, keep_default_na=False, low_memory=False)
    d = d[d.def1_status.isin(["resolved", "unresolved"]) & (d.period == "2024-26")]
    out = {}
    for t in ("B", "S", "W"):
        g = d[d.tier == t]
        u = g.def1_status == "unresolved"
        sk = g.oa_skipped.astype(str).isin(["1", "1.0", "True"])
        out[t] = dict(n=len(g), U=int(u.sum()), U_oa_unanswered=int((u & sk).sum()), lower=float((u & ~sk).sum() / len(g)),
                      upper=float(u.sum() / len(g)))
    return out


def audit_split():
    a = pd.read_csv(RES / "p2_recall_drop_audit.csv", dtype=str, keep_default_na=False)
    return dict(by_set_label=a.groupby(["set", "audit_label"]).size().unstack(fill_value=0).to_dict("index"),
                auditor=a.auditor.value_counts().to_dict(), n=len(a),
                note="auditor CC = Claude Code (an AI coding agent), evidence URL per row")


def rows_units():
    """Deep-search counts of the academic sets in rows of the ground truth (the unit of N and U), and in distinct refs."""
    import p3f_bounds as fb
    x = fb.rd(RES / "p3f_deep_search.csv")
    d = fb.attach(fb.frame(), x)
    src = x.set_index("ref_id").source
    dep = x.set_index("ref_id").depth_reason
    out = {}
    for per, s in (("2019-21", "acad1921"), ("2024-26", "acad2426")):
        g = d[(d.period == per) & d.tier.isin(["J", "C", "P"]) & (d.u == 1)]
        f = g[g.f == 1]
        xs = x[x.set == s]
        out[per] = dict(rows=dict(U=len(g), F=int(g.f.sum()), not_found=int(g.r_notfound.sum()), unanswered=int(g.r_unans.sum()),
                                  F_by_source=f.ref_id.map(src).value_counts().to_dict(),
                                  F_by_depth=f.ref_id.map(dep).value_counts().to_dict()),
                        distinct=dict(U=len(xs), F=int((xs.state == "found").sum()), not_found=int((xs.state == "not found").sum()),
                                      unanswered=int((xs.state == "unanswered").sum())))
    return out


def main():
    nums = json.loads((RES / "numbers.json").read_text(encoding="utf-8"))
    for k in [k for k in nums if k.endswith("_p3g")]:
        del nums[k]
    nums["branch_split_p3g"] = J("p3g_branch_split.json")
    nums["two_ends_p3g"] = J("p3g_two_ends.json")
    nums["bounds_p3g"] = J("p3g_bounds.json")
    nums["policy_coding_p3g"] = J("p3g_policy_coding.json")
    nums["nonacad_interval_2024_26_p3g"] = nonacad_interval()
    nums["audit_split_p3g"] = audit_split()
    nums["units_p3g"] = rows_units()
    (RES / "numbers.json").write_text(json.dumps(nums, indent=1, default=float), encoding="utf-8")
    print("numbers.json keys _p3g:", [k for k in nums if k.endswith("_p3g")])


if __name__ == "__main__":
    main()
