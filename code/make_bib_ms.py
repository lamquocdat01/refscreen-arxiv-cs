#!/usr/bin/env python3
"""Topic 43 / P3 (C5): build submission_package/latex/refs.bib for the manuscript from registry records only.

DOI entries: the record is verified with Crossref (works/<doi>, or DataCite for 10.48550 arXiv DOIs) and the BibTeX
text is what doi.org returns under content negotiation (Accept: application/x-bibtex). The script only assigns the
key, strips publisher markup, protects capitals/proper nouns with braces (C5c), drops month/ISSN/ISBN/abstract,
removes every `note` field (C5b) and re-emits one field per line.
URL-only entries (policy pages, software): fields below, each URL checked earlier in results/p2_policy_survey.csv or
lit/refs_verify.csv; access date goes into `howpublished` (sn-basic has no urldate; `note` stays empty).
Cache: $THS_DATASETS/_derived/43/cache/bib_ms/ (raw responses). Requests carry no identity (AGENT_RULES):
User-Agent "refscreen-fp/1.0 (mailto:noreply@example.org)".
Outputs: submission_package/latex/refs.bib, results/refs_ms_verify.csv
Usage: python make_bib_ms.py [--offline]
"""
import argparse
import csv
import hashlib
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ground_truth import DATA, ROOT  # noqa: E402

CACHE = DATA / "_derived" / "43" / "cache" / "bib_ms"
UA = "refscreen-fp/1.0 (mailto:noreply@example.org)"

DOI = [  # key, doi
    # prevalence, audits, policies with DOI
    ("Zhao2026hallucinations", "10.48550/arXiv.2605.07723"),
    ("Russinovich2026phantom", "10.48550/arXiv.2607.00738"),
    ("Sakai2026hallucitation", "10.48550/arXiv.2601.18724"),
    ("Topaz2026fabricated", "10.1016/S0140-6736(26)00603-3"),
    ("Bauchner2026fabricated", "10.1016/S0140-6736(26)00798-1"),
    ("Walters2023fabrication", "10.1038/s41598-023-41032-5"),
    ("Ansari2026compound", "10.48550/arXiv.2602.05930"),
    ("Han2026phantomcitations", "10.1002/asi.70104"),
    ("Chen2026beyondexistence", "10.1007/s11192-026-05727-6"),
    ("OrdunaMalea2023ghost", "10.1007/s11192-023-04804-4"),
    ("Chawla2026arxivban", "10.1038/d41586-026-01595-5"),
    ("Resnik2026hallucinated", "10.1080/08989621.2026.2645390"),
    # tools and tool reviews
    ("Badalova2026detecting", "10.48550/arXiv.2607.22693"),
    ("Abbonato2026checkifexist", "10.48550/arXiv.2602.15871"),
    ("Lee2026citecheck", "10.48550/arXiv.2603.17339"),
    ("Stringhini2026hallucinator", "10.1109/SPW72489.2026.00037"),
    ("Rao2026bibtex", "10.48550/arXiv.2604.03159"),
    ("HALLMARK2026", "10.48550/arXiv.2607.18360"),
    ("Shi2026citeaudit", "10.48550/arXiv.2602.23452"),
    ("Citetracer2026", "10.48550/arXiv.2605.08583"),
    ("Ilter2026gap", "10.48550/arXiv.2601.17431"),
    ("OracleGrounding2026", "10.48550/arXiv.2606.00898"),
    ("An2026whatcitations", "10.21203/rs.3.rs-10449790/v1"),
    ("Deb2026marebito", "10.1007/s11192-026-05868-8"),
    # coverage, data quality, matching
    ("Culbert2025openalex", "10.1007/s11192-025-05293-3"),
    ("Visser2021largescale", "10.1162/qss_a_00112"),
    ("DelgadoQuiros2024completeness", "10.1162/qss_a_00286"),
    ("DelgadoQuiros2024missing", "10.1002/asi.24839"),
    ("DelgadoQuiros2025citation", "10.1016/j.joi.2024.101618"),
    ("Zhou2026missingness", "10.1162/qss.a.400"),
    ("AlonsoAlvarez2025african", "10.1162/qss.a.396"),
    ("Forchino2026review", "10.1016/j.joi.2026.101800"),
    ("Aria2026matching", "10.1007/s11192-026-05763-2"),
    ("Ghaffari2023length", "10.1007/s11192-023-04780-9"),
    ("TeixeiraDaSilva2024name", "10.1007/s11192-024-05029-9"),
    ("Ortega2024retracted", "10.1007/s11192-024-05034-y"),
    ("Maisano2025doctype", "10.1007/s11192-025-05244-y"),
    ("Besancon2024sneaked", "10.1002/asi.24896"),
    ("BornmannLeibel2026accuracy", "10.1007/s11192-026-05841-5"),
    ("vanEck2019accuracy", "10.48550/arXiv.1906.07011"),
    ("Hendricks2020crossref", "10.1162/qss_a_00022"),
    ("Priem2022openalex", "10.48550/arXiv.2205.01833"),
    ("Kinney2023s2", "10.48550/arXiv.2301.10140"),
    ("Ley2009dblp", "10.14778/1687553.1687577"),
    ("Lopez2009grobid", "10.1007/978-3-642-04346-8_62"),
    ("Olensky2016matching", "10.1002/asi.23590"),
    ("MartinMartin2021coverage", "10.1007/s11192-020-03690-4"),
    ("Xu2026ghostcite", "10.48550/arXiv.2602.06718"),
    # statistics
    ("LeCam1960", "10.2140/pjm.1960.10.1181"),
    ("Hoeffding1956", "10.1214/aoms/1177728178"),
    ("Barbour1984", "10.1017/S0305004100061806"),
    ("Feinstein1990", "10.1016/0895-4356(90)90158-L"),
    ("Byrt1993", "10.1016/0895-4356(93)90018-V"),
    ("Gwet2008", "10.1348/000711006X126600"),
    ("Wilson1927", "10.1080/01621459.1927.10502953"),
    ("Efron1979", "10.1214/aos/1176344552"),
    ("Ioannidis2005why", "10.1371/journal.pmed.0020124"),
    ("Nosek2018prereg", "10.1073/pnas.1708274114"),
]

