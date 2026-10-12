"""Création de documents (partie 22) : md, txt, html, json, csv, docx, pdf, xlsx — sans dépendance.

- DOCX : HTML → textutil (natif macOS).
- PDF : HTML → Google Chrome sans interface (--print-to-pdf), si Chrome est présent.
- XLSX : écrit directement (format OpenXML minimal, zip).
"""
from __future__ import annotations

import csv
import html as htmlmod
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List
from xml.sax.saxutils import escape

from ..errors import JarvisError, ValidationError
from .files import keep_version
from .registry import CONFIRME, ECHOUE, Tool

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

CSS = """body{font-family:-apple-system,'Helvetica Neue',Arial,sans-serif;max-width:760px;margin:40px auto;color:#16201d;line-height:1.55;font-size:11pt}
h1{font-size:22pt;margin:0 0 6px}h2{font-size:15pt;margin-top:26px;border-bottom:1px solid #d9e2df;padding-bottom:4px}h3{font-size:12pt}
table{border-collapse:collapse;width:100%}td,th{border:1px solid #cfd8d5;padding:6px 8px;text-align:left}th{background:#eef3f1}
code{background:#f1f4f3;padding:1px 4px;border-radius:3px}blockquote{border-left:3px solid #00a07a;margin:0;padding-left:12px;color:#40504b}"""


def markdown_to_html(md: str, title: str = "") -> str:
    """Convertisseur Markdown simple (titres, listes, gras, italique, code, liens, tableaux)."""
    lines = md.replace("\r\n", "\n").split("\n")
    out: List[str] = []
    in_list, in_code, table = None, False, []

    def inline(t: str) -> str:
        t = htmlmod.escape(t)
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", t)
        t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', t)
        return t

    def flush_table():
        nonlocal table
        if table:
            rows = [r for r in table if not re.match(r"^\|?\s*:?-{2,}", r.strip().strip("|").strip())]
            cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
            h = "".join(f"<th>{inline(c)}</th>" for c in cells[0])
            b = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in cells[1:])
            out.append(f"<table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>")
            table = []

    for line in lines:
        if line.startswith("```"):
            if in_code:
                out.append("</code></pre>")
            else:
                out.append("<pre><code>")
            in_code = not in_code
            continue
        if in_code:
            out.append(htmlmod.escape(line))
            continue
        if line.strip().startswith("|"):
            table.append(line)
            continue
        flush_table()
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        lm = re.match(r"^\s*([-*]|\d+\.)\s+(?:\[( |x)\]\s+)?(.*)", line)
        if lm:
            kind = "ol" if lm.group(1)[0].isdigit() else "ul"
            if in_list != kind:
                if in_list:
                    out.append(f"</{in_list}>")
                out.append(f"<{kind}>")
                in_list = kind
            box = "☑ " if lm.group(2) == "x" else ("☐ " if lm.group(2) == " " else "")
            out.append(f"<li>{box}{inline(lm.group(3))}</li>")
            continue
        if in_list:
            out.append(f"</{in_list}>")
            in_list = None
        if m:
            n = len(m.group(1))
            out.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
        elif line.startswith(">"):
            out.append(f"<blockquote>{inline(line[1:].strip())}</blockquote>")
        elif line.strip():
            out.append(f"<p>{inline(line)}</p>")
    flush_table()
    if in_list:
        out.append(f"</{in_list}>")
    t = htmlmod.escape(title or "Document")
    return f'<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>{t}</title><style>{CSS}</style></head><body>' + "\n".join(out) + "</body></html>"


def _col(n: int) -> str:
    s = ""
    while n >= 0:
        s = chr(65 + n % 26) + s
        n = n // 26 - 1
    return s


def write_xlsx(path: Path, rows: List[List[Any]], sheet: str = "Feuille1") -> None:
    def cell(ref, v):
        if isinstance(v, bool) or v is None:
            v = "" if v is None else str(v)
        if isinstance(v, (int, float)):
            return f'<c r="{ref}"><v>{v}</v></c>'
        return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(str(v))}</t></is></c>'

    data = "".join(f'<row r="{i + 1}">' + "".join(cell(f"{_col(j)}{i + 1}", v) for j, v in enumerate(r)) + "</row>"
                   for i, r in enumerate(rows))
    files = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="{escape(sheet[:31])}" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        "xl/worksheets/sheet1.xml": '<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{data}</sheetData></worksheet>",
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in files.items():
            z.writestr(name, content)


def _chrome_pdf(src: Path, path: Path, td: str, timeout: float = 60) -> None:
    """Chrome sans interface écrit le PDF mais ne rend pas toujours la main : on attend que le
    fichier soit complet (taille stable), puis on arrête le processus."""
    import signal
    import time
    if path.exists():
        path.unlink()
    proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--no-first-run",
                             "--no-default-browser-check", "--use-mock-keychain", "--disable-extensions",
                             f"--user-data-dir={td}/profil", f"--print-to-pdf={path}", src.as_uri()],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    end, last, stable = time.time() + timeout, -1, 0
    try:
        while time.time() < end:
            if path.exists():
                size = path.stat().st_size
                stable = stable + 1 if size == last and size > 0 else 0
                last = size
                if stable >= 3 and path.read_bytes()[-1024:].rstrip().endswith(b"%%EOF"):
                    return
            if proc.poll() is not None and not path.exists():
                break
            time.sleep(0.2)
        raise JarvisError("Conversion PDF échouée (Chrome n'a pas produit le fichier).", code="conversion")
    finally:
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except Exception:  # noqa: BLE001
                    pass


