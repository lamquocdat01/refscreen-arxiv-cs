#!/usr/bin/env python3
"""Topic 43 / P3E (PREREG_AMENDMENT_7 (b), (c)): human-rated check H01-H68 and tier-rule check T001-T100.

tier    (c) Seed 46: 100 distinct corpus references (both periods, all tiers), drawn as a seed-46 permutation of every
        distinct (paper, key), skipping references with neither .bib entry nor .bbl item text. Writes the blind sheet
        results/p3e_tier_sheet.csv (T001-T100: bib_entry, bbl_item, empty tier_human/evidence_note/checker/checked_at),
        the guide results/p3e_tier_guide.md (PREREG §2 definitions) and the key (machine tier, period, source) ENCRYPTED
        as KEYDIR/p3e_tier_key.csv.enc; prints the sha256 of the plaintext key.
build   (b) After the completed cascade (P3E/cascade_passes.json has "unanswered_after_last_pass"):
        the 20 rows V01-V20 of results/p3c_validity_sheet.csv, content unchanged (their key is not opened here), plus
        the 2019-21 academic references unresolved under the completed full cascade (no-title excluded; titles equal
        to a V-row title are not drawn): all if <= 48, else 48 stratified J/C/P (16 each, seed 47; a short tier gives
        all and its remainder goes equally to the other two, odd remainder to the larger tier). Same columns as the
        P3C sheet; shuffled with seed 45; ids H01-H68. Writes results/p3e_human_sheet.csv,
        results/p3e_human_rules.md (= results/p3c_validity_rules.md verbatim) and the key ENCRYPTED as
        KEYDIR/p3e_human_key.csv.enc; prints the sha256 of the plaintext key.
score   When results/p3e_human_rH1.csv, results/p3e_tier_rH1.csv and results/p3e_human_rB.csv exist (rH2 optional;
        Addendum 3: R_H1 = label_pass2 of the two-pass form, label_pass1 only for the intra-rater block): decrypts both
        keys (P3E and the Amendment-6 key for V01-V20), checks their commitment hashes, writes
        results/p3e_human_key.csv (plaintext, releasable after scoring) and results/p3e_human_merged.csv, then stats.
        Also scores results/p3e_tier_rH1.csv if it exists (-> results/p3e_tier_merged.csv).
stats   Reads only the merged files -> results/p3e_human_stats.json (+ results/p3e_tier_stats.json).
score-rb (PREREG_AMENDMENT_8 (B)) R_B only, needs no human file: decrypts the key (plaintext hash checked, mismatch = STOP) and
        writes results/p3f_rB_score.{csv,json}. The tier key is never decrypted.
Usage: python code/p3e_human_sheet.py tier|build|score|stats|score-rb [--seed N]
"""
import argparse
import hashlib
import io
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ground_truth as gtm  # noqa: E402
import refmatch as rm  # noqa: E402
from manual_sample import bib_entry_text  # noqa: E402
from p3_recheck import bbl_lookup  # noqa: E402
from p3c_validity import CATS, agree, cp, fernet, manifest  # noqa: E402
import p3c_validity as p3c  # noqa: E402

RES = gtm.ROOT / "results"
DER = gtm.DATA / "_derived" / "43"
KEYDIR = DER / "keys"
SHEET, RULES = RES / "p3e_human_sheet.csv", RES / "p3e_human_rules.md"
KEYENC, KEYPLAIN, MERGED = KEYDIR / "p3e_human_key.csv.enc", RES / "p3e_human_key.csv", RES / "p3e_human_merged.csv"
TSHEET, TGUIDE = RES / "p3e_tier_sheet.csv", RES / "p3e_tier_guide.md"
TKEYENC, TKEYPLAIN, TMERGED = KEYDIR / "p3e_tier_key.csv.enc", RES / "p3e_tier_key.csv", RES / "p3e_tier_merged.csv"
GT = DER / "p3e_groundtruth_refs_full.csv"
SHOW = ["check_id", "citing_paper_date", "bib_version_date", "tier", "title", "author", "bib_entry", "bbl_item"]
FILL = ["exists", "evidence_url", "evidence_note", "checker", "checked_at"]
RATERS = {"R_H1": "p3e_human_rH1.csv", "R_H2": "p3e_human_rH2.csv", "R_B": "p3e_human_rB.csv"}
TIERS = ["J", "C", "P", "B", "S", "W"]


