#!/usr/bin/env python3
"""Vérification statique de JARVIS, sans dépendance :

- Python : syntaxe compatible 3.9 (ast), imports inutilisés, noms de module manquants (import réel des modules),
  annotations sans « from __future__ » interdites en 3.9 (X | Y).
- JavaScript : syntaxe (moteur JavaScriptCore de macOS), imports inutilisés, imports de noms inexistants.
- CSS : variables utilisées mais non définies, couleurs codées en dur hors de tokens.css.
- Secrets : aucun secret probable dans les fichiers suivis.
Code de sortie 0 = aucun problème.
"""
from __future__ import annotations

import ast
import importlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
problems = []


def py_files():
    yield ROOT / "jarvis.py"
    for d in ("jarvis", "tests", "scripts"):
        yield from sorted((ROOT / d).rglob("*.py"))


def check_python():
    n = 0
    for f in py_files():
        n += 1
        src = f.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src, filename=str(f), feature_version=(3, 9))
        except SyntaxError as e:
            problems.append(f"{f.relative_to(ROOT)}:{e.lineno} syntaxe : {e.msg}")
            continue
        if f.name == "__init__.py":
            continue
        imported = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    imported[(a.asname or a.name).split(".")[0]] = node.lineno
            elif isinstance(node, ast.ImportFrom) and node.module != "__future__":
                for a in node.names:
                    imported[a.asname or a.name] = node.lineno
        used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | \
               {n.value.id for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)}
        strings = " ".join(n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str))
        for name, line in imported.items():
            if name not in used and name not in strings:
                problems.append(f"{f.relative_to(ROOT)}:{line} import inutilisé : {name}")
        if "from __future__ import annotations" not in src and re.search(r"->\s*\w+\s*\|\s*\w+|:\s*\w+\s*\|\s*None", src):
            problems.append(f"{f.relative_to(ROOT)} annotation « X | Y » sans from __future__ (incompatible 3.9)")
    for mod in sorted(p for p in (ROOT / "jarvis").rglob("*.py")):
        name = ".".join(mod.relative_to(ROOT).with_suffix("").parts)
        try:
            importlib.import_module(name.replace(".__init__", ""))
        except Exception as e:  # noqa: BLE001
            problems.append(f"{name} ne s'importe pas : {e}")
    return n


JSC = """function run(argv){ ObjC.import('Foundation'); var out=[];
 for (var i=0;i<argv.length;i++){ var p=argv[i];
  var src=ObjC.unwrap($.NSString.stringWithContentsOfFileEncodingError(p,4,null));
  src=src.replace(/^import .*$/mg,'').replace(/^export /mg,'');
  try{ new Function(src); }catch(e){ out.push(p+':'+e.line+' syntaxe : '+e.message); } }
 return out.join('\\n'); }"""


def check_js():
    files = sorted((ROOT / "web" / "js").rglob("*.js"))
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as t:
        t.write(JSC)
    out = subprocess.run(["osascript", "-l", "JavaScript", t.name, *map(str, files)], capture_output=True, text=True).stdout.strip()
    Path(t.name).unlink()
    problems.extend(l.replace(str(ROOT) + "/", "") for l in out.splitlines() if l.strip())
    exports = {}
    for f in files:
        src = f.read_text(encoding="utf-8")
        exports[f.resolve()] = set(re.findall(r"^export (?:async )?(?:function|class|const|let) ([\w$]+)", src, re.M))
    for f in files:
        src = f.read_text(encoding="utf-8")
        for m in re.finditer(r'^import \{([^}]+)\} from "([^"]+)";', src, re.M):
            target = (f.parent / m.group(2)).resolve()
            body = src[m.end():]
            for name in [x.strip() for x in m.group(1).split(",") if x.strip()]:
                if not re.search(rf"(?<![\w$.]){re.escape(name)}(?![\w$])", body):
                    problems.append(f"{f.relative_to(ROOT)} import inutilisé : {name}")
                if target in exports and name not in exports[target]:
                    problems.append(f"{f.relative_to(ROOT)} importe « {name} », absent de {m.group(2)}")
    return len(files)


def check_css():
    tokens = (ROOT / "web" / "css" / "tokens.css").read_text(encoding="utf-8")
    defined = set(re.findall(r"(--[\w-]+)\s*:", tokens))
    for f in [ROOT / "web" / "css" / "app.css", ROOT / "web" / "css" / "nova.css", *sorted((ROOT / "web" / "js").rglob("*.js"))]:
        src = f.read_text(encoding="utf-8")
        defined |= set(re.findall(r"(--[\w-]+)\s*:", src))
        for v in set(re.findall(r"var\((--[\w-]+)", src)):
            if v not in defined:
                problems.append(f"{f.relative_to(ROOT)} variable CSS non définie : {v}")
        if f.suffix == ".css":
            for m in re.finditer(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b", src):
                problems.append(f"{f.relative_to(ROOT)} couleur codée en dur {m.group(0)} (utiliser un jeton de tokens.css)")


def check_secrets():
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    pats = [r"sk-ant-[A-Za-z0-9_\-]{20,}", r"\bgh[pousr]_[A-Za-z0-9]{30,}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----", r"\bAKIA[0-9A-Z]{16}\b"]
    for f in files:
        if f.startswith(("data/", "workspace/")) or f.endswith((".db", ".env")):
            problems.append(f"{f} ne doit pas être suivi par Git")
            continue
        p = ROOT / f
        if not p.is_file() or p.suffix in (".png", ".icns"):
            continue
        txt = p.read_text(encoding="utf-8", errors="replace")
        for pat in pats:
            if re.search(pat, txt) and not f.startswith(("tests/", "scripts/")):
                problems.append(f"{f} contient un secret probable ({pat})")


if __name__ == "__main__":
    npy = check_python()
    njs = check_js()
    check_css()
    check_secrets()
    if problems:
        print(f"{len(problems)} problème(s) :")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print(f"Vérification OK : {npy} fichiers Python, {njs} fichiers JavaScript, CSS et secrets contrôlés.")
