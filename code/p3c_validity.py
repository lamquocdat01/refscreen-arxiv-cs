#!/usr/bin/env python3
"""Topic 43 / P3C: rater validity check with planted negatives (PREREG_AMENDMENT_6.md, POST-HOC, supplementary).

candidates  Seed 44. Positives: 10 NEW real references from the pass-1 pool (results/p1_manual_sample.csv 200 +
            results/p2_manual_sample.csv 60) minus every row rechecked before (P1 recheck 40, P2 K01-K40, P3 Q01-Q40);
            6 tiers, a seeded permutation of the tiers decides which 4 tiers get 2 rows (the other 2 get 1).
            Negatives: 5 gen_a (fabricated title) + 5 gen_c (real title, wrong venue/year) from results/p2_fake_items.csv
            (the controlled P2 set, code/fake_refs/). gen_c rows keep their source paper and .bib key; gen_a rows get a
            seeded host paper from the 2024-26 render pool whose .bib version is later than the cited year. Writes the
            plaintext candidate dump into the key folder (KEYDIR) for hand rendering of the negatives' .bib/.bbl text in
            the host paper's own style (KEYDIR/p3c_render.json).
build       Reads the candidates and KEYDIR/p3c_render.json, writes the blind sheet results/p3c_validity_sheet.csv
            (V01-V20, seed-44 shuffled, empty outcome columns) and the key ENCRYPTED (Fernet) as
            KEYDIR/p3c_validity_key.csv.enc; prints the sha256 of the plaintext key (commitment, recorded in Amendment 6)
            and deletes the plaintext dumps. The Fernet key file sits in KEYDIR too: this guards against accidental
            opening only, not against a determined reader; the commitment hash is what fixes the key.
score       After both rater files exist (results/p3c_validity_rH.csv, results/p3c_validity_rC.csv): decrypts the key,
            verifies the commitment hash, writes results/p3c_validity_key.csv (plaintext, now releasable) and
            results/p3c_validity_merged.csv, then the statistics -> results/p3c_validity_stats.json.
stats       Reads only results/p3c_validity_merged.csv (offline, reproduce.py) -> results/p3c_validity_stats.json.
KEYDIR = $THS_DATASETS/_derived/43/keys (outside the synced drive and outside the repo).
Usage: python p3c_validity.py candidates|build|score|stats --seed 44
"""
import argparse
import hashlib
import io
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import beta

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ground_truth as gtm  # noqa: E402
from manual_sample import bib_entry_text  # noqa: E402
from p3_recheck import bbl_lookup  # noqa: E402

RES = gtm.ROOT / "results"
KEYDIR = gtm.DATA / "_derived" / "43" / "keys"
CAND = KEYDIR / "p3c_candidates.json"
RENDER = KEYDIR / "p3c_render.json"
KEYENC = KEYDIR / "p3c_validity_key.csv.enc"
FKEY = KEYDIR / "p3c_fernet.key"
SHEET = RES / "p3c_validity_sheet.csv"
KEYPLAIN = RES / "p3c_validity_key.csv"
MERGED = RES / "p3c_validity_merged.csv"
TIERS = ["J", "C", "P", "B", "S", "W"]
SHOW = ["check_id", "citing_paper_date", "bib_version_date", "tier", "title", "author", "bib_entry", "bbl_item"]
FILL = ["exists", "evidence_url", "evidence_note", "checker", "checked_at"]
CATS = ["exists", "not-exists", "ambiguous"]
RATERS = {"R_H": "p3c_validity_rH.csv", "R_C": "p3c_validity_rC.csv"}


def rd(p):
    return pd.read_csv(p, dtype=str, keep_default_na=False)


def manifest():
    sv = rd(gtm.ROOT / "data_manifest" / "manifest_src_version.csv")
    return sv.set_index("arxiv_id")[["published_v1", "src_version", "src_version_date"]].to_dict("index")