def rd(p):  # utf-8-sig: Excel "CSV UTF-8" adds a BOM; some Excel locales save with ";"
    with open(p, encoding="utf-8-sig") as fh:
        head = fh.readline()
    sep = ";" if head.count(";") > head.count(",") else ","
    return pd.read_csv(p, dtype=str, keep_default_na=False, encoding="utf-8-sig", sep=sep)


def rater_frame(r, f):
    """Rater file -> check_id + FILL. R_H1 under Addendum 3 (form p3e_human_rH1_form.csv): the rating is label_pass2
    (time pass2_at); label_pass1, pass1_at and pass2_note are kept for the intra-rater statistics."""
    x = rd(RES / f)
    if r == "R_H1" and "label_pass2" in x.columns:
        empty = x.check_id[x.label_pass2.str.strip() == ""].tolist()
        if empty:
            sys.exit(f"R_H1: label_pass2 empty on {len(empty)} rows (Addendum 3 needs both passes): {empty[:10]}")
        x = x.rename(columns={"label_pass2": "exists", "pass2_at": "checked_at"})
        extra = ["label_pass1", "pass1_at", "pass2_note"]
        return x[["check_id"] + FILL + extra].rename(columns={c: f"{r}_{c}" for c in extra})
    return x[["check_id"] + FILL]


def sha(b):
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------------------------------------- (c) tier sheet
GUIDE = """# Tier sheet — guide (T001–T100)

For each row, read the bibliography entry (`bib_entry`, a BibTeX entry) or, when it is empty, the formatted item
(`bbl_item`). Decide **what kind of work the reference is**, and write one letter in `tier_human`. If the entry does
not say enough, you may search the web for the work. Judge the work itself, not the BibTeX entry type: a journal
article written as `@misc` is still a journal article.

The six tiers (definitions of the study's pre-registration, §2):

| Tier | What the work is |
|---|---|
| **P** preprint | available as a preprint (arXiv, bioRxiv, medRxiv, SSRN), or cited as one |
| **S** software / dataset / model card | a code repository, software package, dataset or model card (GitHub, GitLab, Hugging Face, Zenodo, Kaggle, …) |
| **J** journal article | an article in a journal |
| **C** conference / workshop | a paper in conference or workshop proceedings |
| **B** book / chapter / thesis | a book, a chapter of a book, or a PhD/master's thesis |
| **W** web / report / standard / other | everything else: web page, blog post, technical report, standard, patent, manual, unpublished note, … |

**Conflict order:** if more than one tier fits, take the first in the order **P > S > J > C > B > W**. For example, a
conference paper that is cited with its arXiv identifier is **P**; a dataset described in a journal article and
cited as the dataset is **S**.

Fill in: `tier_human` (one of P, S, J, C, B, W), `evidence_note` (optional, a few words), `checker` (your name or
initials), `checked_at` (date). Save the file as `results/p3e_tier_rH1.csv`. Do not open any other project file
before you have finished.
"""


def tier(args):
    if TSHEET.exists() or TKEYENC.exists():
        sys.exit("tier sheet/key exist; not overwritten")
    d = rd(DER / "p2_groundtruth_refs_full.csv").drop_duplicates(["arxiv_id", "key"]).reset_index(drop=True)
    perm = np.random.default_rng(args.seed).permutation(len(d))
    bibc, bblc, rows, skipped = {}, {}, [], 0
    for i in perm:
        r = d.loc[i]
        be = bib_entry_text(r.arxiv_id, r.key, bibc) if r.ref_source == "bib" else ""
        bi = bbl_lookup(r.arxiv_id, r.key, bblc)
        if not be and not bi:
            skipped += 1
            continue
        rows.append(dict(paper_id=r.arxiv_id, key=r.key, period=r.period, ref_source=r.ref_source,
                         entrytype=r.entrytype, tier_machine=r.tier, bib_entry=be, bbl_item=bi, draw_pos=int(i)))
        if len(rows) == 100:
            break
    k = pd.DataFrame(rows)
    k.insert(0, "tier_id", [f"T{i + 1:03d}" for i in range(len(k))])
    sh = k[["tier_id", "bib_entry", "bbl_item"]].copy()
    for f in ("tier_human", "evidence_note", "checker", "checked_at"):
        sh[f] = ""
    sh.to_csv(TSHEET, index=False)
    TGUIDE.write_text(GUIDE, encoding="utf-8")
    buf = k.to_csv(index=False).encode("utf-8")
    KEYDIR.mkdir(parents=True, exist_ok=True)
    TKEYENC.write_bytes(fernet().encrypt(buf))
    (KEYDIR / "p3e_tier_key.sha256").write_text(sha(buf) + "  p3e_tier_key.csv\n", encoding="ascii")
    print(f"tier sheet {TSHEET.name}: {len(sh)} rows (skipped {skipped} without text); key sha256 {sha(buf)}")
    print("sheet sha256", sha(TSHEET.read_bytes()), "| guide sha256", sha(TGUIDE.read_bytes()))


