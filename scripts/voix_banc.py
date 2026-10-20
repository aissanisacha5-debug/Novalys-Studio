#!/usr/bin/env python3
"""Banc d'essai des voix françaises du Mac pour Nova (stdlib seule, Python 3.9+, macOS).

Pour chaque voix française installée (`say -v ?`) et plusieurs débits, synthétise la même phrase, mesure le profil
acoustique (hauteur médiane F0, étendue, intonation, débit en syllabes/s) et classe les voix selon leur distance au
profil de la voix de la vidéo de référence (mesuré sur l'audio de la vidéo, voir docs/NOVA.md).

    python3 scripts/voix_banc.py                 # classement + extraits WAV dans ~/JARVIS/voix-banc/
    python3 scripts/voix_banc.py --profil f.wav  # profil d'un fichier WAV (mono 16 bits)

Rien n'est envoyé sur Internet, aucune voix n'est clonée : seules les voix de synthèse du Mac sont comparées.
La mesure ne remplace pas l'écoute : le classement sert à présélectionner, Sacha choisit à l'oreille.
"""
from __future__ import annotations

import argparse
import array
import json
import math
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path
from typing import Dict, List

# Profil mesuré sur la vidéo de référence (93 s, voix masculine, musique de fond) : voir docs/NOVA.md § 5.
REFERENCE = {"f0_mediane": 140, "f0_p10": 106, "f0_p90": 208, "intonation_demi_tons": 4.4, "syllabes_s": 5.0}
PHRASE = ("Bonjour Sacha. Hier, tu as eu trois rendez-vous. Sonia est la plus chaude : elle veut centraliser ses "
          "communications. Je t'ai préparé la proposition, tu veux que je l'envoie ?")
RATES = (175, 190, 205, 220)
SR = 8000


def read_wav(path: Path) -> List[float]:
    with wave.open(str(path)) as w:
        if w.getsampwidth() != 2:
            raise SystemExit(f"{path} : WAV 16 bits attendu")
        data = array.array("h", w.readframes(w.getnframes()))
        if sys.byteorder == "big":
            data.byteswap()
        ch = w.getnchannels()
        sr = w.getframerate()
    x = [v / 32768 for v in data[::ch]]
    if sr != SR:  # rééchantillonnage simple par décimation (suffisant pour la F0 de la voix parlée)
        step = sr / SR
        x = [x[int(i * step)] for i in range(int(len(x) / step))]
    return x


def percentile(v: List[float], p: float) -> float:
    s = sorted(v)
    return s[min(len(s) - 1, max(0, int(round(p / 100 * (len(s) - 1)))))]


def profile(x: List[float]) -> Dict[str, float]:
    hop, win = SR // 100, SR // 25
    lo, hi = SR // 260, SR // 70
    hann = [0.5 - 0.5 * math.cos(2 * math.pi * i / (win - 1)) for i in range(win)]
    f0, en = [], []
    for start in range(0, len(x) - win - hi, hop):
        f = [x[start + i] * hann[i] for i in range(win)]
        e = math.sqrt(sum(v * v for v in f) / win)
        en.append(e)
        if e < 0.008:
            f0.append(0.0)
            continue
        e0 = sum(v * v for v in f) + 1e-9
        best, bk = -1.0, lo
        for k in range(lo, hi):
            c = sum(f[i] * f[i + k] for i in range(win - k)) / e0
            if c > best:
                best, bk = c, k
        f0.append(SR / bk if best > 0.5 else 0.0)
    voiced = [v for v in f0 if v > 0]
    if len(voiced) < 20:
        raise ValueError("trop peu de parole voisée pour mesurer")
    med = percentile(voiced, 50)
    st = [12 * math.log2(v / med) for v in voiced]
    mean = sum(st) / len(st)
    env = [sum(en[max(0, i - 2):i + 3]) / len(en[max(0, i - 2):i + 3]) for i in range(len(en))]
    thr, talk = percentile(env, 40), percentile(env, 25)
    peaks: List[int] = []
    for i in range(1, len(env) - 1):
        if env[i] > env[i - 1] and env[i] >= env[i + 1] and env[i] > thr and (not peaks or i - peaks[-1] >= 12):
            peaks.append(i)
    speech_s = max(sum(1 for v in env if v > talk) / 100, 1e-3)
    return {"f0_mediane": round(med), "f0_p10": round(percentile(voiced, 10)), "f0_p90": round(percentile(voiced, 90)),
            "intonation_demi_tons": round(math.sqrt(sum((s - mean) ** 2 for s in st) / len(st)), 1),
            "syllabes_s": round(len(peaks) / speech_s, 1)}