def candidates(args):
    if CAND.exists() or KEYENC.exists():
        sys.exit("candidates/key exist; not overwritten")
    rng = np.random.default_rng(args.seed)
    p1 = rd(RES / "p1_manual_sample.csv")
    p2 = rd(RES / "p2_manual_sample.csv").assign(author="")
    used = set(rd(RES / "p1_manual_recheck.csv").sample_id)
    used |= set(rd(gtm.DATA / "_derived" / "43" / "p2_recheck_key.csv").sample_id)
    used |= set(rd(gtm.DATA / "_derived" / "43" / "p3_recheck_key.csv").sample_id)
    cols = ["sample_id", "paper_id", "citing_paper_date", "tier", "key", "title", "author", "bib_entry", "exists"]
    pool = pd.concat([p1[cols].assign(origin="P1"), p2[cols].assign(origin="P2")])
    pool = pool[(pool.exists != "") & ~pool.sample_id.isin(used)].reset_index(drop=True)
    assert (pool.exists == "exists").all(), pool.exists.value_counts()
    order = list(rng.permutation(TIERS))
    alloc = {t: (2 if i < 4 else 1) for i, t in enumerate(order)}
    real = []
    for t in TIERS:
        x = pool[pool.tier == t]
        real += list(rng.choice(x.index, alloc[t], replace=False))
    real = pool.loc[sorted(real)].copy()
    mf = manifest()
    cache = {}
    real["bib_version_date"] = [mf[p]["src_version_date"] for p in real.paper_id]
    real["bbl_item"] = [bbl_lookup(p, k, cache) for p, k in zip(real.paper_id, real.key)]
    fk = rd(RES / "p2_fake_items.csv")
    ga = fk[(fk.set == "gen_a") & (fk.check == "passed")]
    gc = fk[fk.set == "gen_c"].copy()
    gc["src_paper"] = gc.raw.str.extract(r"source (\S+?)/")[0]
    gc["src_key"] = gc.raw.str.extract(r"source \S+?/(\S+?);")[0]
    bibc = {}
    gc["has_bib"] = [bib_entry_text(p, k, bibc) != "" for p, k in zip(gc.src_paper, gc.src_key)]
    gc["has_bbl"] = [bbl_lookup(p, k, cache) != "" for p, k in zip(gc.src_paper, gc.src_key)]
    gc = gc[gc.has_bib & gc.has_bbl & ~gc.src_paper.isin(real.paper_id)]
    ga5 = ga.loc[rng.choice(ga.index, 5, replace=False)]
    gc5 = gc.loc[rng.choice(gc.index, 5, replace=False)]
    hosts = pool[(pool.origin == "P2") & ~pool.paper_id.isin(real.paper_id)].paper_id.unique()
    hosts = [h for h in rng.permutation(hosts)
             if any(True for _ in (gtm.SRC / h.replace("/", "_")).rglob("*.bbl"))]
    neg = []
    for _, r in ga5.iterrows():
        h = next(h for h in hosts if int(mf[h]["src_version_date"][:4]) > int(r.year) and h not in
                 [n.get("paper_id") for n in neg])
        items = gtm.bbl_items(gtm.SRC / h.replace("/", "_"))
        ex = [i for i in range(len(items))]
        pick = sorted(rng.choice(ex, min(3, len(ex)), replace=False))
        neg.append(dict(family="gen_a", item_id=r.item_id, paper_id=h, title=r.title, author=r.author, venue=r.venue,
                        year=r.year, tier=r.tier, citing_paper_date=mf[h]["published_v1"],
                        bib_version_date=mf[h]["src_version_date"],
                        host_examples=[dict(key=items[i][0], bib=bib_entry_text(h, items[i][0], bibc),
                                            bbl=" ".join(items[i][1].split())) for i in pick]))
    for _, r in gc5.iterrows():
        p = r.src_paper
        neg.append(dict(family="gen_c", item_id=r.item_id, paper_id=p, key=r.src_key, title=r.title, author=r.author,
                        venue=r.venue, year=r.year, tier=r.tier, raw=r.raw, citing_paper_date=mf[p]["published_v1"],
                        bib_version_date=mf[p]["src_version_date"], orig_bib=bib_entry_text(p, r.src_key, bibc),
                        orig_bbl=bbl_lookup(p, r.src_key, cache)))
    KEYDIR.mkdir(parents=True, exist_ok=True)
    CAND.write_text(json.dumps(dict(seed=args.seed, tier_order=order, alloc=alloc, pool_n=len(pool),
                                    pool_tiers=pool.tier.value_counts().to_dict(),
                                    real=real.to_dict("records"), neg=neg), indent=1, ensure_ascii=False),
                    encoding="utf-8")
    print("pool", len(pool), pool.tier.value_counts().to_dict(), "| alloc", alloc)
    print("real", real.groupby(["tier", "origin"]).size().to_dict(), "| bbl non-empty", int((real.bbl_item != "").sum()))
    print("gen_c eligible", len(gc), "| hosts", len(hosts), "| candidates ->", CAND)


