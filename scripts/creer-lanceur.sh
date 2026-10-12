#!/bin/zsh
# Crée ~/Applications/JARVIS.app : un double-clic démarre JARVIS (si besoin) et ouvre sa fenêtre.
# Ne configure AUCUN lancement automatique au démarrage du Mac.
set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP="$HOME/Applications/JARVIS.app"
mkdir -p "$HOME/Applications"
TMP="$(mktemp -d)/jarvis.applescript"
cat > "$TMP" <<AS
try
	do shell script "cd " & quoted form of "$DIR" & " && /usr/bin/python3 jarvis.py start > /dev/null 2>&1 &"
on error errMsg
	display dialog "JARVIS n'a pas pu démarrer : " & errMsg buttons {"OK"} default button 1 with icon caution
end try
AS
osacompile -o "$APP" "$TMP"
# Icône : noyau émeraude (générée depuis web/icone-1024.png si présent)
if [ -f "$DIR/web/icone-1024.png" ]; then
  ICONSET="$(mktemp -d)/jarvis.iconset"; mkdir -p "$ICONSET"
  for s in 16 32 128 256 512; do
    sips -z $s $s "$DIR/web/icone-1024.png" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
    sips -z $((s*2)) $((s*2)) "$DIR/web/icone-1024.png" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
  done
  iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/applet.icns"
fi
touch "$APP"
echo "Lanceur créé : $APP"
