#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stringfog_decrypt.py — Descifra llamadas StringFog.decrypt(byte[], byte[]) del
mod SansxdSamurai (com.samurai.vengine) en fuentes jadx.

Algoritmo (verificado contra StringFogImpl.java, jadx_24):
    xor(data, key):
        for i in range(len(data)):
            data[i] ^= key[i % len(key)]   # índice de clave cíclico
    resultado = new String(data, UTF-8)

jadx emite los bytes Java con signo (-128..127) -> se convierten con b & 0xFF.

Uso:
    python3 stringfog_decrypt.py [raiz_jadx_sources] [archivo_salida]

Por defecto: raiz = re/original/jadx_24/sources, salida = re/analysis/stringfog_strings.txt
"""
import os
import re
import sys

# StringFog.decrypt(new byte[]{...}, new byte[]{...})
CALL_RE = re.compile(
    r'StringFog\.decrypt\(\s*new byte\[\]\s*\{([^}]*)\}\s*,\s*new byte\[\]\s*\{([^}]*)\}\s*\)'
)
BYTES_RE = re.compile(r'-?\d+')


def parse_byte_array(s: str) -> bytes:
    """Convierte '8, 94, 1, -66' (bytes Java con signo) a bytes sin signo."""
    vals = [int(x) for x in BYTES_RE.findall(s)]
    return bytes(v & 0xFF for v in vals)


def xor_decrypt(data: bytes, key: bytes) -> bytes:
    if not key:
        return data
    return bytes(d ^ key[i % len(key)] for i, d in enumerate(data))


def decrypt_call(data_arr: str, key_arr: str) -> str:
    data = parse_byte_array(data_arr)
    key = parse_byte_array(key_arr)
    plain = xor_decrypt(data, key)
    try:
        return plain.decode('utf-8')
    except UnicodeDecodeError:
        return repr(plain)


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else 're/original/jadx_24/sources'
    out_path = sys.argv[2] if len(sys.argv) > 2 else 're/analysis/stringfog_strings.txt'
    # Solo com/samurai por defecto (el paquete del mod)
    base = os.path.join(root, 'com', 'samurai')
    if not os.path.isdir(base):
        base = root

    results = []  # (relpath, lineno, plaintext)
    n_files = 0
    for dirpath, _dirs, files in os.walk(base):
        for fn in sorted(files):
            if not fn.endswith('.java'):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, root)
            try:
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    text = f.read()
            except OSError:
                continue
            if 'StringFog.decrypt' not in text:
                continue
            n_files += 1
            for m in CALL_RE.finditer(text):
                plain = decrypt_call(m.group(1), m.group(2))
                line = text.count('\n', 0, m.start()) + 1
                results.append((rel, line, plain))

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('# StringFog strings descifradas — SansxdSamurai-1.3.0 (com.samurai.*)\n')
        f.write('# Algoritmo: XOR cíclico data[i] ^ key[i %% len(key)], resultado UTF-8\n')
        f.write('# (StringFogImpl.java verificado en jadx_24/sources/com/github/megatronking/stringfog/xor/)\n')
        f.write(f'# Archivos con llamadas: {n_files} | Strings descifradas: {len(results)}\n\n')
        cur = None
        for rel, line, plain in results:
            if rel != cur:
                cur = rel
                f.write(f'=== {rel} ===\n')
            f.write(f'  L{line}: {plain}\n')
        f.write('\n')

    print(f'[+] {len(results)} strings descifradas de {n_files} archivos -> {out_path}')


if __name__ == '__main__':
    main()