def fernet():
    from cryptography.fernet import Fernet
    if not FKEY.exists():
        FKEY.write_bytes(Fernet.generate_key())
    return Fernet(FKEY.read_bytes())


def build(args):
    if SHEET.exists() or KEYENC.exists():
        sys.exit("sheet/key exist; not overwritten")
    c = json.loads(CAND.read_text(encoding="utf-8"))
    rend = json.loads(RENDER.read_text(encoding="utf-8"))
    rows = []
    for r in c["real"]:
        rows.append(dict(truth="exists", family="real", source_id=r["sample_id"], paper_id=r["paper_id"],
                         key=r["key"], citing_paper_date=r["citing_paper_date"],
                         bib_version_date=r["bib_version_date"], tier=r["tier"], title=r["title"],
                         author=r["author"], bib_entry=r["bib_entry"], bbl_item=r["bbl_item"], origin=r["origin"],
                         note="pass-1 exists"))
    for n in c["neg"]:
        x = rend[n["item_id"]]
        rows.append(dict(truth="not-exists", family=n["family"], source_id=n["item_id"], paper_id=n["paper_id"],
                         key=x["key"], citing_paper_date=n["citing_paper_date"],
                         bib_version_date=n["bib_version_date"], tier=n["tier"], title=x["title"],
                         author=x["author"], bib_entry=x["bib_entry"], bbl_item=x["bbl_item"],
                         origin="P1" if n["family"] == "gen_c" else "P2", note=x.get("note", "")))
    k = pd.DataFrame(rows).sample(frac=1, random_state=args.seed).reset_index(drop=True)
    k.insert(0, "check_id", [f"V{i + 1:02d}" for i in range(len(k))])
    sh = k[SHOW].copy()
    for f in FILL:
        sh[f] = ""
    sh.to_csv(SHEET, index=False)
    buf = k.to_csv(index=False).encode("utf-8")
    h = hashlib.sha256(buf).hexdigest()
    KEYENC.write_bytes(fernet().encrypt(buf))
    (KEYDIR / "p3c_validity_key.sha256").write_text(h + "  p3c_validity_key.csv\n", encoding="ascii")
    bundle = fernet().encrypt(json.dumps(dict(candidates=c, render=rend), ensure_ascii=False).encode("utf-8"))
    (KEYDIR / "p3c_candidates_render.json.enc").write_bytes(bundle)
    CAND.unlink()
    RENDER.unlink()
    print("sheet", SHEET, len(sh), "| key sha256", h)
    print("sheet sha256", hashlib.sha256(SHEET.read_bytes()).hexdigest())


def cp(k, n, conf=0.95):
    a = (1 - conf) / 2
    lo = float(beta.ppf(a, k, n - k + 1)) if k > 0 else 0.0
    hi = float(beta.ppf(1 - a, k + 1, n - k)) if k < n else 1.0
    return [lo, hi]


def agree(x, y):
    """3-outcome PABAK, Gwet AC1, kappa, binary (exists vs not) PABAK/AC1 for two label lists."""
    x, y = list(x), list(y)
    n = len(x)
    t = np.zeros((3, 3))
    for a, b in zip(x, y):
        t[CATS.index(a), CATS.index(b)] += 1
    po = float(np.trace(t) / n)
    pe = float((t.sum(0) * t.sum(1)).sum() / n ** 2)
    pi = (t.sum(0) + t.sum(1)) / (2 * n)
    pe_ac = float((pi * (1 - pi)).sum() / 2)
    xb, yb = [a == "exists" for a in x], [b == "exists" for b in y]
    pob = float(np.mean([a == b for a, b in zip(xb, yb)]))
    pib = (sum(xb) + sum(yb)) / (2 * n)
    pe_b = float(2 * pib * (1 - pib))
    k_dis = int(n - np.trace(t))
    lo_dis = cp(k_dis, n)[1]
    return dict(n=n, raw=po, pabak=(3 * po - 1) / 2, ac1=(po - pe_ac) / (1 - pe_ac) if pe_ac < 1 else None,
                kappa=(po - pe) / (1 - pe) if pe < 1 else None, table=t.astype(int).tolist(), labels=CATS,
                disagree_n=k_dis, disagree_cp95=cp(k_dis, n), pabak_cp_lower=(3 * (1 - lo_dis) - 1) / 2,
                bin_raw=pob, bin_pabak=2 * pob - 1, bin_ac1=(pob - pe_b) / (1 - pe_b) if pe_b < 1 else None)


