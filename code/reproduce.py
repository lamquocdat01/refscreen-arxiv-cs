#!/usr/bin/env python3
"""Topic 43: reproduce the offline part of the pipeline from the committed results + derived files, and check that
the numbers match the committed ones key by key (C7(h)).

Run it in a fresh clone (the scripts write to <clone>/results/): it snapshots the committed outputs, reruns
  p1_backend_table.py, p1_hypotheses.py, p1_h5_betabinom.py --boot 200, p2_render_manual_fp.py, p2_theory_final.py,
  p2_merge_retry.py + p1_backend_table.py --name p2_backend_table_retry (P2 main table after the night retry),
  p2_render_manual_fp.py --adjudicated (H4-render with the Amendment-5 adjudication),
  p3_recheck.py stats --seed 43 (post-hoc recheck statistics from results/p3_recheck_merged.csv),
  p3d_theory_fix.py --seed 42 (erratum: R2, R3, k*, identifier tables; runs right after p2_theory_final.py),
  p3e_recompute.py (completed cascade, *_p3e) and the P3F chain (deep-search states from cache_p3f, bounds, tier check,
  numbers.json *_p3f; offline)
(all --seed 42; no network). Inputs: results/ plus three derived files under $THS_DATASETS/_derived/43/
(p1_groundtruth_refs_full.csv, p2_retry_ratelimited.csv, screen_p1/screen_refs.csv; GitHub release asset). Then it compares
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
         ["p2_render_manual_fp.py", "--seed", "42", "--adjudicated"],
         ["p3_recheck.py", "stats", "--seed", "43"],
         ["p2_theory_final.py", "--seed", "42"], ["p3d_theory_fix.py", "--seed", "42"], ["p2_merge_retry.py"],
         ["p1_backend_table.py", "--seed", "42", "--input", "{DERIVED}/p2_groundtruth_refs_full.csv",
          "--name", "p2_backend_table_retry"],
         # P3E (Amendment 7): the whole chain again on the completed ground truth (derived file
         # p3e_groundtruth_refs_full.csv), outputs with the suffix _p3e and numbers.json keys *_p3e
         ["p3e_recompute.py"],
         # P3F (Amendment 8): deep-search states from the stored answers (cache_p3f, offline), bounds, tier-rule check,
         # POST-HOC profile, numbers.json keys *_p3f (results/p3f_rB_vs_gt3.json is an input: it needs the sheet key)
         ["p3f_deep_search.py", "--evaluate"], ["p3f_bounds.py"], ["p3f_tier_validation.py"],
         ["p3f_notfound_profile.py"], ["p3f_numbers.py"],
         # P3G (POSTHOC_NOTE_P3G.md, post hoc, offline): branch split, both ends, bounds/decoys/families/periods,
         # policy coding, numbers.json keys *_p3g
         ["p3g_branch_split.py"], ["p3g_two_ends.py"], ["p3g_bounds.py"], ["p3g_policy_coding.py"], ["p3g_numbers.py"],
         # P3H (Amendment 9 and the closure check, post hoc, offline): periods by branch, rule check of the stored web
         # captures (cache_p3h), score with the released key and the author's file, numbers.json keys *_p3h
         ["p3h_period_standardised.py"], ["p3h_evidence_check.py"], ["p3h_evidence_score.py"], ["p3h_numbers.py"]]
# P4B: inputs that are not redistributed (stored backend and deep-search responses, arXiv sources). A step whose
# inputs are missing is skipped (its committed outputs stay in results/ and feed the later steps); for p3e_recompute the
# listed outputs are put back to the committed files after the step. The script prints every skip.
_C = ["_derived/43/cache", "_derived/43/cache_p3e", "_derived/43/cache_p3f"]
NEEDS = {"p3f_deep_search.py --evaluate": ["_derived/43/cache_p3f", "arxiv_src_43/src"],
         "p3f_tier_validation.py": _C,
         "p3f_notfound_profile.py": ["_derived/43/cache_p3f", "arxiv_src_43/src"],
         "p3g_branch_split.py": _C + ["arxiv_src_43/src"],
         "p3g_bounds.py": _C + ["arxiv_src_43/src"]}
KEEP = {"p3e_recompute.py": (["_derived/43/cache", "_derived/43/cache_p3e"],
                             ["p3e_exploratory_p3e.csv", "p3e_exploratory_p3e.json"])}
CSVS = ["p1_backend_table.csv", "p1_h5_betabinom.csv", "p2_render_manual_fp.csv", "p2_theory_final.csv",
        "p2_backend_table_retry.csv", "p2_render_manual_fp_adjudicated.csv", "p3d_theory_fix.csv",
        "p2_backend_table_retry_p3e.csv", "p1_h5_betabinom_p3e.csv", "p2_theory_final_p3e.csv", "p3d_theory_fix_p3e.csv",
        "p1_h4_bias_p3e.csv", "p1_theory_tables_p3e.csv", "p1_period_compare_p3e.csv", "p3e_exploratory_p3e.csv",
        "p3f_deep_search.csv", "p3f_tier_validation.csv",
        "p3g_branch_split.csv", "p3g_two_ends.csv", "p3g_fake_gt3rule.csv", "p3g_notfound_split.csv", "p3g_policy_coding.csv",
        "p3h_period_standardised.csv", "p3h_evidence_checked.csv", "p3h_evidence_score.csv", "p3h_two_ends.csv"]
JSONS = ["numbers.json", "p1_hypotheses_h1h2.json", "p1_h5_betabinom.json", "p2_render_manual_fp.json",
         "p2_render_manual_fp_adjudicated.json", "p3_recheck_stats.json", "p3d_theory_fix.json",
         "p2_backend_table_retry_p3e.json", "p1_hypotheses_h1h2_p3e.json", "p1_h5_betabinom_p3e.json",
         "p3d_theory_fix_p3e.json", "p3_revision_checks_p3e.json", "p1_h4_bias_p3e.json", "p3e_exploratory_p3e.json",
         "p3f_gt3_summary.json", "p3f_tier_validation.json", "p3f_posthoc.json", "p3f_notfound_profile.json",
         "p3g_branch_split.json", "p3g_two_ends.json", "p3g_bounds.json", "p3g_policy_coding.json",
         "p3h_period_standardised.json", "p3h_evidence_score.json", "p3h_two_ends.json"]


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
        if (a != a and b != b) or a == b:  # both NaN, or equal (also +inf == +inf, where a - b is NaN)
            return True
        return abs(a - b) <= 1e-9 * max(1.0, abs(a))
    return a == b


def main():
    snap = Path(tempfile.mkdtemp(prefix="refscreen_snap_"))
    for f in CSVS + JSONS:
        shutil.copy2(RES / f, snap / f)
    data = Path(__import__("os").environ.get("THS_DATASETS", r"D:\Datasets"))
    skipped = []
    for step in STEPS:
        print(">>", " ".join(step), flush=True)
        derived = data / "_derived" / "43"
        # P4: inputs that are not redistributed (stored backend responses, arXiv sources). Without them the step is
        # skipped and its committed output is used downstream and in the comparison.
        missing = [n for n in NEEDS.get(" ".join(step), []) if not (data / n).exists()]
        if missing:
            print("   skipped: needs", ", ".join(missing), "(not redistributed); committed output kept", flush=True)
            skipped.append(step[0])
            continue
        r = subprocess.run([sys.executable, str(HERE / step[0])] + [a.replace("{DERIVED}", str(derived))
                                                                       for a in step[1:]], cwd=HERE,
                           env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode:
            print(r.stdout[-2000:], r.stderr[-2000:])
            sys.exit(f"step failed: {step[0]}")
        if step[0] in KEEP:
            need, files = KEEP[step[0]]
            missing = [n for n in need if not (data / n).exists()]
            if missing:
                for f in files:
                    shutil.copy2(snap / f, RES / f)
                print("   kept committed", ", ".join(files), "(needs", ", ".join(missing) + ", not redistributed)", flush=True)
                skipped.append(f"{step[0]} ({', '.join(files)})")
    bad = 0
    for f in JSONS:
        a = dict(flat(json.loads((snap / f).read_text(encoding="utf-8"))))
        b = dict(flat(json.loads((RES / f).read_text(encoding="utf-8"))))
        a.pop("interim", None), b.pop("interim", None)
        a.pop("input", None), b.pop("input", None)  # P4B: a local file path, differs with THS_DATASETS
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
    if skipped:
        print("skipped steps (inputs not redistributed):", ", ".join(skipped))
    print("REPRODUCED: all checked numbers identical" if not bad else f"DIFFERENCES: {bad}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
