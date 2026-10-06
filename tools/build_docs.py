#!/usr/bin/env python3
"""build_docs.py — DocSources/<App>/<Doc>_<lang>.md → Stage/<App><yymmdd>/*.html

用法：
    python3 tools/build_docs.py --app LIV --date 250529            # 產出到 Stage/LIV250529/
    python3 tools/build_docs.py --app LIV --date 250529 --check    # 只比對現有 HTML 的去標籤文字，不寫檔

規則（specs/02 §1、D4、D15、D16、P1–P3）：
- 原稿只在 DocSources/<App>/，HTML 一律可重新產生。
- 產出檔名每個 App 不同，以 App 程式碼寫死的為準；全部寫在下面的 APPS 表，新 App 加一列。
- 只依賴標準庫 + markdown（pip 的 `markdown` 套件，已裝 3.6）；不裝 pandoc、不引入產生器。
- 本腳本永遠不碰 version-info.json，也不碰 Release/。Stage 驗過再手動複製到 Release。

轉換核心拆成兩層，官網產生器（SITE-10）重用第一層：
    md_to_html_fragment(md_text)  -> HTML 片段（只有 body 內容）
    render_page(fragment, ...)    -> 套 _template/page.html + style.css 成完整頁
"""

from __future__ import annotations

import argparse
import difflib
import html as htmllib
import re
import sys
from pathlib import Path

try:
    import markdown  # https://python-markdown.github.io/  (D15)
except ImportError:  # pragma: no cover
    sys.exit("需要 Python 套件 `markdown`（pip3 install markdown）")

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_SOURCES = REPO_ROOT / "DocSources"
TEMPLATE_DIR = DOC_SOURCES / "_template"
STAGE_DIR = REPO_ROOT / "Stage"

LANGS = ("zh", "ja", "en")
DOCS = ("AboutMe", "PrivacyPolicy", "TermsOfUse")

# ---------------------------------------------------------------------------
# 每 App 的產出檔名表（P1：App 程式碼寫死的名字，只加不改）
#   值可以是：
#     "pattern"                 → 三語都產，{date} 代入 --date、{lang} 代入語言
#     ("pattern", ("en",))      → 只產指定語言；pattern 內沒有 {lang} 就是單一檔
#   程式碼位置見 specs/02 §1 的表。
# ---------------------------------------------------------------------------
APPS: dict[str, dict[str, str | tuple[str, tuple[str, ...]]]] = {
    # Life with Villager — SystemConfigure.swift:56–
    "LIV": {
        "AboutMe": "AboutMe_{lang}.html",
        "PrivacyPolicy": "PrivacyPolicy_{date}_{lang}.html",
        "TermsOfUse": "TermsOfUse_{date}_{lang}.html",
    },
    # Trace Your BLE — AppSysDefaults.swift:88–
    "TYBLE": {
        "AboutMe": "AboutMe_{lang}.html",
        "PrivacyPolicy": "PrivacyPolicy_{date}_{lang}.html",
        "TermsOfUse": "TermsOfUse_{date}_{lang}.html",
    },
    # Quick Collection Check — AppSysDefaults.swift:65–91
    # 隱私權只有一份英文、三語共用、檔名無語言；條款的日期 211011 ≠ 目錄日期 210917。
    "QCC": {
        "AboutMe": "AboutMe_{lang}.html",
        "PrivacyPolicy": ("PrivacyPolicy210917.html", ("en",)),
        "TermsOfUse": "TermsOfUse211011_{lang}.html",
    },
    # Khoo Khoo Book — Config/App.xcconfig 三值（specs/02 §4），格式同 LIV
    "KKB": {
        "AboutMe": "AboutMe_{lang}.html",
        "PrivacyPolicy": "PrivacyPolicy_{date}_{lang}.html",
        "TermsOfUse": "TermsOfUse_{date}_{lang}.html",
    },
}

# <html lang="…">
HTML_LANG = {"zh": "zh-Hant", "ja": "ja", "en": "en"}

# <title>；只進 <head>，不進 body（body 文字要與原稿一字不差）
TITLES = {
    "AboutMe": {"zh": "關於我", "ja": "私について", "en": "About Me"},
    "PrivacyPolicy": {"zh": "隱私權政策", "ja": "プライバシーポリシー", "en": "Privacy Policy"},
    "TermsOfUse": {"zh": "使用條款", "ja": "利用規約", "en": "Terms of Use"},
}

# markdown 擴充：只用套件內建的 nl2br（原稿是「一行一段、換行就是換行」的寫法，
# 例如「Robin Hsu⏎E-Mail: …」與「1. …⏎2. …」要各自一行，現役 HTML 也是這樣排）。
MD_EXTENSIONS = ["nl2br"]


# ---------------------------------------------------------------------------
# 轉換核心 ①：md → HTML 片段（SITE-10 重用這個）
# ---------------------------------------------------------------------------
def md_to_html_fragment(md_text: str, extensions: list[str] | None = None) -> str:
    """把 markdown 原稿轉成 HTML 片段（只有 body 內容，不含模板）。"""
    md_text = md_text.lstrip("﻿")  # 有些原稿帶 BOM
    return markdown.markdown(
        md_text,
        extensions=MD_EXTENSIONS if extensions is None else extensions,
        output_format="html",
    )


