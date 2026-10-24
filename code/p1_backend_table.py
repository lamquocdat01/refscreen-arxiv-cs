#!/usr/bin/env python3
"""Topic 43 / P1: cumulative-backend table of u_s (def 1). Main table of the paper: FP depends on the backend set.

Columns follow the cascade order of PREREG_AMENDMENT_3: Crossref-only -> +arXiv -> +DBLP -> +OpenAlex -> +S2.
The cascade stops at the first backend that resolves, so the first hit gives the column where a reference becomes
resolved. The denominator is the same in every column: references whose final def-1 state is resolved/unresolved
(rate-limited after the retry rounds and no-title are excluded). A reference that is unresolved at the end counts as
unresolved in every column.
- arXiv applies only to references with an arXiv id or in tier P (Amendment 1), so for other references the
  "+arXiv" column equals Crossref-only.
- OpenAlex is keyless: references with oa_skipped = 1 had no OpenAlex answer, and their count is reported per cell.
Rows: period x tier (J, C, P, B, S, W, A = J+C+P, all, certified-real) plus P by identifier (arxiv-id / doi-only /
no-id, and P/with-id = arxiv-id + doi-only). CI: paper-level bootstrap (B = 1000) for every column = main CI; Wilson =
secondary. Rate-limited references after the retry rounds are excluded from the denominator and counted per row.
Input:  $THS_DATASETS/_derived/43/p1_groundtruth_refs_full.csv (ground_truth_p1.py)
Output: results/p1_backend_table.csv, results/p1_backend_table.json, results/p1_backend_table.png
Usage:  python p1_backend_table.py --seed 42 [--boot 1000] [--input <csv>] [--interim] [--name <stem>]
        --name: output stem (default p1_backend_table); P2 after the night retry:
        --input $THS_DATASETS/_derived/43/p2_groundtruth_refs_full.csv --name p2_backend_table_retry
        --interim: input $THS_DATASETS/_derived/43/interim/p1_groundtruth_refs_full.csv (ground_truth_p1.py --interim),
        output results/interim/ with "interim": true and "s2_pending": n. The +S2 column is written as
        "chưa hoàn tất, n_pending=<n>" and +OpenAlex (when no stored answer resolved a ref) as
        "không có dữ liệu (keyless 429)"; columns up to +DBLP are exact (S2 comes after them in the cascade).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ground_truth import boot_ratio, wilson  # noqa: E402
from ground_truth_p1 import ACADEMIC, BACKENDS, DERIVED, ROOT  # noqa: E402

COLS = ["crossref", "arxiv", "dblp", "openalex", "s2"]
DBLP_DUMP = "2026-10-19 release (server last-modified 2026-10-18 23:39 UTC)"  # D:/Datasets/dblp/DATA_SOURCES.md
LABEL = {"crossref": "Crossref-only", "arxiv": "+arXiv", "dblp": f"+DBLP (dump {DBLP_DUMP})", "openalex": "+OpenAlex",
         "s2": "+S2"}
assert tuple(COLS) == BACKENDS


def first_hit_stage(bh):
    hits = [b for b in str(bh or "").split(";") if b in COLS]
    return min(COLS.index(b) for b in hits) if hits else len(COLS)


def p_group(g):
    return np.where(g.has_arxiv == 1, "arxiv-id", np.where(g.has_doi == 1, "doi-only", "no-id"))


def row(g, per, name, seed, B):
    ev = g[g.def1_status.isin(["resolved", "unresolved"])].copy()
    ev["stage"] = np.where(ev.def1_status == "resolved", ev.backends_hit.map(first_hit_stage), len(COLS))
    out = {"period": per, "stratum": name, "n": int(len(ev)), "n_papers": int(ev.arxiv_id.nunique()),
           "n_rate_limited": int((g.def1_status == "rate-limited").sum()),
           "n_no_title": int((~g.def1_status.isin(["resolved", "unresolved", "rate-limited"])).sum()),
           "n_oa_skipped": int((ev.get("oa_skipped", 0) == 1).sum()),
           "n_dblp_missing": int((ev.get("dblp_missing", 0) == 1).sum()),
           "n_s2_pending": int((ev.get("s2_pending", 0) == 1).sum()),
           "k_first_hit_openalex": int((ev.stage == COLS.index("openalex")).sum())}
    for j, c in enumerate(COLS):
        x = (ev.stage > j).astype(int)
        k, n = int(x.sum()), len(ev)
        out[f"k_{c}"] = k
        out[f"u_{c}"] = round(k / n, 4) if n else None
        lo, hi = wilson(k, n) if n else (None, None)
        out[f"wilson_{c}"] = f"{lo:.4f}-{hi:.4f}" if n else ""
        if n:
            ev["x"] = x
            blo, bhi = boot_ratio(ev, "x", ev.index == ev.index, seed, B)
            out[f"boot_{c}"] = f"{blo:.4f}-{bhi:.4f}"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--input", default=None)
    ap.add_argument("--interim", action="store_true")
    ap.add_argument("--name", default="p1_backend_table")
    args = ap.parse_args()
    der, out_dir = (DERIVED / "interim", ROOT / "results" / "interim") if args.interim else (DERIVED, ROOT / "results")
    args.input = args.input or str(der / "p1_groundtruth_refs_full.csv")
    out_dir.mkdir(parents=True, exist_ok=True)
    d = pd.read_csv(args.input, dtype={"arxiv_id": str, "key": str}, low_memory=False)
    for c in ("has_arxiv", "has_doi", "certified_real", "oa_skipped", "dblp_missing", "s2_pending"):
        if c in d:
            d[c] = d[c].fillna(0).astype(int)
    rows = []
    for per, g0 in d.groupby("period"):
        strata = [(t, g0[g0.tier == t]) for t in ["J", "C", "P", "B", "S", "W"]]
        strata += [("A", g0[g0.tier.isin(ACADEMIC)]), ("all", g0), ("certified_real", g0[g0.certified_real == 1])]
        gp = g0[g0.tier == "P"].assign(idg=lambda x: p_group(x))
        strata += [(f"P/{k}", v) for k, v in gp.groupby("idg")]
        strata += [("P/with-id", gp[gp.idg != "no-id"])]
        rows += [row(g, per, name, args.seed, args.boot) for name, g in strata if len(g)]
    tab = pd.DataFrame(rows)
    n_all = int(tab[tab.stratum == "all"].n.sum())
    oa = int(tab[tab.stratum == "all"].n_oa_skipped.sum())
    oa_hits = int(tab[tab.stratum == "all"].k_first_hit_openalex.sum())
    oa_note = (f"keyless: {oa_hits} ref từ câu trả lời đã cache; phần còn lại không hỏi được (429), "
               f"{100 * oa / n_all:.1f} % ref không được hỏi") if oa else "keyless, all refs reaching it asked"
    plot_cols = COLS
    s2_pending = int(tab[tab.stratum == "all"].n_s2_pending.sum())
    if args.interim:
        # +S2 has no final state yet; +OpenAlex has no data unless a stored answer resolved a ref
        blank = ["s2"] + ([] if oa_hits else ["openalex"])
        for r in rows:
            for c in blank:
                txt = f"chưa hoàn tất, n_pending={r['n_s2_pending']}" if c == "s2" else "không có dữ liệu (keyless 429)"
                for f in ("k", "u", "wilson", "boot"):
                    r[f"{f}_{c}"] = txt
        tab = pd.DataFrame(rows)
        plot_cols = [c for c in COLS if c not in blank]
        oa_note = oa_note if oa_hits else "không có dữ liệu (keyless 429)"
    tab.to_csv(out_dir / f"{args.name}.csv", index=False)
    meta = {"seed": args.seed, "boot": args.boot, "input": args.input, "columns": [LABEL[c] for c in COLS],
            "openalex_note": oa_note, "dblp_dump": DBLP_DUMP,
            "note": "def 1; cumulative backends in cascade order (PREREG_AMENDMENT_3); same denominator per row",
            "column_definitions": {
                "Crossref-only": "Crossref alone (DOI check + title search); not the same as Crossref+arXiv",
                "+arXiv": "Crossref, then arXiv (refs with an arXiv id or in tier P)",
                "+DBLP": "... then the offline DBLP dump", "+OpenAlex": "... then OpenAlex (keyless)",
                "+S2": "... then Semantic Scholar = final cascade state (primary column for H1/H2)",
                "Crossref+arXiv (19-10)": "P1_LOG 19-10: round-1 state before Amendment 3 (Crossref + arXiv + cached OpenAlex/S2, no DBLP), A 12.3 % / 15.1 %; not a column of this table"},
            "rows": rows}
    if args.interim:
        meta.update(interim=True, s2_pending=s2_pending,
                    interim_note="INTERIM: round-1 replay from the cache; Crossref-only, +arXiv, +DBLP exact; "
                                 "+S2 not final (s2_pending refs counted unresolved in the denominator)")
    (out_dir / f"{args.name}.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    show = tab[["period", "stratum", "n"] + [f"u_{c}" for c in COLS] + ["n_oa_skipped", "n_s2_pending"]]
    print(show.rename(columns={f"u_{c}": LABEL[c] for c in COLS}).to_string(index=False))
    print("OpenAlex:", oa_note)
    plot(tab, oa_note, plot_cols, out_dir, "INTERIM — " if args.interim else "", name=args.name)


def plot(tab, oa_note, cols=COLS, out_dir=ROOT / "results", tag="", name="p1_backend_table"):
    COLS = cols  # noqa: N806 (columns drawn: all, or up to +DBLP for an interim table)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    strata = ["A", "J", "C", "P/with-id", "P/no-id", "B", "W", "S"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    for ax, per in zip(axes, ["2019-21", "2024-26"]):
        t = tab[tab.period == per].set_index("stratum")
        xs = np.arange(len(COLS))
        for s_ in strata:
            if s_ not in t.index:
                continue
            r = t.loc[s_]
            u = np.array([r[f"u_{c}"] for c in COLS], float) * 100
            lo = np.array([float(r[f"boot_{c}"].split("-")[0]) for c in COLS]) * 100
            hi = np.array([float(r[f"boot_{c}"].split("-")[1]) for c in COLS]) * 100
            ax.errorbar(xs, u, yerr=[u - lo, hi - u], marker="o", capsize=2, lw=2.2 if s_ == "A" else 1,
                        label=f"{s_} (n={int(r.n)})")
        ax.set_yscale("log")
        ax.set_xticks(xs, [LABEL[c].replace(" (", "\n(") for c in COLS], fontsize=7)
        ax.set_title(f"citing papers {per}", fontsize=9)
        ax.axhspan(0.5, 5, color="0.9", zorder=0)
        ax.grid(alpha=0.3, which="both")
    axes[0].set_ylabel("u (def 1), % unresolved — log scale")
    axes[1].legend(fontsize=7, loc="upper right", ncol=2)
    fig.suptitle(f"{tag}Cumulative backends; paper bootstrap 95 % CI (B=1000, seed 42); OpenAlex {oa_note}; "
                 "shaded = H1 window 0.5-5 %", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / f"{name}.png", dpi=150)


if __name__ == "__main__":
    main()
