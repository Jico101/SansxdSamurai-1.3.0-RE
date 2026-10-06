#!/usr/bin/env python3
"""verify_v2.py - Verificacion integral de un APK parcheado contra su base:
- unica entrada modificada (fuera de META-INF) = la esperada
- dex de los parches previos byte-identico
- 26 dex presentes, origin.apk y librerias nativas intactas

Uso:
    python3 verify_v2.py <apk_base> <apk_parcheado>
"""
import hashlib
import sys
import zipfile

EXPECTED_DIFF = {"classes26.dex"}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    z1 = zipfile.ZipFile(sys.argv[1])
    z2 = zipfile.ZipFile(sys.argv[2])

    n1 = {i.filename for i in z1.infolist()}
    n2 = {i.filename for i in z2.infolist()}
    print(f"[i] entradas: base={len(n1)}  parcheado={len(n2)}")
    only1 = sorted(n1 - n2)
    only2 = sorted(n2 - n1)
    print(f"[i] solo en base: {only1}")
    print(f"[i] solo en parcheado: {only2}")

    diffs, same = [], 0
    for name in sorted(n1 & n2):
        if name.startswith("META-INF/"):
            continue
        if sha(z1.read(name)) != sha(z2.read(name)):
            diffs.append(name)
        else:
            same += 1
    print(f"[i] entradas identicas fuera de META-INF: {same}")
    print(f"[i] entradas DISTINTAS fuera de META-INF: {diffs}")

    c24 = sha(z1.read("classes24.dex")) == sha(z2.read("classes24.dex"))
    print(f"[{'OK' if c24 else 'FAIL'}] classes24.dex (parches V1) byte-identico")

    dexes = [n for n in n2 if n.startswith("classes") and n.endswith(".dex")]
    print(f"[{'OK' if len(dexes) == 26 else 'FAIL'}] dex count: {len(dexes)}")

    for k in ("assets/SignatureKiller/origin.apk", "lib/arm64-v8a/libsamurai.so",
              "lib/arm64-v8a/libSignatureKiller.so"):
        a, b = sha(z1.read(k)), sha(z2.read(k))
        print(f"[{'OK' if a == b else 'FAIL'}] {k} intacto: {a[:16]}...")

    ok = (set(diffs) == EXPECTED_DIFF and not only2
          and all(x.startswith("META-INF/") for x in only1) and c24 and len(dexes) == 26)
    print(f"\n[{'VERIFICACION COMPLETA OK' if ok else 'HAY DESVIOS'}] resultado final")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
