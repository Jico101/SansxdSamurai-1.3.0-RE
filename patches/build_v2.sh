#!/bin/bash
# build_v2.sh - Rebuild del classes26 parcheado (V2), swap sobre el APK V1 y re-firma
# Uso:
#   PROJECT_ROOT=/home/z/my-project ./build_v2.sh
# Requiere: re/patched/mini26/out26 (arbol apktool ya parcheado con patch_v2.py)
#           re/original/v1-cracked.apk (base V1 con los 6 parches de classes24)
#           re/tools/dl/{apktool.jar, uber-apk-signer.jar, testkey.jks}
set -e
BASE="${PROJECT_ROOT:-$PWD}"
RE="$BASE/re"
DL="$RE/tools/dl"
SRC="$RE/patched/mini26"
V1="$RE/original/v1-cracked.apk"
OUT="$BASE/download/SansxdSamurai-1.3.0-cracked-v2.apk"

echo "[1/7] Rebuild mini APK classes26 (smali -> dex)"
cd "$SRC"
java -Xmx1500m -jar "$DL/apktool.jar" b out26 -o mini26_rebuilt.apk 2>&1 | tail -3

echo "[2/7] Extraer nuevo dex"
rm -rf mini26_rebuilt && mkdir mini26_rebuilt
unzip -q -o mini26_rebuilt.apk classes.dex -d mini26_rebuilt
stat -c '%s bytes (classes.dex nuevo)' mini26_rebuilt/classes.dex

echo "[3/7] Preparar classes26.dex"
rm -rf swap26 && mkdir swap26
cp mini26_rebuilt/classes.dex swap26/classes26.dex

echo "[4/7] Copiar APK V1 -> V2"
mkdir -p "$BASE/download"
cp "$V1" "$OUT"
stat -c '%s bytes (base V1)' "$OUT"

echo "[5/7] Swap classes26.dex en el APK V2"
cd swap26
zip -q "$OUT" classes26.dex

echo "[6/7] Eliminar firma v1 vieja"
zip -q -d "$OUT" "META-INF/ANDROID.RSA" "META-INF/ANDROID.SF" "META-INF/MANIFEST.MF" || true

echo "[7/7] zipalign + firma (v1+v2+v3) con AOSP testkey"
cd "$SRC"
java -Xmx1200m -jar "$DL/uber-apk-signer.jar" -a "$OUT" \
  --ks "$DL/testkey.jks" --ksAlias androiddebugkey --ksPass android --ksKeyPass android \
  --allowResign --overwrite 2>&1 | grep -vE "^$" | tail -15

echo "--- Hashes finales ---"
sha256sum "$OUT"
stat -c '%s bytes (V2 final)' "$OUT"
echo "[+] BUILD V2 COMPLETO"
