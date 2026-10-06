#!/bin/bash
# extract_mod_dex.sh - Extrae los dex tocados por el modder y los descompila con jadx
# Uso:
#   PROJECT_ROOT=/ruta/al/proyecto JADX=/ruta/a/jadx ./extract_mod_dex.sh
#   (si JADX no se define, se usa "jadx" del PATH)
set -u
ROOT="${PROJECT_ROOT:-$PWD}"
ORIG="$ROOT/re/original"
JADX="${JADX:-jadx}"
mkdir -p "$ORIG/dex_mod"

echo "[*] Extrayendo dex del modder..."
cd "$ORIG"
unzip -o -q SansxdSamurai-1.3.0.apk \
  "classes3.dex" "classes12.dex" "classes14.dex" "classes21.dex" \
  "classes22.dex" "classes23.dex" "classes24.dex" "classes25.dex" "classes26.dex" \
  -d dex_mod 2>/dev/null
ls -la dex_mod/

# Los del 5-oct (seguro del mod) primero, luego 30-sep, luego classes3
for d in 22 23 24 25 26 21 14 12 3; do
  if [ -f "dex_mod/classes$d.dex" ]; then
    echo "[*] jadx classes$d.dex ..."
    timeout 400 $JADX --no-res -j 2 --no-debug-info -d "jadx_$d" "dex_mod/classes$d.dex" > "jadx_$d.log" 2>&1 || true
    N=$(find "jadx_$d" -name '*.java' 2>/dev/null | wc -l)
    P=$(find "jadx_$d" -name '*.java' 2>/dev/null | sed 's|.*/sources/||' | cut -d/ -f1-2 | sort -u | head -8 | tr '\n' ' ')
    echo "    classes$d -> $N archivos java | paquetes: $P"
  fi
done
echo "[+] EXTRACCION/DECOMPILACION COMPLETA"