# ---------------------------------------------------------------------------------------------- (b) human sheet
def alloc48(avail, total=48, tiers=("J", "C", "P")):
    a = {t: 16 for t in tiers}
    while True:
        short = [t for t in tiers if a[t] > avail[t]]
        if not short:
            return a
        rem = sum(a[t] - avail[t] for t in short)
        for t in short:
            a[t] = avail[t]
        rest = sorted([t for t in tiers if a[t] < avail[t]], key=lambda t: -avail[t])
        if not rest:
            return a
        for j, t in enumerate(rest):
            a[t] += rem // len(rest) + (1 if j < rem % len(rest) else 0)


def build(args):
    global SHEET, RULES, KEYENC  # noqa: PLW0603
    if args.provisional:
        # P3E 08-11 (LQD): dry build on the INTERIM flag set while the Addendum-A cascade runs; NOT for raters.
        # Separate files, overwritten on every provisional build; the registered build below is unchanged.
        SHEET, RULES = RES / "p3e_human_sheet_PROVISIONAL.csv", RES / "p3e_human_rules_PROVISIONAL.md"
        KEYENC = KEYDIR / "p3e_human_key_PROVISIONAL.csv.enc"
    else:
        if SHEET.exists() or KEYENC.exists():
            sys.exit("human sheet/key exist; not overwritten")
        # Addenda A/2: the pool depends only on the def-1 states of 2019-21 academic references, so the sheet is
        # drawn as soon as every 2019-21 academic target has its answer (P3E/cascade_targets.csv, written per pass)
        ct = rd(gtm.ROOT / "P3E" / "cascade_targets.csv")
        a = ct[(ct.period == "2019-21") & ct.tier.isin(["J", "C", "P"])]
        left = int(((a.missing_after != "") | (a.state_after == "")).sum())
        if left and not args.allow_unanswered:
            sys.exit(f"{left} academic 2019-21 references still lack an answer "
                     "(--allow-unanswered only after the 13-11 deadline)")
    v = rd(RES / "p3c_validity_sheet.csv")
    vt = [rm.norm(t) for t in v.title]
    d = rd(GT).drop_duplicates(["arxiv_id", "key"])
    pool = d[(d.period == "2019-21") & d.tier.isin(["J", "C", "P"]) & (d.def1_status == "unresolved")].copy()
    pool["dup_v"] = [any(rm.title_sim_norm(rm.norm(t), x) >= 0.9 for x in vt) for t in pool.title]
    n_pool, n_dup = len(pool), int(pool.dup_v.sum())
    pool = pool[~pool.dup_v].reset_index(drop=True)
    avail = pool.tier.value_counts().reindex(["J", "C", "P"], fill_value=0).to_dict()
    rng = np.random.default_rng(args.seed)  # 47
    if len(pool) <= 48:
        pick, alloc = pool, {t: avail[t] for t in avail}
    else:
        alloc = alloc48(avail)
        idx = []
        for t in ("J", "C", "P"):
            x = pool.index[pool.tier == t]
            idx += list(rng.choice(x, alloc[t], replace=False))
        pick = pool.loc[sorted(idx)]
    mf = manifest()
    bibc, bblc = {}, {}
    p1 = rd(RES / "p1_manual_sample.csv")[["paper_id", "key", "sample_id", "exists"]]
    p1 = p1[p1.exists != ""].set_index(["paper_id", "key"])
    rows = []
    for _, r in pick.iterrows():
        pk = (r.arxiv_id, r.key)
        rows.append(dict(origin="U", v_id="", paper_id=r.arxiv_id, key=r.key, tier_machine=r.tier,
                         state=r.def1_status, oa_skipped=r.oa_skipped,
                         pass1=p1.loc[pk, "exists"] if pk in p1.index else "",
                         pass1_sample=p1.loc[pk, "sample_id"] if pk in p1.index else "",
                         citing_paper_date=mf[r.arxiv_id]["published_v1"],
                         bib_version_date=mf[r.arxiv_id]["src_version_date"], tier=r.tier, title=r.title,
                         author=r.author, bib_entry=bib_entry_text(r.arxiv_id, r.key, bibc) if r.ref_source == "bib"
                         else "", bbl_item=bbl_lookup(r.arxiv_id, r.key, bblc)))
    for _, r in v.iterrows():
        rows.append(dict(origin="V", v_id=r.check_id, **{c: r[c] for c in SHOW if c != "check_id"}))
    k = pd.DataFrame(rows).fillna("").sample(frac=1, random_state=45).reset_index(drop=True)
    k.insert(0, "check_id", [f"H{i + 1:02d}" for i in range(len(k))])
    sh = k[SHOW].copy()
    for f in FILL:
        sh[f] = ""
    sh.to_csv(SHEET, index=False)
    shutil.copyfile(RES / "p3c_validity_rules.md", RULES)
    buf = k.to_csv(index=False).encode("utf-8")
    KEYENC.write_bytes(fernet().encrypt(buf))
    kname = "p3e_human_key_PROVISIONAL" if args.provisional else "p3e_human_key"
    (KEYDIR / f"{kname}.sha256").write_text(sha(buf) + f"  {kname}.csv\n", encoding="ascii")
    meta = dict(provisional=bool(args.provisional), seed_draw=args.seed, seed_shuffle=45, pool_unresolved_2019_21_academic=n_pool, excluded_as_v_title=n_dup,
                pool_after=len(pool), avail=avail, alloc=alloc, n_u=len(pick), n_v=len(v), n=len(k),
                u_with_pass1=int((k.pass1 != "").sum()), key_sha256=sha(buf), sheet_sha256=sha(SHEET.read_bytes()),
                rules_sha256=sha(RULES.read_bytes()))
    meta_name = "p3e_human_sheet_meta_PROVISIONAL.json" if args.provisional else "p3e_human_sheet_meta.json"
    if args.provisional:
        meta["banner"] = "PROVISIONAL: interim flag set (cascade not complete); NOT for raters; rebuilt when done"
    (RES / meta_name).write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(json.dumps(meta, indent=1))


