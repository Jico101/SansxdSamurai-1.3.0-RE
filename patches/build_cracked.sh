#!/bin/bash
# build_cracked.sh - Rebuild del dex parcheado, swap en APK completo y firma con AOSP testkey
# Uso:
#   PROJECT_ROOT=/ruta/al/proyecto ./build_cracked.sh
#
# Requiere (en $PROJECT_ROOT/re/tools/dl/): apktool.jar, uber-apk-signer.jar, testkey.jks
# Requiere en $PROJECT_ROOT/re/patched/mini_out: el arbol apktool ya parcheado con patch_v1.py
# Requiere en $PROJECT_ROOT/re/original/: el APK original SansxdSamurai-1.3.0.apk
set -e
BASE="${PROJECT_ROOT:-$PWD}"
PATCHED="$BASE/re/patched"
DL="$BASE/re/tools/dl"
ORIG="$BASE/re/original/SansxdSamurai-1.3.0.apk"
OUT="$BASE/download/SansxdSamurai-1.3.0-cracked.apk"

echo "[1/8] Rebuild mini APK (smali -> dex)"
cd "$PATCHED"
java -Xmx1500m -jar "$DL/apktool.jar" b mini_out -o mini_rebuilt.apk 2>&1 | tail -3

echo "[2/8] Extraer nuevo dex"
rm -rf mini_rebuilt && mkdir mini_rebuilt
unzip -q -o mini_rebuilt.apk classes.dex -d mini_rebuilt
ls -la mini_rebuilt/classes.dex

echo "[3/8] Preparar classes24.dex"
rm -rf swap && mkdir swap
cp mini_rebuilt/classes.dex swap/classes24.dex

echo "[4/8] Copiar APK original -> cracked"
cp "$ORIG" "$OUT"
ls -la "$OUT"

echo "[5/8] Swap classes24.dex en el APK"
cd swap
zip -q "$OUT" classes24.dex

echo "[6/8] Eliminar firma v1 vieja"
zip -q -d "$OUT" "META-INF/ANDROID.RSA" "META-INF/ANDROID.SF" "META-INF/MANIFEST.MF" || true

echo "[7/8] zipalign + firma (v1+v2+v3) con AOSP testkey"
cd "$PATCHED"
java -Xmx1200m -jar "$DL/uber-apk-signer.jar" -a "$OUT" \
  --ks "$DL/testkey.jks" --ksAlias androiddebugkey --ksPass android --ksKeyPass android \
  --allowResign --overwrite 2>&1 | grep -vE "^$" | tail -15

echo "[8/8] Hashes finales"
sha256sum "$OUT"
ls -la "$OUT"
echo "[+] BUILD COMPLETO"
