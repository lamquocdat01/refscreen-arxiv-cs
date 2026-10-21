#!/usr/bin/env python3
"""Topic 43 / P2 / T10a condition 3: P1 ground truth + the night retry of the rate-limited references.

Rows of $THS_DATASETS/_derived/43/p1_groundtruth_refs_full.csv whose (arxiv_id, key) was re-resolved by
p2_retry_ratelimited.py are replaced by the retried rows (same columns); every other row is unchanged. The P1 file is
not modified. Used for the main table only where a u_s cell changed by >= 0.05 percentage points (Amendment 4).
Output: $THS_DATASETS/_derived/43/p2_groundtruth_refs_full.csv
Usage:  python p2_merge_retry.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ground_truth import DATA  # noqa: E402

D = DATA / "_derived" / "43"


def main():
    full = pd.read_csv(D / "p1_groundtruth_refs_full.csv", dtype=str, keep_default_na=False, low_memory=False)
    new = pd.read_csv(D / "p2_retry_ratelimited.csv", dtype=str, keep_default_na=False, low_memory=False)
    k = ["arxiv_id", "key"]
    # the P1 file has identical duplicate rows (same key twice in a paper); they are kept, as in the P1 tables and in
    # p2_retry_ratelimited.cells, and every copy gets the retried values
    assert not new.duplicated(k).any()
    # references that were rate-limited under def 1 take every retried column; references rate-limited under def 2 only
    # take def2_status, so that the def-1 cascade fields (backends_hit -> first-hit column of the main table) of
    # references already resolved in P1 are not re-attributed by the retry (OpenAlex keyless refused in the retry)
    out = full.set_index(k)
    old1 = out[~out.index.duplicated()].def1_status
    nn = new.set_index(k)
    assert nn.index.isin(out.index).all()
    rl1 = nn.index[(old1.reindex(nn.index) == "rate-limited").to_numpy()]
    oth = nn.index.difference(rl1)
    cols = [c for c in full.columns if c not in k]
    out.loc[rl1, cols] = nn.loc[rl1, cols]
    out.loc[oth, "def2_status"] = nn.loc[oth, "def2_status"]
    print(f"def-1 rate-limited: {len(rl1)} (all columns); def-2 only: {len(oth)} (def2_status)")
    out = out.reset_index()[full.columns]
    assert len(out) == len(full)
    out.to_csv(D / "p2_groundtruth_refs_full.csv", index=False)
    print(f"{len(new)} rows replaced of {len(full)} -> {D / 'p2_groundtruth_refs_full.csv'}")


if __name__ == "__main__":
    main()
