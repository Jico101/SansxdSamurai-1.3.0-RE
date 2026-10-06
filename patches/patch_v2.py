#!/usr/bin/env python3
"""patch_v2.py - Parche V2: bypass del gate de arranque del reseller "Sandsxd Modz"
(com.aryanispe.login.MainActivity, classes26.dex)

Uso:
    python3 patch_v2.py <ruta_al_directorio_smali_raiz_de_classes26>

El directorio debe contener com/aryanispe/login/MainActivity.smali
(ej.: out26/smali).

Parches:
  MainActivity.smali:
    1. Start(Landroid/content/Context;)V  -> no-op total: el dialogo de licencia
       del reseller nunca se construye ni se muestra (todo el builder del
       AlertDialog, el EditText de key y el CheckBox viven dentro de Start).
    2. onCreate(Landroid/os/Bundle;)V     -> solo super.onCreate + return
       (seguro extra: la actividad no esta en el manifest, es codigo muerto)

Las inner classes AIDE (MainActivity$100000xxx, classes25) solo son referenciadas
por el dialogo que construia Start(): quedan muertas sin invocador.
"""
import sys

START_BODY = [
    '.method public static Start(Landroid/content/Context;)V',
    '    .locals 0',
    '',
    '    return-void',
]

ONCREATE_BODY = [
    '.method protected onCreate(Landroid/os/Bundle;)V',
    '    .locals 2',
    '',
    '    invoke-super {p0, p1}, Landroid/app/Activity;->onCreate(Landroid/os/Bundle;)V',
    '',
    '    return-void',
]


def replace_method_body(lines, method_sig, new_body):
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith('.method') and method_sig in ln:
            start = i
            break
    if start is None:
        return None, f'No encontre {method_sig}'
    end = None
    for j in range(start + 1, len(lines)):
        if lines[j].strip() == '.end method':
            end = j
            break
    if end is None:
        return None, f'No encontre .end method para {method_sig}'
    new_lines = lines[:start] + [ln + '\n' for ln in new_body] + lines[end:]
    return new_lines, f'{method_sig}: cuerpo de {end - start - 1} lineas -> {len(new_body) - 2}'


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    path = sys.argv[1].rstrip('/') + '/com/aryanispe/login/MainActivity.smali'
    with open(path) as f:
        lines = f.readlines()
    total_old = len(lines)

    lines, msg = replace_method_body(lines, 'Start(Landroid/content/Context;)V', START_BODY)
    if lines is None:
        print('[FAIL]', msg)
        return 1
    print('[OK]', msg)

    lines, msg = replace_method_body(lines, 'onCreate(Landroid/os/Bundle;)V', ONCREATE_BODY)
    if lines is None:
        print('[FAIL]', msg)
        return 1
    print('[OK]', msg)

    with open(path, 'w') as f:
        f.writelines(lines)
    print(f'\n[OK] {path}: {total_old} -> {len(lines)} lineas')
    return 0


if __name__ == '__main__':
    sys.exit(main())