# ---------------------------------------------------------------------------
# 轉換核心 ②：套模板成完整頁、寫檔
# ---------------------------------------------------------------------------
def load_template(template_dir: Path = TEMPLATE_DIR) -> tuple[str, str]:
    page = (template_dir / "page.html").read_text(encoding="utf-8")
    style = (template_dir / "style.css").read_text(encoding="utf-8")
    return page, style


def strip_css_comments(css: str) -> str:
    """內嵌進頁面時拿掉 /* … */ 註解（註解留在 style.css 給維護者看就好）。"""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return re.sub(r"\n{3,}", "\n\n", css).strip("\n")


def render_page(
    fragment: str,
    *,
    title: str,
    lang: str,
    updated: str,
    template: tuple[str, str] | None = None,
) -> str:
    """HTML 片段 + 模板（{{title}} {{lang}} {{body}} {{updated}} {{style}}）→ 完整頁。"""
    page, style = template or load_template()
    out = page
    for key, value in (
        ("{{title}}", htmllib.escape(title, quote=True)),
        ("{{lang}}", htmllib.escape(lang, quote=True)),
        ("{{updated}}", htmllib.escape(updated, quote=True)),
        ("{{style}}", strip_css_comments(style)),
        ("{{body}}", fragment.strip("\n")),
    ):
        out = out.replace(key, value)
    return out


def write_page(path: Path, page_html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page_html, encoding="utf-8")


# ---------------------------------------------------------------------------
# --check：去標籤後的 body 文字比對
# ---------------------------------------------------------------------------
def visible_text(page_html: str) -> str:
    """<body> 內去標籤、解 entity、空白壓成單一空格。
    與派工單的一行指令同一精神，只是限定在 <body>（<style>、<title> 不是使用者看得到的文字）。"""
    m = re.search(r"<body[^>]*>(.*?)</body>", page_html, flags=re.S | re.I)
    s = m.group(1) if m else page_html
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"<(script|style)\b.*?</\1\s*>", "", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = htmllib.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def describe_diff(expected: str, actual: str, context: int = 20) -> list[str]:
    """列出兩段文字的差異片段（expected＝現役 HTML，actual＝腳本產出）。"""
    sm = difflib.SequenceMatcher(None, expected, actual, autojunk=False)
    lines = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        e = expected[max(0, i1 - context): i2 + context]
        a = actual[max(0, j1 - context): j2 + context]
        lines.append(f"      {tag:7s} 現役: …{e}…")
        lines.append(f"      {'':7s} 產出: …{a}…")
    return lines


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def iso_date(yymmdd: str) -> str:
    return f"20{yymmdd[0:2]}-{yymmdd[2:4]}-{yymmdd[4:6]}"


def plan_outputs(app: str, date: str) -> list[tuple[str, str, Path, str]]:
    """回傳 [(doc, lang, 原稿路徑, 產出檔名)]。"""
    plan = []
    for doc in DOCS:
        spec = APPS[app][doc]
        if isinstance(spec, tuple):
            pattern, langs = spec
        else:
            pattern, langs = spec, LANGS
        for lang in langs:
            src = DOC_SOURCES / app / f"{doc}_{lang}.md"
            name = pattern.format(date=date, lang=lang)
            plan.append((doc, lang, src, name))
    return plan


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--app", required=True, choices=sorted(APPS), help="App 代號")
    ap.add_argument("--date", required=True, help="目錄日期 yymmdd，如 250529 → Stage/LIV250529/")
    ap.add_argument("--check", action="store_true", help="只與 Stage 現有 HTML 比對去標籤文字，不寫檔")
    args = ap.parse_args(argv)

    if not re.fullmatch(r"\d{6}", args.date):
        ap.error("--date 要是 6 位數 yymmdd")

    out_dir = STAGE_DIR / f"{args.app}{args.date}"
    template = load_template()
    updated = iso_date(args.date)
    plan = plan_outputs(args.app, args.date)

    missing = [src for _, _, src, _ in plan if not src.is_file()]
    if missing:
        for src in missing:
            print(f"缺原稿：{src.relative_to(REPO_ROOT)}", file=sys.stderr)
        return 2

    failures = 0
    mode = "CHECK" if args.check else "BUILD"
    print(f"[{mode}] {args.app} → {out_dir.relative_to(REPO_ROOT)}/")
    for doc, lang, src, name in plan:
        fragment = md_to_html_fragment(src.read_text(encoding="utf-8"))
        page = render_page(
            fragment,
            title=TITLES[doc][lang],
            lang=HTML_LANG[lang],
            updated=updated,
            template=template,
        )
        target = out_dir / name
        if args.check:
            if not target.is_file():
                print(f"  MISSING  {name}（Stage 沒有這個檔，無從比對）")
                failures += 1
                continue
            expected = visible_text(target.read_text(encoding="utf-8"))
            actual = visible_text(page)
            if expected == actual:
                print(f"  OK       {name}")
            else:
                failures += 1
                print(f"  DIFF     {name}")
                for line in describe_diff(expected, actual):
                    print(line)
        else:
            write_page(target, page)
            print(f"  wrote    {name}  ← {src.relative_to(REPO_ROOT)}")

    if args.check:
        print(f"[CHECK] {len(plan) - failures}/{len(plan)} OK")
        return 1 if failures else 0
    print(f"[BUILD] {len(plan)} 檔寫入 {out_dir.relative_to(REPO_ROOT)}/；version-info.json 未動。"
          "驗過再手動複製到 Release/（P3）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