# ---------------------------------------------------------------------------------------------- score / stats
def score(args):
    have = {r: f for r, f in RATERS.items() if (RES / f).exists()}
    if "R_H1" not in have or "R_B" not in have:
        sys.exit(f"missing rater files: need p3e_human_rH1.csv and p3e_human_rB.csv (have {sorted(have)})")
    if not (RES / "p3e_tier_rH1.csv").exists():  # Addendum 3: score only when both R_H1 files exist
        sys.exit("missing results/p3e_tier_rH1.csv (Addendum 3: score only with both R_H1 files)")
    buf = fernet().decrypt(KEYENC.read_bytes())
    assert sha(buf) == (KEYDIR / "p3e_human_key.sha256").read_text().split()[0], "P3E key does not match its hash"
    k = pd.read_csv(io.BytesIO(buf), dtype=str, keep_default_na=False)
    vbuf = fernet().decrypt(p3c.KEYENC.read_bytes())
    assert sha(vbuf) == (KEYDIR / "p3c_validity_key.sha256").read_text().split()[0], "V key does not match its hash"
    vk = pd.read_csv(io.BytesIO(vbuf), dtype=str, keep_default_na=False).set_index("check_id")
    KEYPLAIN.write_bytes(buf)
    k["truth"] = [vk.loc[v, "truth"] if o == "V" else "unknown (screen-unresolved)" for o, v in zip(k.origin, k.v_id)]
    k["family"] = [vk.loc[v, "family"] if o == "V" else "unresolved" for o, v in zip(k.origin, k.v_id)]
    k.loc[k.origin == "V", "pass1"] = ["exists" if f == "real" else "" for f in k.family[k.origin == "V"]]
    m = k[["check_id", "origin", "v_id", "truth", "family", "tier", "pass1", "paper_id", "key", "title"]]
    for r, f in have.items():
        x = rater_frame(r, f)
        x = x.rename(columns={c: (r if c == "exists" else f"{r}_{c}") for c in FILL})
        m = m.merge(x, on="check_id", how="left")
        m[r] = m[r].str.strip().str.lower()
        if f"{r}_label_pass1" in m.columns:
            m[f"{r}_label_pass1"] = m[f"{r}_label_pass1"].str.strip().str.lower()
    assert not m.apply(lambda c: c.str.contains(r"@[\w-]+\.[a-z]{2,}", regex=True)).any().any(), "email-like string"
    m.sort_values("check_id").to_csv(MERGED, index=False)
    if (RES / "p3e_tier_rH1.csv").exists():
        tb = fernet().decrypt(TKEYENC.read_bytes())
        assert sha(tb) == (KEYDIR / "p3e_tier_key.sha256").read_text().split()[0], "tier key does not match its hash"
        TKEYPLAIN.write_bytes(tb)
        tk = pd.read_csv(io.BytesIO(tb), dtype=str, keep_default_na=False)
        th = rd(RES / "p3e_tier_rH1.csv")[["tier_id", "tier_human"]]
        tk.merge(th, on="tier_id", how="left").to_csv(TMERGED, index=False)
    stats(args)