def distance(p: Dict[str, float], ref: Dict[str, float] = REFERENCE) -> float:
    """Écart pondéré : hauteur (demi-tons) d'abord, puis débit, puis expressivité."""
    pitch = abs(12 * math.log2(p["f0_mediane"] / ref["f0_mediane"])) / 2
    rate = abs(p["syllabes_s"] - ref["syllabes_s"]) / 0.5
    tone = abs(p["intonation_demi_tons"] - ref["intonation_demi_tons"]) / 1.5
    return round(pitch + rate + tone, 2)


def french_voices() -> List[str]:
    out = subprocess.run(["say", "-v", "?"], capture_output=True, timeout=20).stdout.decode("utf-8", "replace")
    names = []
    for line in out.splitlines():
        m = re.match(r"^(.+?)\s{2,}(fr_[A-Z]{2})\s+#", line)
        if m:
            names.append(m.group(1).strip())
    return names


def render(voice: str, rate: int, dest: Path) -> Path:
    aiff = dest.with_suffix(".aiff")
    subprocess.run(["say", "-v", voice, "-r", str(rate), "-o", str(aiff), PHRASE], check=True, timeout=120)
    subprocess.run(["afconvert", "-f", "WAVE", "-d", f"LEI16@{SR}", "-c", "1", str(aiff), str(dest)], check=True, timeout=60)
    aiff.unlink()
    return dest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profil", nargs="*", help="profil de fichiers WAV au lieu du banc")
    ap.add_argument("--sortie", default=str(Path.home() / "JARVIS" / "voix-banc"))
    a = ap.parse_args()
    if a.profil:
        for f in a.profil:
            print(f, json.dumps(profile(read_wav(Path(f))), ensure_ascii=False))
        return
    if not (shutil.which("say") and shutil.which("afconvert")):
        raise SystemExit("say/afconvert introuvables : ce banc fonctionne sur macOS.")
    out = Path(a.sortie)
    out.mkdir(parents=True, exist_ok=True)
    voices = french_voices()
    print("Voix françaises installées :", ", ".join(voices) or "aucune")
    rows = []
    for v in voices:
        for r in RATES:
            f = out / f"{re.sub(r'[^A-Za-z0-9]+', '-', v).strip('-')}-{r}.wav"
            try:
                p = profile(read_wav(render(v, r, f)))
            except Exception as e:  # noqa: BLE001
                print(f"  {v} {r} : échec ({e})")
                continue
            rows.append({"voix": v, "debit": r, **p, "distance": distance(p), "fichier": str(f)})
            print(f"  {v:28s} {r} mots/min  F0 {p['f0_mediane']:3d} Hz  intonation {p['intonation_demi_tons']} dt  "
                  f"{p['syllabes_s']} syll/s  → distance {rows[-1]['distance']}")
    rows.sort(key=lambda x: x["distance"])
    (out / "classement.json").write_text(json.dumps({"reference": REFERENCE, "phrase": PHRASE, "resultats": rows},
                                                    ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nRéférence :", REFERENCE)
    print("Les plus proches :")
    for x in rows[:5]:
        print(f"  {x['voix']} à {x['debit']} mots/min (distance {x['distance']}) : {x['fichier']}")


if __name__ == "__main__":
    main()
