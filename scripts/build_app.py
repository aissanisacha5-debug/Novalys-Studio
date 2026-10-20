#!/usr/bin/env python3
"""Construction reproductible de l'application macOS Nova :

  dist/Nova.app          application native (Swift + WebKit) contenant le service Python et l'interface
  dist/Nova-<v>.dmg      image disque d'installation (glisser Nova dans Applications)

Étapes : compilation Swift (choix automatique d'un SDK compatible avec le compilateur), assemblage du
paquet (.app), icône, Info.plist (micro, reconnaissance vocale, réseau local), signature ad hoc (pas de
certificat Apple Developer : Gatekeeper peut demander « Ouvrir » au premier lancement), image .dmg, vérifications.
"""
from __future__ import annotations

import hashlib
import json
import plistlib
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from jarvis import VERSION  # noqa: E402

DIST = ROOT / "dist"
BUILD = ROOT / "build"
APP = DIST / "Nova.app"
SDK_DIR = Path("/Library/Developer/CommandLineTools/SDKs")
FRAMEWORKS = ["Cocoa", "WebKit", "Speech", "AVFoundation"]


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    return r.returncode, (r.stdout + r.stderr)


def compile_swift(out: Path) -> str:
    sdks = [None] + sorted((p for p in SDK_DIR.glob("MacOSX*.sdk") if p.name != "MacOSX.sdk"), reverse=True) if SDK_DIR.exists() else [None]
    last = ""
    for sdk in sdks:
        cmd = ["swiftc", "-O", "-target", "arm64-apple-macos13.0", "-o", str(out), str(ROOT / "macos" / "main.swift")]
        if sdk:
            cmd[1:1] = ["-sdk", str(sdk)]
        for fw in FRAMEWORKS:
            cmd += ["-framework", fw]
        code, log = run(cmd)
        if code == 0:
            return sdk.name if sdk else "SDK par défaut"
        last = log[-1500:]
    raise SystemExit("Compilation Swift impossible avec les SDK disponibles :\n" + last)


def make_icns(dest: Path) -> None:
    src = ROOT / "web" / "icone-1024.png"
    with tempfile.TemporaryDirectory() as td:
        iconset = Path(td) / "Nova.iconset"
        iconset.mkdir()
        for s in (16, 32, 128, 256, 512):
            for scale, suffix in ((1, ""), (2, "@2x")):
                run(["sips", "-z", str(s * scale), str(s * scale), str(src), "--out", str(iconset / f"icon_{s}x{s}{suffix}.png")])
        code, log = run(["iconutil", "-c", "icns", str(iconset), "-o", str(dest)])
        if code:
            raise SystemExit("Icône : " + log)


def copy_code(dest: Path) -> int:
    n = 0
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")
    dest.mkdir(parents=True)
    shutil.copy2(ROOT / "jarvis.py", dest / "jarvis.py")
    for d in ("jarvis", "web"):
        shutil.copytree(ROOT / d, dest / d, ignore=ignore)
    (dest / "scripts").mkdir()
    shutil.copy2(ROOT / "scripts" / "verifier-secrets.py", dest / "scripts" / "verifier-secrets.py")
    for f in dest.rglob("*"):
        n += f.is_file()
    return n


def info_plist() -> dict:
    return {
        "CFBundleName": "Nova", "CFBundleDisplayName": "Nova", "CFBundleIdentifier": "studio.novalys.jarvis",  # identifiant conservé : données, micro et trousseau existants
        "CFBundleExecutable": "Nova", "CFBundleIconFile": "Nova", "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": VERSION, "CFBundleVersion": time.strftime("%Y%m%d%H%M"),
        "LSMinimumSystemVersion": "13.0", "LSApplicationCategoryType": "public.app-category.productivity",
        "NSHighResolutionCapable": True, "NSPrincipalClass": "NSApplication",
        "NSHumanReadableCopyright": "Novalys Studio — assistant personnel Nova",
        "NSMicrophoneUsageDescription": "Nova utilise le micro uniquement quand vous activez la dictée, pour transcrire votre demande.",
        "NSSpeechRecognitionUsageDescription": "Nova transcrit votre voix en texte (sur l'appareil quand c'est possible) ; aucun audio n'est conservé.",
        "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
    }


def build_app() -> dict:
    if APP.exists():
        shutil.rmtree(APP)
    (APP / "Contents" / "MacOS").mkdir(parents=True)
    (APP / "Contents" / "Resources").mkdir()
    BUILD.mkdir(exist_ok=True)
    sdk = compile_swift(APP / "Contents" / "MacOS" / "Nova")
    with open(APP / "Contents" / "Info.plist", "wb") as f:
        plistlib.dump(info_plist(), f)
    (APP / "Contents" / "PkgInfo").write_text("APPL????")
    make_icns(APP / "Contents" / "Resources" / "Nova.icns")
    files = copy_code(APP / "Contents" / "Resources" / "app")
    code, log = run(["codesign", "--force", "--deep", "--sign", "-", str(APP)])
    if code:
        raise SystemExit("Signature ad hoc impossible : " + log)
    code, log = run(["codesign", "--verify", "--deep", "--strict", str(APP)])
    if code:
        raise SystemExit("Vérification de signature échouée : " + log)
    return {"sdk": sdk, "files": files}


def build_dmg() -> Path:
    dmg = DIST / f"Nova-{VERSION}.dmg"
    if dmg.exists():
        dmg.unlink()
    with tempfile.TemporaryDirectory() as td:
        stage = Path(td) / "Nova"
        stage.mkdir()
        shutil.copytree(APP, stage / "Nova.app", symlinks=True)
        (stage / "Applications").symlink_to("/Applications")
        (stage / "LISEZMOI.txt").write_text(
            f"Nova {VERSION}\n\nInstallation : glisser Nova dans le dossier Applications (ou ~/Applications), puis l'ouvrir.\n"
            "Premier lancement : application signée ad hoc (sans certificat Apple Developer). Si macOS refuse de l'ouvrir :\n"
            "clic droit sur Nova > Ouvrir > Ouvrir, ou Réglages Système > Confidentialité et sécurité > Ouvrir quand même.\n"
            "Prérequis : macOS 13+, Python 3 d'Apple (/usr/bin/python3, outils en ligne de commande). Fournisseur IA à choisir dans Modèles IA.\n",
            encoding="utf-8")
        code, log = run(["hdiutil", "create", "-volname", f"Nova {VERSION}", "-srcfolder", str(stage), "-ov", "-format", "UDZO", str(dmg)])
        if code:
            raise SystemExit("Création du .dmg impossible : " + log)
    code, log = run(["hdiutil", "verify", str(dmg)])
    if code:
        raise SystemExit("Vérification du .dmg échouée : " + log)
    return dmg


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


if __name__ == "__main__":
    DIST.mkdir(exist_ok=True)
    t0 = time.time()
    info = build_app()
    dmg = build_dmg()
    report = {"version": VERSION, "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "app": str(APP), "dmg": str(dmg),
              "dmg_sha256": sha256(dmg), "dmg_bytes": dmg.stat().st_size, "swift_sdk": info["sdk"], "app_files": info["files"],
              "signature": "ad hoc (pas de certificat Apple Developer, pas de notarisation)", "seconds": round(time.time() - t0, 1)}
    (DIST / "BUILD-INFO.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