def _rate(k, n):
    return dict(k=int(k), n=int(n), rate=(k / n) if n else None, cp95=cp(int(k), int(n)) if n else None)


def stats(args):
    m = rd(MERGED)
    raters = [r for r in RATERS if r in m.columns]
    bad = {r: sorted(set(m[r]) - set(CATS)) for r in raters}
    assert not any(bad.values()), f"labels outside {CATS}: {bad}"
    out = {"label": "human-rated check (Amendment 7 (b), post hoc); descriptive", "n": len(m), "raters": raters,
           "composition": m.groupby(["origin", "family"]).size().reset_index().values.tolist()}
    neg, pos, unr = m[m.truth == "not-exists"], m[m.family == "real"], m[m.origin == "U"]
    for r in raters:
        s = {"neg_recall": _rate(neg[r].isin(["not-exists", "ambiguous"]).sum(), len(neg)),
             "neg_notexists_only": _rate((neg[r] == "not-exists").sum(), len(neg)),
             "pos_exists": _rate((pos[r] == "exists").sum(), len(pos)),
             "unresolved_exists": _rate((unr[r] == "exists").sum(), len(unr)),
             "unresolved_labels": unr[r].value_counts().to_dict()}
        for fam in ("gen_a", "gen_c"):
            f = neg[neg.family == fam]
            s[f"neg_recall_{fam}"] = {**_rate(f[r].isin(["not-exists", "ambiguous"]).sum(), len(f)),
                                      "labels": f[r].value_counts().to_dict()}
        out[r] = s
    pairs = [(a, b) for i, a in enumerate(raters) for b in raters[i + 1:]]
    out["pairs"] = {f"{a}-{b}": agree(m[a], m[b]) for a, b in pairs}
    p1 = m[m.pass1 != ""]
    if len(p1):
        out["pairs"]["R_B-pass1"] = agree(p1.R_B, p1.pass1)
    if "R_H1_label_pass1" in m.columns:  # Addendum 3: intra-rater (pass 1 vs pass 2 = the rating)
        a, b = m.R_H1_label_pass1, m.R_H1
        ch = m[a != b]
        t1 = pd.to_datetime(m.R_H1_pass1_at, utc=True, errors="coerce")
        t2 = pd.to_datetime(m.R_H1_checked_at, utc=True, errors="coerce")
        gap = (t2 - t1).dt.total_seconds() / 3600
        out["R_H1_intra"] = {"pass1_vs_pass2": agree(a, b), "n_changed": int(len(ch)),
                             "changed": [[i, x, y] for i, x, y in zip(ch.check_id, ch.R_H1_label_pass1, ch.R_H1)],
                             "changed_without_note": int((ch.R_H1_pass2_note.str.strip() == "").sum()),
                             "pass1_labels_outside_cats": sorted(set(a) - set(CATS)),
                             "gap_hours_min": None if gap.isna().all() else float(gap.min()),
                             "gap_unparsed_rows": int(gap.isna().sum()),
                             "gap_rows_under_12h": int((gap < 12).sum())}
        out["R_H1_pass1_stats"] = {"unresolved_exists": _rate((m[m.origin == "U"].R_H1_label_pass1 == "exists").sum(),
                                                              int((m.origin == "U").sum()))}
    humans = [r for r in raters if r.startswith("R_H")]
    out["reading_search_depth"] = {r: {"cp_lower": out[r]["unresolved_exists"]["cp95"][0],
                                       "kept": out[r]["unresolved_exists"]["cp95"][0] > 0.5} for r in humans}
    out["option"] = "A (two human raters, one not an author)" if "R_H2" in raters else \
        "B (one blind human check by the author; all other passes AI-assisted)"
    (RES / "p3e_human_stats.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1)[:4000])
    if TMERGED.exists():
        t = rd(TMERGED)
        t = t[t.tier_human.str.strip() != ""]
        t["tier_human"] = t.tier_human.str.strip().str.upper()
        conf = pd.crosstab(t.tier_machine, t.tier_human).reindex(index=TIERS, columns=TIERS, fill_value=0)
        acc = int((t.tier_machine == t.tier_human).sum())
        acad = int((t.tier_machine.isin(["J", "C", "P"]) == t.tier_human.isin(["J", "C", "P"])).sum())
        to = {"n": len(t), "accuracy": _rate(acc, len(t)), "academic_binary": _rate(acad, len(t)),
              "confusion_machine_rows_human_cols": conf.values.tolist(), "labels": TIERS,
              "per_tier": {s: {"precision": _rate(conf.loc[s, s], conf.loc[s].sum()),
                               "recall": _rate(conf.loc[s, s], conf[s].sum())} for s in TIERS}}
        (RES / "p3e_tier_stats.json").write_text(json.dumps(to, indent=1), encoding="utf-8")
        print(json.dumps(to, indent=1)[:2000])


# ---------------------------------------------------------------------------------------------- Amendment 8 (B)
KEY_PLAIN_SHA = "b4bba6e0f361bc56b203fea1339fbad6c038eefbb327aced8fd563f204266fd7"  # logged before the sheet was released
# check_id -> True if R_B's evidence_note reports the venue/year mismatch (coded by CC after unblinding, Amendment 6;
# all five notes state it: "entry's ... venue/year wrong")
GEN_C_NOTICED = {"H04": True, "H11": True, "H44": True, "H55": True, "H65": True}
RB_OUT = RES / "p3f_rB_score"


def load_key_rows():
    """Decrypted key of H01-H68 with the V rows' truth/family, in memory only (never written in plain form here).
    Stops if a plaintext hash differs from its commitment."""
    buf = fernet().decrypt(KEYENC.read_bytes())
    if sha(buf) != KEY_PLAIN_SHA:
        sys.exit(f"STOP: p3e_human_key plaintext sha256 {sha(buf)} != committed {KEY_PLAIN_SHA}")
    k = pd.read_csv(io.BytesIO(buf), dtype=str, keep_default_na=False)
    vbuf = fernet().decrypt(p3c.KEYENC.read_bytes())
    vsha = (KEYDIR / "p3c_validity_key.sha256").read_text().split()[0]
    if sha(vbuf) != vsha:
        sys.exit(f"STOP: V key plaintext sha256 {sha(vbuf)} != committed {vsha}")
    vk = pd.read_csv(io.BytesIO(vbuf), dtype=str, keep_default_na=False).set_index("check_id")
    k["truth"] = [vk.loc[v, "truth"] if o == "V" else "unknown (screen-unresolved)" for o, v in zip(k.origin, k.v_id)]
    k["family"] = [vk.loc[v, "family"] if o == "V" else "unresolved" for o, v in zip(k.origin, k.v_id)]
    return k, vk


def score_rb(args):
    """Amendment 8 (B): R_B only (no human file is read). Metrics of Amendment 6 -> results/p3f_rB_score.{csv,json}."""
    k, _ = load_key_rows()
    rb = rd(RES / RATERS["R_B"])
    m = k[["check_id", "origin", "v_id", "truth", "family", "tier"]].merge(
        rb[["check_id", "exists", "evidence_url", "evidence_note"]], on="check_id", how="left")
    m["label"] = m.exists.str.strip().str.lower()
    bad = sorted(set(m.label) - set(CATS))
    if bad:
        sys.exit(f"labels outside {CATS}: {bad}")
    rows = []

    def add(metric, family, k_, n_):
        lo, hi = cp(int(k_), int(n_)) if n_ else (None, None)
        rows.append(dict(metric=metric, family=family, k=int(k_), n=int(n_), rate=(k_ / n_) if n_ else None, cp95_lo=lo,
                         cp95_hi=hi))

    nz = m.label.isin(["not-exists", "ambiguous"])
    for fam in ("gen_a", "gen_c"):
        f = m.family == fam
        add("negative_recall (not-exists or ambiguous)", fam, int((f & nz).sum()), int(f.sum()))
        add("not-exists alone", fam, int((f & (m.label == "not-exists")).sum()), int(f.sum()))
    neg = m.truth == "not-exists"
    add("negative_recall (not-exists or ambiguous), pooled as in Amendment 6", "gen_a+gen_c", int((neg & nz).sum()),
        int(neg.sum()))
    gc = m[m.family == "gen_c"]
    add("gen_c rows whose evidence_note reports the venue/year mismatch (coded by CC)", "gen_c",
        sum(GEN_C_NOTICED.get(i, False) for i in gc.check_id), len(gc))
    real = m.family == "real"
    add("exists", "real V rows", int((real & (m.label == "exists")).sum()), int(real.sum()))
    u = m.origin == "U"
    add("exists", "flagged rows", int((u & (m.label == "exists")).sum()), int(u.sum()))
    add("ambiguous", "flagged rows", int((u & (m.label == "ambiguous")).sum()), int(u.sum()))
    add("not-exists", "flagged rows", int((u & (m.label == "not-exists")).sum()), int(u.sum()))
    tab = pd.DataFrame(rows)
    tab.to_csv(str(RB_OUT) + ".csv", index=False)
    note = m.evidence_note.fillna("")
    earlier = sorted(p.name for p in RES.glob("p3c_validity_r*.csv"))
    out = {"label": "R_B (AI sub-agent) characterisation, Amendment 8 (B); Supplement only; descriptive; no inference",
           "rater_file": RATERS["R_B"], "rater_file_sha256": sha((RES / RATERS["R_B"]).read_bytes()),
           "key_plaintext_sha256_checked": KEY_PLAIN_SHA, "metrics": rows,
           "earlier_ai_labels_V01_V20": earlier or "not available (no earlier AI label file of V01-V20 on disk)",
           "n_rows": len(m), "n_lenient_notes": int(note.str.contains("lenient", case=False).sum()),
           "lenient_rows": m.check_id[note.str.contains("lenient", case=False)].tolist(),
           "n_dblp_blocked_notes": int(note.str.contains("dblp", case=False).sum()),
           "limits": ["DBLP was behind a bot wall during rating (Crossref and web search were used instead)",
                      "the brief quotes 'three rows rated leniently'; the word does not occur in R_B's notes. Rows whose "
                      "note reports a title variant beyond a dropped subtitle: H40 (suffix variant), H50 (truncated "
                      "title), H54 (truncated by 1 word). Which three the brief meant is not verifiable from the file"]}
    (Path(str(RB_OUT) + ".json")).write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    print(tab.to_string(index=False))
    print({k_: out[k_] for k_ in ("n_lenient_notes", "lenient_rows", "n_dblp_blocked_notes", "earlier_ai_labels_V01_V20")})
    if args.show_gen_c:
        for _, r in gc.iterrows():
            print(r.check_id, "|", r.label, "|", (r.evidence_note or "")[:400])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["tier", "build", "score", "stats", "score-rb"])
    ap.add_argument("--show-gen-c", action="store_true", help="score-rb: print R_B's notes on the gen_c rows for coding")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--provisional", action="store_true", help="build only: interim flag set, separate files")
    ap.add_argument("--allow-unanswered", action="store_true", help="build only: after the Addendum-A deadline")
    args = ap.parse_args()
    args.seed = args.seed if args.seed is not None else {"tier": 46, "build": 47}.get(args.stage, 45)
    {"tier": tier, "build": build, "score": score, "stats": stats, "score-rb": score_rb}[args.stage](args)


if __name__ == "__main__":
    main()
