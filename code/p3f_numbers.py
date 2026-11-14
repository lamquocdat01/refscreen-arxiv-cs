#!/usr/bin/env python3
"""Topic 43 / P3F (P3F2 Viec 3): collect the P3F results into results/numbers.json under keys *_p3f, plus the POST-HOC
sensitivity lines that P3F2 3b asks for (results/p3f_posthoc.json). Offline; earlier keys are not touched.

Keys written (each the whole JSON of its source file):
  gt3_p3f              results/p3f_gt3_summary.json        (Amendment 8 (E)-(G), (J), depth)
  tier_validation_p3f  results/p3f_tier_validation.json    (Amendment 8 (I))
  rB_score_p3f         results/p3f_rB_score.json           (Amendment 8 (B); Supplement only)
  rB_vs_gt3_p3f        results/p3f_rB_vs_gt3.json          (Supplement only)
  notfound_profile_p3f results/p3f_notfound_profile.json   (POST-HOC, descriptive)
  posthoc_p3f          results/p3f_posthoc.json            (POST-HOC, written here)
POST-HOC (P3F2 3a/3b, LQD 2026-11-11, after the interim GT-3 results were seen; registered rows are not replaced):
  coverage   share of unresolved references that no open source finds under the relaxed GT-3 rule (R_not_found / U)
  rn_notfound_only   R/N with R = not found only, both periods, difference with a paper bootstrap (B = 1000, seed 42)
  unanswered_by_source   unanswered share of GT-3 rows by period x missing source
Usage: python code/p3f_numbers.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3f_bounds as pb  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
FILES = {"gt3_p3f": "p3f_gt3_summary.json", "tier_validation_p3f": "p3f_tier_validation.json",
         "rB_score_p3f": "p3f_rB_score.json", "rB_vs_gt3_p3f": "p3f_rB_vs_gt3.json",
         "notfound_profile_p3f": "p3f_notfound_profile.json", "posthoc_p3f": "p3f_posthoc.json"}


def rn_diff(d, col):
    keep = d.tier.isin(pb.ACAD)
    a, b = d[(d.period == "2019-21") & keep], d[(d.period == "2024-26") & keep]
    pa, pbb = [x.assign(n1=1).groupby("arxiv_id")[[col, "n1"]].sum().values for x in (a, b)]
    rng = np.random.default_rng(pb.SEED)
    sa = pa[rng.integers(0, len(pa), (pb.B, len(pa)))].sum(1)
    sb = pbb[rng.integers(0, len(pbb), (pb.B, len(pbb)))].sum(1)
    dd = sb[:, 0] / sb[:, 1] - sa[:, 0] / sa[:, 1]
    r1, r2 = pa[:, 0].sum() / pa[:, 1].sum(), pbb[:, 0].sum() / pbb[:, 1].sum()
    return dict(r_over_n_1921=r1, r_over_n_2426=r2, diff=r2 - r1, ci=np.quantile(dd, [.025, .975]).tolist(),
                k_1921=int(pa[:, 0].sum()), n_1921=int(pa[:, 1].sum()), k_2426=int(pbb[:, 0].sum()), n_2426=int(pbb[:, 1].sum()))


def posthoc():
    x = pb.rd(RES / "p3f_deep_search.csv")
    d = pb.attach(pb.frame(), x)
    out = {"label": "POST-HOC (P3F2 3a/3b, LQD 2026-11-11, after interim GT-3 results); descriptive; registered rows unchanged",
           "seed": pb.SEED, "B": pb.B}
    cov = {}
    for per in ("2019-21", "2024-26"):
        g = d[(d.period == per) & d.tier.isin(pb.ACAD)]
        U, nf, un, F = int(g.u.sum()), int(g.r_notfound.sum()), int(g.r_unans.sum()), int(g.f.sum())
        cov[per] = dict(U=U, F=F, not_found=nf, unanswered=un, not_found_over_U=nf / U if U else None,
                        not_found_or_unanswered_over_U=(nf + un) / U if U else None, cp95_not_found_over_U=pb.cp(nf, U))
    out["coverage_academic"] = cov
    out["rn_registered"] = rn_diff(d, "r")
    out["rn_notfound_only"] = rn_diff(d, "r_notfound")
    un = {}
    for s, per in (("acad1921", "2019-21"), ("acad2426", "2024-26"), ("nonacad1921", "2019-21 B/S/W")):
        y = x[x.set == s]
        u = y[y.state == "unanswered"]
        miss = {}
        for m in u.missing_sources:
            for src in [q for q in m.replace(";", ",").split(",") if q.strip()]:
                miss[src.strip()] = miss.get(src.strip(), 0) + 1
        un[s] = dict(period=per, n=int(len(y)), unanswered=int(len(u)), share=len(u) / len(y) if len(y) else None,
                     by_missing_source={k: dict(k=v, share=v / len(y)) for k, v in sorted(miss.items())})
    out["unanswered_by_source"] = un
    (RES / "p3f_posthoc.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    return out


def main():
    posthoc()
    nums = json.loads((RES / "numbers.json").read_text(encoding="utf-8"))
    for k in [k for k in nums if k.endswith("_p3f")]:
        del nums[k]
    for k, f in FILES.items():
        p = RES / f
        if not p.exists():
            sys.exit(f"STOP: missing {p}")
        nums[k] = json.loads(p.read_text(encoding="utf-8"))
    (RES / "numbers.json").write_text(json.dumps(nums, indent=1, default=float), encoding="utf-8")
    print("numbers.json keys *_p3f:", sorted(k for k in nums if k.endswith("_p3f")))


if __name__ == "__main__":
    main()
