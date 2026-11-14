#!/usr/bin/env python3
"""Topic 43 / P3G (POSTHOC_NOTE_P3G.md P11; POST HOC): code each counted policy statement of results/p2_policy_survey.csv
(official, verify_status != not-found-at-source; the 26 statements of Table S2) by the step between a flag and a rejection,
from the stored quotation and rule text only (no new fetching). Coding by Claude Code (an AI model), recorded per row
with the words it rests on; descriptive.
Codes:
  confirm   rejection or sanction only after a stated human check (chair, AC/SAC, PC, integrity group, "confirmed")
  no_confirm  a rejection or desk-rejection rule with no human confirmation step stated in the statement
  no_rule   no rejection rule for non-existent references stated
Outputs: results/p3g_policy_coding.csv, results/p3g_policy_coding.json
Usage: python code/p3g_policy_coding.py
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
CODE = {  # venue -> (code, words the code rests on)
    "ACL 2026 (camera-ready)": ("confirm", "all flags reviewed by PCs and SACs"),
    "ACL Rolling Review (ARR)": ("no_confirm", "listed among desk-rejection reasons; no check stated"),
    "EMNLP 2026 (via ARR)": ("confirm", "flagged entries further examined and verified by the senior program committee"),
    "ICLR 2026": ("confirm", "action only if an AC/SAC identifies concrete evidence"),
    "ICLR 2026 (retrospective)": ("confirm", "confirmed hallucinated references; flags checked by ACs then PCs"),
    "NeurIPS 2026": ("no_rule", "violation of the Code of Conduct; no penalty stated"),
    "NeurIPS 2025 LLM policy": ("no_rule", "may revoke publication status; investigation"),
    "ICML 2026": ("confirm", "area chairs email the program chairs (escalation)"),
    "CVPR 2026": ("no_confirm", "will be rejected when found, may be rejected without review"),
    "AAAI-27": ("confirm", "violations subcommittee, case by case"),
    "USENIX Security 2026": ("confirm", "confirmed by a chair and the responsible Vice Chair"),
    "USENIX Security 2027": ("no_confirm", "might lead to the paper being desk rejected"),
    "arXiv (moderation policy page)": ("no_rule", "authors responsible; no rule stated"),
    "Springer Nature": ("confirm", "RIG checks manually and decides"),
    "Elsevier": ("no_rule", "no sanction or threshold stated"),
    "Wiley": ("no_rule", "rule on citation manipulation, not on non-existent references"),
    "PLOS": ("no_rule", "no explicit rule on non-existent references"),
    "IEEE": ("no_rule", "no rule found"),
    "ECCV 2026": ("no_confirm", "glaring examples can be desk-rejected"),
    "ACM CCS 2026": ("no_confirm", "may be desk rejected"),
    "ICSE 2027 (Research Track)": ("confirm", "confirmed cases desk-rejected"),
    "FSE 2027 (Research Papers)": ("confirm", "confirmed fabricated or hallucinated citations desk-rejected"),
    "AISTATS 2027": ("no_confirm", "may lead to desk rejection"),
    "ISCA 2027": ("no_confirm", "clear, verifiable issues may lead to desk rejection"),
    "ACM ASIACCS 2027": ("no_confirm", "desk-rejection reason before reviewer assignment"),
    "IEEE CSF 2027": ("no_confirm", "will be desk rejected"),
}
NUMERIC = {"EMNLP 2026 (via ARR)": "any (>= 1)", "ICML 2026": "2 (escalation)", "USENIX Security 2026": ">= 3"}


def main():
    x = pd.read_csv(RES / "p2_policy_survey.csv", dtype=str, keep_default_na=False)
    ok = x[(x.source_type == "official") & (x.verify_status != "not-found-at-source")].copy()
    miss = sorted(set(ok.venue) - set(CODE))
    if miss:
        raise SystemExit(f"uncoded statements: {miss}")
    ok["code"] = ok.venue.map(lambda v: CODE[v][0])
    ok["rests_on"] = ok.venue.map(lambda v: CODE[v][1])
    ok["numeric_threshold"] = ok.venue.map(lambda v: NUMERIC.get(v, ""))
    ok[["venue", "code", "rests_on", "numeric_threshold", "threshold_or_rule", "source_url"]].to_csv(RES / "p3g_policy_coding.csv", index=False)
    c = ok.code.value_counts().to_dict()
    num = ok[ok.numeric_threshold != ""]
    out = dict(label="POST HOC (POSTHOC_NOTE_P3G.md P11); coded by Claude Code from stored text; descriptive",
               n=len(ok), counts=c, numeric_thresholds=len(num), numeric_with_confirmation=int((num.code == "confirm").sum()),
               no_confirm_venues=sorted(ok[ok.code == "no_confirm"].venue))
    (RES / "p3g_policy_coding.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