URL = [  # key, type, fields
    ("ACL2026statement", "misc", dict(author="{ACL 2026 Program Chairs}", title="{ACL} Statement on Desk Rejecting Papers with Hallucinated References",
                                      year="2026", url="https://2026.aclweb.org/acl_statement/", howpublished="Web page, accessed 21 October 2026")),
    ("EMNLP2026integrity", "misc", dict(author="{EMNLP 2026 Organizers}", title="{EMNLP} 2026 Paper Integrity Policy", year="2026",
                                        url="https://2026.emnlp.org/paper-integrity-policy/", howpublished="Web page, accessed 21 October 2026")),
    ("ICLR2025response", "misc", dict(author="{ICLR 2026 Program Chairs}", title="{ICLR} 2026 Response to {LLM}-Generated Papers and Reviews",
                                      year="2025", url="https://blog.iclr.cc/2025/11/19/iclr-2026-response-to-llm-generated-papers-and-reviews/",
                                      howpublished="Blog post, accessed 21 October 2026")),
    ("ICLR2026retrospective", "misc", dict(author="{ICLR 2026 Program Chairs}", title="A Retrospective on the {ICLR} 2026 Review Process",
                                           year="2026", url="https://blog.iclr.cc/2026/03/31/a-retrospective-on-the-iclr-2026-review-process/",
                                           howpublished="Blog post, accessed 21 October 2026")),
    ("NeurIPS2026handbook", "misc", dict(author="{NeurIPS 2026 Organizers}", title="{NeurIPS} 2026 Main Track Handbook", year="2026",
                                         url="https://neurips.cc/Conferences/2026/MainTrackHandbook", howpublished="Web page, accessed 21 October 2026")),
    ("ICML2026ethics", "misc", dict(author="{ICML 2026 Organizers}", title="{ICML} 2026 Peer Review Ethics", year="2026",
                                    url="https://icml.cc/Conferences/2026/PeerReviewEthics", howpublished="Web page, accessed 21 October 2026")),
    ("ICML2026ACinstructions", "misc", dict(author="{ICML 2026 Organizers}", title="{ICML} 2026 Area Chair Instructions", year="2026",
                                            url="https://icml.cc/Conferences/2026/AreaChairInstructions", howpublished="Web page, accessed 24 October 2026")),
    ("USENIXSec2026report", "misc", dict(author="{USENIX Security 2026 Program Chairs}",
                                         title="{USENIX} Security 2026: Report on Submissions with Invalid References", year="2026",
                                         url="https://docs.google.com/document/d/e/2PACX-1vSnHpeTFReelMZ124SzmgObXrHDN_B-UgxhOaE2RKfnfHn_qWuobI7kPg4TKBMhhZy_qxYtggCo7vjK/pub",
                                         howpublished="Public document, accessed 21 October 2026")),
    ("CVPR2026guidelines", "misc", dict(author="{CVPR 2026 Organizers}", title="{CVPR} 2026 Author Guidelines", year="2026",
                                        url="https://cvpr.thecvf.com/Conferences/2026/AuthorGuidelines", howpublished="Web page, accessed 21 October 2026")),
    ("arXiv2026moderation", "misc", dict(author="{arXiv}", title="Content Moderation", year="2026",
                                         url="https://info.arxiv.org/help/moderation/index.html", howpublished="Web page, accessed 21 October 2026")),
    ("SpringerNature2025checker", "misc", dict(author="{Springer Nature}", title="Springer Nature Unveils New {AI} Tool to Protect Research Integrity",
                                               year="2025", url="https://group.springernature.com/gp/group/media/press-releases/new-research-integrity-ai-tool/27769148",
                                               howpublished="Press release, accessed 21 October 2026")),
    ("GPTZero2026neurips", "misc", dict(author="{GPTZero}", title="{GPTZero} Finds 100 New Hallucinations in {NeurIPS} 2025 Accepted Papers",
                                        year="2026", url="https://gptzero.me/news/neurips/", howpublished="Web page, accessed 18 October 2026")),
    ("anystyle", "misc", dict(author="Keil, Sylvester", title="{AnyStyle}: Fast and Smart Citation Reference Parsing", year="2026",
                              url="https://github.com/inukshuk/anystyle", howpublished="Software repository, accessed 18 October 2026")),
    ("Shell2015ieeetran", "misc", dict(author="Shell, Michael", title="{IEEEtran} {BibTeX} Style, Version 1.14", year="2015",
                                      url="https://ctan.org/pkg/ieeetran", howpublished="CTAN package, accessed 16 October 2026")),
]

