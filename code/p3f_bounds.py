#!/usr/bin/env python3
"""Topic 43 / P3F (PREREG_AMENDMENT_8 (E), (F), (G), (J), Depth): results/p3f_gt3_summary.json from stored GT-3 states.
Offline. Reads results/p3f_deep_search.csv and the completed ground truth. Bootstrap: papers, B = 1000, seed 42, f_hi fixed.
Usage: python code/p3f_bounds.py [--partial]   (--partial: allowed before GT-3 is complete; labels the output INTERIM)
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ground_truth_p1 as gt  # noqa: E402
from p3c_validity import cp  # noqa: E402
from screen_baseline import _bib_flags  # noqa: E402
from p1_backend_table import first_hit_stage  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
TIERS = ["J", "C", "P", "B", "S", "W"]
ACAD = ["J", "C", "P"]
B, SEED = 1000, 42


def rd(p):
    return pd.read_csv(p, dtype=str, keep_default_na=False, low_memory=False)


def prop(k, n):
    return dict(k=int(k), n=int(n), rate=(k / n) if n else None, cp95=cp(int(k), int(n)) if n else None)


def false_match(x, partial=False):
    fam = {}
    y = x[x.set == "decoy"]
    dec = rd(RES / "p3f_decoys.csv").set_index("decoy_id").family
    y = y.assign(family=y.ref_id.map(dec))
    # partial (smoke test only): sources still pending are read as "no match so far", so f is a lower figure
    ans = y.state.isin(["found", "not found"]) | (partial & (y.state == "unanswered"))
    for name, m in (("D-splice", y.family == "D-splice"), ("gen_a", y.family == "gen_a"), ("pooled", y.family != "")):
        k, n = int((m & (y.state == "found")).sum()), int((m & ans).sum())
        fam[name] = dict(prop(k, n), n_unanswered=int((m & ~ans).sum()), f_hi=cp(k, n)[1] if n else None)
    fam["f_hi_used"] = max(fam["D-splice"]["f_hi"] or 0, fam["pooled"]["f_hi"] or 0)
    return fam


def frame():
    d = rd(gt.DERIVED / "p3e_groundtruth_refs_full.csv")
    d = d[d.def1_status.isin(["resolved", "unresolved"])].copy()
    d["ref_id"] = d.arxiv_id + "/" + d.key
    d["u"] = (d.def1_status == "unresolved").astype(int)
    return d


def attach(d, x):
    s = x[x.set.isin(["acad1921", "acad2426", "nonacad1921"])].set_index("ref_id").state
    d["gt3"] = d.ref_id.map(s).fillna("")
    d["f"] = ((d.u == 1) & (d.gt3 == "found")).astype(int)
    d["r"] = ((d.u == 1) & d.gt3.isin(["not found", "unanswered"])).astype(int)
    d["r_notfound"] = ((d.u == 1) & (d.gt3 == "not found")).astype(int)
    d["r_unans"] = ((d.u == 1) & (d.gt3 == "unanswered")).astype(int)
    d["not_in_set"] = ((d.u == 1) & (d.gt3 == "")).astype(int)
    return d


def boot_cell(g, f_hi, rng):
    p = g.groupby("arxiv_id")[["u", "r", "n1"]].sum()
    a, n = p.values, len(p)
    idx = rng.integers(0, n, (B, n))
    s = a[idx].sum(1)
    x_hi = s[:, 1] / (1 - f_hi)
    lo = np.maximum(0, s[:, 0] - x_hi) / s[:, 2]
    hi = s[:, 0] / s[:, 2]
    return np.quantile(lo, [.025, .975]).tolist(), np.quantile(hi, [.025, .975]).tolist()


def cell(g, f_hi, boot=True):
    g = g.assign(n1=1)
    N, U, F, R = len(g), int(g.u.sum()), int(g.f.sum()), int(g.r.sum())
    out = dict(N=N, U=U, F=F, R=R, R_not_found=int(g.r_notfound.sum()), R_unanswered=int(g.r_unans.sum()), not_in_set=int(g.not_in_set.sum()),
               U_over_N=U / N if N else None, F_over_U=F / U if U else None, R_over_N=R / N if N else None, n_papers=int(g.arxiv_id.nunique()))
    if f_hi is not None and N:
        x = R / (1 - f_hi)
        out.update(X_hi=x, fp_lower=max(0.0, U - x) / N, fp_upper=U / N, bias_bound_X_hi_over_N=x / N)
        if boot:
            lo_ci, hi_ci = boot_cell(g, f_hi, np.random.default_rng(SEED))
            out.update(fp_lower_ci=lo_ci, fp_upper_ci=hi_ci)
    return out


def diff_rn(d, keep):
    a = d[(d.period == "2019-21") & keep]
    b = d[(d.period == "2024-26") & keep]
    pa, pb = [x.assign(n1=1).groupby("arxiv_id")[["r", "n1"]].sum().values for x in (a, b)]
    rng = np.random.default_rng(SEED)
    sa, sb = pa[rng.integers(0, len(pa), (B, len(pa)))].sum(1), pb[rng.integers(0, len(pb), (B, len(pb)))].sum(1)
    dd = sb[:, 0] / sb[:, 1] - sa[:, 0] / sa[:, 1]
    return dict(r_over_n_1921=pa[:, 0].sum() / pa[:, 1].sum(), r_over_n_2426=pb[:, 0].sum() / pb[:, 1].sum(),
                diff=pb[:, 0].sum() / pb[:, 1].sum() - pa[:, 0].sum() / pa[:, 1].sum(), ci=np.quantile(dd, [.025, .975]).tolist())


def h4_auto(d, f_hi):
    g = d[d.period == "2019-21"]
    frame_ = g[(g.has_doi == "0") & (g.has_arxiv == "0")]
    w = frame_.tier.value_counts(normalize=True).reindex(ACAD).fillna(0)
    w = w / w.sum()
    non = frame_[frame_.tier.isin(ACAD)]
    cert = g[g.certified_real == "1"]
    gnum = g.assign(n1=1)
    cert_u = cert.assign(n1=1).groupby("arxiv_id")[["u", "n1"]].sum()
    tiers_data = {}
    papers = sorted(set(non.arxiv_id) | set(cert.arxiv_id))
    pc = cert_u.reindex(papers).fillna(0).values
    for t in ACAD:
        x = non[non.tier == t].assign(n1=1).groupby("arxiv_id")[["u", "r", "n1"]].sum()
        tiers_data[t] = x.reindex(papers).fillna(0).values

    def stat(pc_s, sums):
        fc = pc_s[0] / pc_s[1]
        lo = sum(w[t] * max(0.0, sums[t][0] - sums[t][1] / (1 - f_hi)) / sums[t][2] for t in ACAD if sums[t][2])
        hi = sum(w[t] * sums[t][0] / sums[t][2] for t in ACAD if sums[t][2])
        return fc, lo, hi

    pt = stat(pc.sum(0), {t: tiers_data[t].sum(0) for t in ACAD})
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(papers), (B, len(papers)))
    ds = []
    for row in idx:
        fc, lo, hi = stat(pc[row].sum(0), {t: tiers_data[t][row].sum(0) for t in ACAD})
        ds.append((lo - fc, hi - fc))
    a = np.array(ds)
    ci_lo, ci_hi = np.quantile(a[:, 0], [.025, .975]).tolist(), np.quantile(a[:, 1], [.025, .975]).tolist()
    verdict = "supports" if ci_lo[0] > 0 else ("contradicts" if ci_hi[1] < 0 else "undetermined")
    return dict(weights=w.to_dict(), fp_certified=pt[0], fp_nonid_lower=pt[1], fp_nonid_upper=pt[2], diff_lower=pt[1] - pt[0], diff_upper=pt[2] - pt[0],
                diff_lower_ci=ci_lo, diff_upper_ci=ci_hi, verdict=verdict, label="H4-auto (exploratory, Amendment 8 (J))",
                n_nonid_academic=int(len(non)), n_certified=int(len(cert)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--partial", action="store_true")
    args = ap.parse_args()
    x = rd(RES / "p3f_deep_search.csv")
    fm = false_match(x, args.partial)
    f_hi = fm["f_hi_used"]
    d = attach(frame(), x)
    out = {"label": "GT-3 summary (Amendment 8)", "interim": bool(args.partial), "false_match": fm, "seed": SEED, "B": B}
    c = {}
    for per in ("2019-21", "2024-26"):
        for t in TIERS + ["A"]:
            g = d[(d.period == per) & ((d.tier == t) if t != "A" else d.tier.isin(ACAD))]
            c[f"{per}|{t}"] = cell(g, f_hi if per == "2019-21" else None, boot=per == "2019-21")
    out["cells"] = c
    out["rn_diff_academic"] = diff_rn(d, d.tier.isin(ACAD))
    posc = x[x.set == "posctl"]
    out["posctl"] = dict(found=int((posc.state == "found").sum()), n=len(posc), n_unanswered=int((posc.state == "unanswered").sum()),
                         recall=prop((posc.state == "found").sum(), len(posc)))
    dep = x[(x.state == "found") & x.set.isin(["acad1921", "acad2426", "nonacad1921"])]
    out["depth"] = {s: dep[dep.set == s].groupby(["depth_reason"]).size().to_dict() for s in ["acad1921", "acad2426", "nonacad1921"]}
    out["depth_source"] = {s: dep[dep.set == s].groupby(["source"]).size().to_dict() for s in ["acad1921", "acad2426", "nonacad1921"]}
    out["h4_auto"] = h4_auto(d, f_hi)
    out["states"] = x.groupby(["set", "state"]).size().rename("n").reset_index().to_dict("records")
    target = (ROOT / "P3F" / "interim_gt3_summary.json") if args.partial else (RES / "p3f_gt3_summary.json")  # interim never in results/
    target.write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("false_match", "posctl", "depth", "rn_diff_academic", "h4_auto")}, indent=1, default=float))
    for k in ("2019-21|J", "2019-21|C", "2019-21|P", "2019-21|A"):
        v = c[k]
        print(k, {q: (round(v[q], 5) if isinstance(v[q], float) else v[q]) for q in ("N", "U", "F", "R", "fp_lower", "fp_upper", "fp_lower_ci", "fp_upper_ci", "X_hi")})


if __name__ == "__main__":
    main()
