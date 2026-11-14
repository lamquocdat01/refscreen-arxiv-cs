#!/usr/bin/env python3
"""Topic 43 / P3H (POST HOC, offline): write numbers.json keys *_p3h.

  period_std_p3h     from results/p3h_period_standardised.json (closure N4, N7, N6)
  sens_extra_p3h     lower FP end at f = family-c rate (12%) and the f at which the lower end reaches zero (= F/U)
  evidence_p3h       from results/p3h_evidence_score.json, if present (Amendment 9 (F)-(G))
Backup of numbers.json before the first write: P3H/numbers.json.bak_before_p3h.
Usage: python code/p3h_numbers.py
"""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"


def main():
    nf = RES / "numbers.json"
    bak = ROOT / "P3H" / "numbers.json.bak_before_p3h"
    if bak.parent.exists() and not bak.exists():  # the project log folder; absent in a clean clone
        shutil.copy2(nf, bak)
    nums = json.loads(nf.read_text(encoding="utf-8"))
    ps = json.loads((RES / "p3h_period_standardised.json").read_text(encoding="utf-8"))
    nums["period_std_p3h"] = ps
    te = nums["two_ends_p3g"]
    fam = nums["bounds_p3g"]["P5_fake_families"]["gen_c"]
    f12 = fam["f"]
    extra = {}
    for s_ in ("pooled", "bib"):
        b = te[f"{s_}|bounds"]
        U, R, N, F = b["U"], b["R"], b["N"], b["F"]
        extra[s_] = dict(f_famc=f12, fp_lower_famc=max(0.0, U - R / (1 - f12)) / N, f_zero=F / U,
                         note="lower end = max(0, U - R/(1-f))/N; it is zero for every f >= F/U")
    nums["sens_extra_p3h"] = extra
    sc = RES / "p3h_evidence_score.json"
    if sc.exists():
        nums["evidence_p3h"] = json.loads(sc.read_text(encoding="utf-8"))
    nf.write_text(json.dumps(nums, indent=1, ensure_ascii=False), encoding="utf-8")
    print("numbers.json: period_std_p3h, sens_extra_p3h" + (", evidence_p3h" if sc.exists() else ""))
    for s_, e in extra.items():
        print(s_, {k: round(v, 5) if isinstance(v, float) else v for k, v in e.items()})


if __name__ == "__main__":
    main()