# fields the registry record leaves incomplete (R2 Q17): set after cleaning; None removes the field
FIX = {
    "Lopez2009grobid": {"booktitle": "Research and Advanced Technology for Digital Libraries: 13th European Conference, "
                                     "{ECDL} 2009", "series": "Lecture Notes in Computer Science", "volume": "5714"},
    "Walters2023fabrication": {"number": None, "pages": "14045"},  # article number; the registry issue "1" is not one
    "DelgadoQuiros2024missing": {"year": "2024"},  # one convention: the year of the issue (75(1), 2024; online 2023)
    "Olensky2016matching": {"year": "2016",  # issue 67(10), 2016; online 2015
                            "title": "Evaluation of the citation matching algorithms of {CWTS} and {iFQ} in comparison "
                                     "to the {Web of Science}"},
    "MartinMartin2021coverage": {"year": "2021"},  # issue 126(1), 2021; online 2020
    "Xu2026ghostcite": {"title": "{GhostCite}: A Large-Scale Analysis of Citation Validity in the Age of Large Language "
                                 "Models"},
}

PROTECT = ["OpenAlex", "Crossref", "CrossRef", "Scopus", "Web of Science", "Semantic Scholar", "DBLP", "GROBID", "ChatGPT", "LLM", "LLMs",
           "AI", "NeurIPS", "ACL", "ICLR", "arXiv", "BibTeX", "MCP", "PubMed", "Dimensions", "Scilit", "Lens", "Google Scholar",
           "African", "China", "Africa", "HalluCitation", "CheckIfExist", "Kappa", "F1000Research", "Poisson", "GPT", "HALLMARK",
           "NLP", "CiteAudit", "zbMATH", "Microsoft Academic", "OpenCitations", "COCI"]


# accented letters as LaTeX accents (sn-basic abbreviates first names byte-wise, which breaks UTF-8), typographic
# punctuation as ASCII TeX ligatures
TO_LATEX = [("İ", r"{\.I}"), ("Á", r"{\'A}"), ("á", r"{\'a}"), ("é", r"{\'e}"), ("É", r"{\'E}"), ("í", r"{\'i}"),
            ("ó", r"{\'o}"), ("ú", r"{\'u}"), ("ñ", r"{\~n}"), ("ç", r"{\c c}"), ("è", r"{\`e}"),
            ("ö", r'{\"o}'), ("ü", r'{\"u}'), ("ä", r'{\"a}'), ("‐", "-"), ("‑", "-"),
            ("–", "--"), ("—", "---"), ("’", "'"), ("‘", "`"), ("“", "``"), ("”", "''"),
            ("·", r"{\textperiodcentered}"), (" ", " ")]


def get(url, accept, fn):
    p = CACHE / fn
    if p.exists():
        return p.read_text(encoding="utf-8")
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": UA})
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                t = r.read().decode("utf-8", errors="replace")
            p.write_text(t, encoding="utf-8")
            time.sleep(1.0)
            return t
        except Exception as e:  # noqa: BLE001
            err = e
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"{url}: {err}")


def fid(doi):
    return hashlib.sha1(doi.lower().encode()).hexdigest()[:16]


