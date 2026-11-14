#!/usr/bin/env python3
"""Topic 43: files that are never packaged: source.zip / upload/, the Zenodo stage, the repository sync and the
recompute work copy. Secrets (the OpenAlex key lives in ROOT/.env) and local-only key material.

Use:
  shutil.copytree(src, dst, ignore=package_exclude.ignore)       # copy without excluded files
  package_exclude.excluded("path/to/file")                        # True for an excluded name anywhere in the path
  package_exclude.assert_clean(list_of_paths_or_zip_member_names)  # raise if any excluded name is present
verify_package.py (gate G11k) additionally checks that no packaged file contains the key value.
"""
import fnmatch
from pathlib import PurePath

EXCLUDE = [".env", ".env.*", "*.env", "keys", "*.key", "*.enc", "*fernet*"]


def excluded(path):
    return any(fnmatch.fnmatch(part, pat) for part in PurePath(str(path).replace("\\", "/")).parts for pat in EXCLUDE)


def ignore(_dirpath, names):
    return [n for n in names if excluded(n)]


def assert_clean(paths):
    bad = [str(p) for p in paths if excluded(p)]
    if bad:
        raise SystemExit(f"excluded file(s) in a package: {bad[:5]}")
