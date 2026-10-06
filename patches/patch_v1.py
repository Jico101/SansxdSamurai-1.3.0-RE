#!/usr/bin/env python3
"""patch_v1.py - Parcheo quirurgico V1 del mod SansxdSamurai (classes24.dex)

Uso:
    python3 patch_v1.py <ruta_al_directorio_smali_de_vengine>

<ruta> debe apuntar al directorio smali del paquete com.samurai.vengine dentro
del arbol que deja apktool, por ejemplo:  smali/com/samurai/vengine

Parches:
  PwfNative.smali:
    1. isSignedIn()Z                  -> siempre true
    2. isLicenseExpired()Z            -> siempre false
    3. expiryEpochMillis()J           -> siempre 0 (muestra "Lifetime")
    4. onSessionEnded(String,String)V -> no-op (nunca desmonta el menu)
  ModMenuState.smali:
    5. isLoggedIn()Z                   -> siempre true (mata todas las ramas del LoginScreen)
    6. getAuthenticated()Z             -> siempre true
"""
import sys

PATCHES = [
    {
        'file': 'utils/PwfNative.smali',
        'method': 'isSignedIn()Z',
        'body': [
            '    .locals 1',
            '',
            '    const/4 v0, 0x1',
            '',
            '    return v0',
        ],
    },
    {
        'file': 'utils/PwfNative.smali',
        'method': 'isLicenseExpired()Z',
        'body': [
            '    .locals 1',
            '',
            '    const/4 v0, 0x0',
            '',
            '    return v0',
        ],
    },
    {
        'file': 'utils/PwfNative.smali',
        'method': 'expiryEpochMillis()J',
        'body': [
            '    .locals 2',
            '',
            '    const-wide/16 v0, 0x0',
            '',
            '    return-wide v0',
        ],
    },
    {
        'file': 'utils/PwfNative.smali',
        'method': 'onSessionEnded(Ljava/lang/String;Ljava/lang/String;)V',
        'body': [
            '    .locals 0',
            '',
            '    return-void',
        ],
    },
    {
        'file': 'screens/modmenu/ModMenuState.smali',
        'method': 'isLoggedIn()Z',
        'body': [
            '    .locals 1',
            '',
            '    const/4 v0, 0x1',
            '',
            '    return v0',
        ],
    },
    {
        'file': 'screens/modmenu/ModMenuState.smali',
        'method': 'getAuthenticated()Z',
        'body': [
            '    .locals 1',
            '',
            '    const/4 v0, 0x1',
            '',
            '    return v0',
        ],
    },
]


def patch_method(path: str, method_sig: str, new_body: list) -> bool:
    with open(path) as f:
        lines = f.readlines()

    start = None
    for i, ln in enumerate(lines):
        if ln.startswith('.method') and method_sig in ln:
            start = i
            break
    if start is None:
        print(f'[FAIL] No encontre {method_sig} en {path}')
        return False

    end = None
    for j in range(start + 1, len(lines)):
        if lines[j].strip() == '.end method':
            end = j
            break
    if end is None:
        print(f'[FAIL] No encontre .end method para {method_sig}')
        return False

    old_body = lines[start + 1:end]
    new_lines = lines[:start + 1] + [b + '\n' for b in new_body] + ['\n'] + lines[end:]
    with open(path, 'w') as f:
        f.writelines(new_lines)

    print(f'[OK] {path.split("/")[-1]} :: {method_sig} '
          f'(cuerpo viejo {len(old_body)} lineas -> {len(new_body)})')
    return True


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    base = sys.argv[1].rstrip('/')
    ok = 0
    for p in PATCHES:
        if patch_method(f'{base}/{p["file"]}', p['method'], p['body']):
            ok += 1
    print(f'\n[{ok}/{len(PATCHES)}] parches aplicados')
    return 0 if ok == len(PATCHES) else 1


if __name__ == '__main__':
    sys.exit(main())