def create_document(app, path: Path, fmt: str, content: str, title: str, rows: Any = None) -> Dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    prev = keep_version(path) if path.exists() else None
    if fmt in ("md", "txt"):
        path.write_text(content, encoding="utf-8")
    elif fmt == "html":
        path.write_text(content if content.lstrip().lower().startswith("<!doctype") or "<html" in content[:300].lower()
                        else markdown_to_html(content, title), encoding="utf-8")
    elif fmt == "json":
        try:
            obj = json.loads(content)
        except ValueError:
            raise ValidationError("Contenu JSON invalide.")
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    elif fmt in ("csv", "xlsx"):
        data = rows
        if data is None:
            data = list(csv.reader(io.StringIO(content)))
        if not isinstance(data, list) or not all(isinstance(r, list) for r in data):
            raise ValidationError("Pour csv/xlsx, fournis rows (liste de lignes) ou un contenu CSV.")
        if fmt == "csv":
            with open(path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerows(data)
        else:
            write_xlsx(path, data, title or "Feuille1")
    elif fmt in ("docx", "pdf"):
        html_doc = content if "<html" in content[:300].lower() else markdown_to_html(content, title)
        td = tempfile.mkdtemp(prefix="jarvis-doc-")
        try:
            src = Path(td) / "doc.html"
            src.write_text(html_doc, encoding="utf-8")
            if fmt == "docx":
                r = subprocess.run(["textutil", "-convert", "docx", "-output", str(path), str(src)], capture_output=True, timeout=60)
                if r.returncode != 0:
                    raise JarvisError("Conversion DOCX impossible (textutil).", {"stderr": r.stderr.decode()[:300]}, code="conversion")
            else:
                if not os.path.exists(CHROME):
                    raise JarvisError("PDF : Google Chrome est nécessaire pour la conversion.", code="conversion")
                _chrome_pdf(src, path, td)
        finally:
            shutil.rmtree(td, ignore_errors=True)
    else:
        raise ValidationError("Format non pris en charge.")
    return {"path": str(path), "format": fmt, "bytes": path.stat().st_size, "previous_version": prev}


def verify_document(path: str, fmt: str) -> (str, str):
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return ECHOUE, "fichier absent ou vide"
    head = p.read_bytes()[:8]
    if fmt in ("docx", "xlsx"):
        try:
            with zipfile.ZipFile(p) as z:
                if z.testzip() is not None:
                    return ECHOUE, "archive OpenXML corrompue"
        except zipfile.BadZipFile:
            return ECHOUE, "pas un fichier OpenXML valide"
        return CONFIRME, f"{fmt.upper()} valide ({p.stat().st_size} octets)"
    if fmt == "pdf":
        return (CONFIRME, f"PDF valide ({p.stat().st_size} octets)") if head.startswith(b"%PDF") else (ECHOUE, "en-tête PDF absent")
    if fmt == "json":
        try:
            json.loads(p.read_text(encoding="utf-8"))
            return CONFIRME, "JSON relu et valide"
        except ValueError:
            return ECHOUE, "JSON invalide"
    return CONFIRME, f"fichier présent ({p.stat().st_size} octets)"


def h_create(ctx, a):
    path = ctx.app.permissions.resolve_path(a["path"], write=True)
    fmt = a.get("format") or path.suffix.lstrip(".").lower()
    if path.exists() and not a.get("overwrite"):
        raise ValidationError("Le fichier existe déjà : passe overwrite=true (version précédente conservée).", {"chemin": str(path)})
    return create_document(ctx.app, path, fmt, a.get("content", ""), a.get("title", ""), a.get("rows"))


def v_create(ctx, a, r):
    return verify_document(r["path"], r["format"])


FORMATS = ["md", "txt", "html", "json", "csv", "xlsx", "docx", "pdf"]


def register(reg) -> None:
    P = lambda **kw: kw  # noqa: E731
    reg.register(Tool("document_creer", "Créer un document (md, txt, html, json, csv, xlsx, docx, pdf). Le contenu est en Markdown pour html/docx/pdf.",
                      {"path": P(type="string", required=True), "format": P(type="string", enum=FORMATS),
                       "content": P(type="string", maxLength=1_000_000), "title": P(type="string"),
                       "rows": P(type="array", description="lignes pour csv/xlsx (liste de listes)", maxItems=20000),
                       "overwrite": P(type="boolean", default=False)},
                      h_create, "modere", "documents", 120, "dossiers autorisés en écriture", "document créé",
                      "relecture du format produit", v_create))