def score(args):
    import hashlib as hl
    for f in RATERS.values():
        if not (RES / f).exists():
            sys.exit(f"missing {f}")
    buf = fernet().decrypt(KEYENC.read_bytes())
    want = (KEYDIR / "p3c_validity_key.sha256").read_text().split()[0]
    assert hl.sha256(buf).hexdigest() == want, "key does not match its commitment hash"
    k = pd.read_csv(io.BytesIO(buf), dtype=str, keep_default_na=False)
    KEYPLAIN.write_bytes(buf)
    m = k[["check_id", "truth", "family", "tier", "origin", "title"]]
    for r, f in RATERS.items():
        x = rd(RES / f)[["check_id"] + FILL]
        x = x.rename(columns={c: (r if c == "exists" else f"{r}_{c}") for c in FILL})
        m = m.merge(x, on="check_id", how="left")
    for r in RATERS:
        m[r] = m[r].str.strip().str.lower()
    m = m.sort_values("check_id")
    assert not m.apply(lambda c: c.str.contains(r"@[\w-]+\.[a-z]{2,}", regex=True)).any().any(), "email-like string"
    m.to_csv(MERGED, index=False)
    stats(args)


def stats(args):
    m = rd(MERGED)
    bad = {r: sorted(set(m[r]) - set(CATS)) for r in RATERS}
    assert not any(bad.values()), f"labels outside {CATS}: {bad}"
    out = {"seed": args.seed, "n": len(m), "label": "rater validity check with planted negatives (Amendment 6, "
           "post hoc, supplementary); does not change any registered result",
           "composition": m.groupby(["truth", "family"]).size().reset_index().values.tolist()}
    flat = {}
    for r in RATERS:
        s = {}
        neg = m[m.truth == "not-exists"]
        pos = m[m.truth == "exists"]
        kneg = int(neg[r].isin(["not-exists", "ambiguous"]).sum())
        s["neg_recall"] = dict(k=kneg, n=len(neg), rate=kneg / len(neg), cp95=cp(kneg, len(neg)))
        knn = int((neg[r] == "not-exists").sum())
        s["neg_notexists_only"] = dict(k=knn, n=len(neg), rate=knn / len(neg), cp95=cp(knn, len(neg)))
        for fam in ("gen_a", "gen_c"):
            f = neg[neg.family == fam]
            kf = int(f[r].isin(["not-exists", "ambiguous"]).sum())
            s[f"neg_recall_{fam}"] = dict(k=kf, n=len(f), rate=kf / len(f) if len(f) else None, cp95=cp(kf, len(f)),
                                         labels=f[r].value_counts().to_dict())
        kp = int((pos[r] == "exists").sum())
        s["pos_exists"] = dict(k=kp, n=len(pos), rate=kp / len(pos), cp95=cp(kp, len(pos)))
        s["labels"] = m[r].value_counts().to_dict()
        out[r] = s
        tag = r.replace("_", "").lower()
        flat.update({f"validity_{tag}_neg_k": kneg, f"validity_{tag}_neg_n": len(neg),
                     f"validity_{tag}_neg_lo": s["neg_recall"]["cp95"][0], f"validity_{tag}_neg_hi": s["neg_recall"]["cp95"][1],
                     f"validity_{tag}_gena_k": s["neg_recall_gen_a"]["k"], f"validity_{tag}_genc_k": s["neg_recall_gen_c"]["k"],
                     f"validity_{tag}_pos_k": kp, f"validity_{tag}_pos_n": len(pos),
                     f"validity_{tag}_pos_lo": s["pos_exists"]["cp95"][0]})
    a = agree(m.R_H, m.R_C)
    out["R_H-R_C"] = a
    for fam in ("real", "gen_a", "gen_c"):
        f = m[m.family == fam]
        out[f"R_H-R_C_{fam}"] = dict(n=len(f), agree=int((f.R_H == f.R_C).sum()))
    flat.update(validity_pabak=a["pabak"], validity_ac1=a["ac1"], validity_kappa=a["kappa"], validity_raw=a["raw"],
                validity_pabak_cplo=a["pabak_cp_lower"], validity_disagree_n=a["disagree_n"], validity_n=len(m))
    out["flat"] = flat
    (RES / "p3c_validity_stats.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1)[:3000])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["candidates", "build", "score", "stats"])
    ap.add_argument("--seed", type=int, default=44)
    args = ap.parse_args()
    {"candidates": candidates, "build": build, "score": score, "stats": stats}[args.stage](args)


if __name__ == "__main__":
    main()
