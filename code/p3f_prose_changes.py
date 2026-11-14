"""P3F Viec 6 item 24: list every sentence of main.tex that changed between v1.3 (P3F/backup_before/v13_20261112/main.tex) and v1.4.

Sentences are split from the LaTeX source after removing comments, table bodies, figure environments and the
preamble; macros are kept as written (\\nv{key}), so a change of number alone does not count as a prose change.
Output: P3F/PROSE_CHANGES_P3F.md (removed, added, and a count of the "X, not Y" closers and of the repeated formula).
Usage: python code/p3f_prose_changes.py
"""
import difflib
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / "code"))
from strip_comments import strip  # noqa: E402


def sentences(tex):
    tex = strip(tex)
    tex = tex[tex.index(r"\begin{document}"):]
    tex = re.sub(r"\\begin\{(table|figure)\}.*?\\end\{\1\}", " ", tex, flags=re.S)
    tex = re.sub(r"\\begin\{appendices\}.*?\\end\{appendices\}", " ", tex, flags=re.S)
    tex = re.sub(r"\s+", " ", tex)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\\])", tex)
    return [p.strip() for p in parts if len(p.split()) >= 4]


old = sentences((R / "P3F" / "backup_before" / "v13_20261112" / "main.tex").read_text(encoding="utf-8"))
new = sentences((R / "submission_package" / "latex" / "main.tex").read_text(encoding="utf-8"))
sm = difflib.SequenceMatcher(None, old, new, autojunk=False)
rem, add = [], []
for op, i1, i2, j1, j2 in sm.get_opcodes():
    if op in ("delete", "replace"):
        rem += old[i1:i2]
    if op in ("insert", "replace"):
        add += new[j1:j2]
formula = re.compile(r"sufficient to lower.*only route we measured", re.I)
notx = re.compile(r",\s*not\s+(?:a|an|the|one|by|in)?\s*\w+[^.]*\.$|\bnot\b[^.,]{0,40}\bbut\b", re.I)
out = ["# PROSE_CHANGES — main.tex v1.3 → v1.4 (P3F, Amendment 8)", "",
       f"Câu (≥ 4 từ, ngoài bảng/hình/phụ lục): v1.3 {len(old)}, v1.4 {len(new)}; bỏ hoặc sửa {len(rem)}, thêm hoặc sửa {len(add)}.",
       f"Câu 'sufficient … only route we measured': v1.3 {sum(bool(formula.search(s)) for s in old)} lần, "
       f"v1.4 {sum(bool(formula.search(s)) for s in new)} lần (main.tex; abstract dùng câu ngắn khác).",
       f"Câu > 35 từ (đếm thô trên nguồn): v1.3 {sum(len(s.split()) > 35 for s in old)}, v1.4 {sum(len(s.split()) > 35 for s in new)}.",
       "", "Danh sách sinh tự động từ nguồn LaTeX; macro số giữ nguyên dạng `\\nv{...}`.", "",
       "## Câu bỏ hoặc thay (v1.3)", ""]
out += [f"- {s}" for s in rem]
out += ["", "## Câu thêm hoặc thay (v1.4)", ""]
out += [f"- {s}" for s in add]
(R / "P3F" / "PROSE_CHANGES_P3F.md").write_text("\n".join(out) + "\n", encoding="utf-8")
print(out[2:5])
