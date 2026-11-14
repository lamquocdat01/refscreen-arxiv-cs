#!/usr/bin/env python3
"""Topic 43 / P4 (Viec 12.4): scan a repository for what must not be published. Prints counts and paths, never values.

Checks (each must be 0): the author's real e-mail (read from \\email{} of the manuscript, or REAL_EMAIL), API key
values from the project .env (and the S2 key prefix), .env files, private paths (the topic folder, the Windows user
folder), files > 50 MB. With --history it also scans every commit: author/committer e-mails and `git grep` over all
revisions.
Usage: python code/p4_repo_scan.py <repo> [--history]
"""
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def secrets():
    keys = []
    env = ROOT / ".env"
    if env.exists():
        for ln in env.read_text(encoding="utf-8").splitlines():
            if "=" in ln and not ln.strip().startswith("#"):
                v = ln.split("=", 1)[1].strip().strip("\"'")
                if len(v) >= 12:
                    keys.append(v)
    m = re.search(r"\\email\{([^{}]+)\}", (ROOT / "submission_package" / "latex" / "main.tex").read_text(encoding="utf-8"))
    email = os.environ.get("REAL_EMAIL") or (m.group(1) if m else "")
    return keys, email


def main():
    repo = Path(sys.argv[1])
    keys, email = secrets()
    user = os.environ.get("USERNAME", "Admin")
    pats = {
        "real e-mail": [email] if email else [],
        "API key value": keys + ["s2" + "k-"],  # split so the scanner does not match itself
        "private path": ["PhD " + "Program", "02." + " Working", f"C:\\Users\\{user}", f"C:/Users/{user}", f"/c/Users/{user}"],
    }
    found = {k: [] for k in pats}
    found[".env file"], found["> 50 MB"] = [], []
    for p in repo.rglob("*"):
        if ".git" in p.parts or not p.is_file():
            continue
        rel = str(p.relative_to(repo))
        if p.name == ".env" or p.name.startswith(".env."):
            found[".env file"].append(rel)
        if p.stat().st_size > 50 * 1024 * 1024:
            found["> 50 MB"].append(rel)
        s = p.read_bytes().decode("utf-8", errors="ignore")
        for k, vals in pats.items():
            if any(v and v in s for v in vals):
                found[k].append(rel)
    for k, v in found.items():
        print(f"[{'PASS' if not v else 'FAIL'}] working tree, {k}: {len(v)} {v[:10]}")
    if "--history" in sys.argv:
        g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True,  # noqa: E731
                                      encoding="utf-8", errors="replace").stdout
        ids = set(g("log", "--all", "--format=%ae%n%ce").split())
        bad = [e for e in ids if not e.endswith("@users.noreply.github.com")]
        print(f"[{'PASS' if not bad else 'FAIL'}] history, author/committer e-mails not noreply: {len(bad)} distinct")
        revs = g("rev-list", "--all").split()
        for k, vals in pats.items():
            hits = 0
            for v in vals:
                if not v:
                    continue
                for r in revs:
                    out = g("grep", "-l", "-F", v, r)
                    hits += len([x for x in out.splitlines() if x.strip()])
            print(f"[{'PASS' if not hits else 'FAIL'}] history, {k}: {hits} (file, revision) hits over {len(revs)} commits")


if __name__ == "__main__":
    main()