def verify(doi):
    if doi.lower().startswith("10.48550/"):
        t = json.loads(get(f"https://api.datacite.org/dois/{doi.lower()}", "application/json", f"dc_{fid(doi)}.json"))
        a = t["data"]["attributes"]
        return a["titles"][0]["title"], str(a.get("publicationYear", ""))
    t = json.loads(get(f"https://api.crossref.org/works/{doi}?mailto=noreply@example.org", "application/json", f"cr_{fid(doi)}.json"))
    m = t["message"]
    title = " ".join(m.get("title", [""])) + ((": " + m["subtitle"][0]) if m.get("subtitle") else "")
    y = (m.get("published-print") or m.get("published-online") or m.get("issued") or {}).get("date-parts", [[""]])[0][0]
    return title, str(y)


def protect(s):
    for w in sorted(PROTECT, key=len, reverse=True):
        s = re.sub(rf"(?<![{{\w]){re.escape(w)}(?![\w}}])", "{" + w + "}", s)
    return s


def clean(bib, key, title_cr):
    bib = html.unescape(bib)
    bib = re.sub(r"<[^>]+>", "", bib)
    m = re.match(r"\s*@(\w+)\s*\{\s*[^,]+,(.*)\}\s*$", bib, re.S)
    typ, body = m.group(1).lower(), m.group(2)
    fields = {}
    for fm in re.finditer(r"(\w+)\s*=\s*(\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}|\"[^\"]*\"|\d+)", body):
        k, v = fm.group(1).lower(), fm.group(2)
        v = v[1:-1] if v[0] in "{\"" else v
        fields[k] = " ".join(v.split())
    for k in ("month", "issn", "isbn", "abstract", "note", "collection", "copyright", "keywords", "language"):
        fields.pop(k, None)
    if title_cr and len(title_cr) > len(fields.get("title", "")) + 3 and ":" in title_cr:
        fields["title"] = title_cr  # restore subtitle stored separately by the registry
    for k, v in fields.items():  # pdfLaTeX-safe ASCII for the characters registries use
        for u, r in TO_LATEX:
            v = v.replace(u, r)
        fields[k] = v
    if typ == "misc" and fields.get("publisher", "").strip("{}").lower() == "arxiv":
        typ = "article"
        fields["journal"] = "arXiv preprint"
        fields.pop("publisher", None)
    if fields.get("doi", "").lower().startswith("10.21203/"):  # Research Square preprint
        fields["journal"] = "Research Square preprint"
        fields.pop("publisher", None)
    if fields.get("doi", "").lower().startswith("10.48550/arxiv."):
        fields["doi"] = "10.48550/arXiv." + fields["doi"].split(".", 2)[2]
    fields["title"] = re.sub(r"(?<!\\)%", r"\\%", protect(fields.get("title", "")))
    for k in ("journal", "booktitle", "publisher"):
        if k in fields:
            fields[k] = protect(fields[k])
    if "doi" in fields:
        fields["doi"] = fields["doi"].replace("https://doi.org/", "")
        fields.pop("url", None)  # the DOI is printed as a link; a duplicate URL adds nothing
    for k, v in FIX.get(key, {}).items():
        if v is None:
            fields.pop(k, None)
        else:
            fields[k] = v
    typ = {"Lopez2009grobid": "inproceedings"}.get(key, typ)  # P3H: an LNCS proceedings paper; @inbook drops the booktitle
    order = ["author", "title", "journal", "booktitle", "series", "editor", "volume", "number", "pages", "year", "publisher", "school",
             "institution", "doi", "url", "howpublished"]
    keys = [k for k in order if k in fields] + sorted(k for k in fields if k not in order)
    return f"@{typ}{{{key},\n" + ",\n".join(f"  {k} = {{{fields[k]}}}" for k in keys) + "\n}\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    out, rows = ["% generated by code/make_bib_ms.py from registry records; do not edit by hand\n"], []
    for key, doi in DOI:
        title, year = verify(doi)
        bib = get(f"https://doi.org/{doi}", "application/x-bibtex; charset=utf-8", f"bib_{fid(doi)}.bib")
        out.append(clean(bib, key, title))
        rows.append(dict(key=key, doi=doi, url="", registry_title=title, registry_year=year, status="OK (registry)"))
    for key, typ, f in URL:
        f = dict(f)
        f["title"] = protect(f["title"]) if "{" not in f["title"] else f["title"]
        out.append(f"@{typ}{{{key},\n" + ",\n".join(f"  {k} = {{{v}}}" for k, v in f.items()) + "\n}\n")
        rows.append(dict(key=key, doi="", url=f["url"], registry_title=f["title"], registry_year=f["year"], status="URL-ONLY"))
    (ROOT / "submission_package" / "latex" / "refs.bib").write_text("\n".join(out), encoding="utf-8")
    with (ROOT / "results" / "refs_ms_verify.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(len(rows), "entries;", sum(r["status"].startswith("OK") for r in rows), "with DOI")


if __name__ == "__main__":
    main()
