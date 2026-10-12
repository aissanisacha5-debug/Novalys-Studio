#!/usr/bin/env python3
"""Crochet pre-commit : bloque un commit qui contient un secret probable (clé API, jeton, clé privée)."""
import re
import subprocess
import sys

PATTERNS = [r"sk-ant-[A-Za-z0-9_\-]{20,}", r"\bsk-[A-Za-z0-9]{32,}", r"\bgh[pousr]_[A-Za-z0-9]{30,}", r"\bAKIA[0-9A-Z]{16}\b",
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----", r"xox[abprs]-[A-Za-z0-9\-]{20,}"]
files = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"], capture_output=True, text=True).stdout.split()
bad = []
for f in files:
    if f.startswith("data/") or f.endswith(".env"):
        bad.append((f, "fichier interdit dans Git"))
        continue
    try:
        txt = subprocess.run(["git", "show", f":{f}"], capture_output=True, text=True, errors="replace").stdout
    except Exception:
        continue
    for p in PATTERNS:
        if re.search(p, txt) and "tests/" not in f:
            bad.append((f, p))
if bad:
    print("Commit bloqué : secret probable détecté.")
    for f, p in bad:
        print(f"  {f} ({p})")
    sys.exit(1)
