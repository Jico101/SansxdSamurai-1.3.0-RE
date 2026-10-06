# SansxdSamurai 1.3.0 — Ingeniería inversa (8 Ball Pool)

Análisis completo del mod de pago SansxdSamurai 1.3.0 para 8 Ball Pool, crack de su
sistema de licencias y APK re-empaquetado con la licencia parcheada y firmado.

| | |
|---|---|
| Objetivo | SansxdSamurai-1.3.0.apk (300 MB, 26 dex) |
| Juego base | 8 Ball Pool 56.31.0 (versionCode 4035) — `com.miniclip.eightballpool` |
| SHA-256 original | `d4ae5278dc4b6aa5d8567534faef8d45b5e6b5031d898b18861589538c7513bf` |
| APK parcheado | release **v1.3.0-cracked** — SHA-256 `de689c4c0bd317387a4c2ff3d195da8ca2a37f2e48cdb0b37619bf7d783b77aa` |

## Qué incluye el mod

- **Menú flotante Jetpack Compose** (`com.samurai.vengine`) montado sobre las activities
  del juego (ComposeView sobre `android.R.id.content`), visible ~2 s después de lanzar.
  5 tabs: Visuals / Combat / Queue / Misc / Settings.
- **Motor de cheats nativo** `libsamurai.so` (10,4 MB, ELF64 AArch64, ImGui + xHook +
  MSHook/And64Hook, OpenSSL estático, compilado en dispositivo con AIDE — autor del
  core: "xHuntx", repo `hunttly/bdk`):
  - ESP de predicción: líneas de trayectoria, posiciones, troneras y shot-state
    (grosor/alpha/tamaño configurables)
  - Auto-play (Human / Fast / Hacker), 9-ball (Normal / Target 9), golden shot,
    random spin, cushion shot
  - Auto-queue (8/9 ball, mesas M1-M17, stop at coin limit)
  - Block ads
  - Cosméticos: 13 trails, 7 ball-impact FX, 7 cushion FX, 4 pocket FX, skins de
    taco/mesa descargables del CDN oficial de Miniclip
- **Reemplazo del Google Sign-In**: intercepta Credential Manager y ejecuta OAuth
  propio en WebView embebido con el client_id real de Miniclip (validación de
  JWT aud/nonce/issuer y reinyección de la credential).
- **Telemetría propia del modder**: banners, versiones y catálogos desde
  `raw.githubusercontent.com/hunttly/bdk` (resller.json / gamever.json / banners.json).

## Cómo funciona su verificación de firma

No verifica la firma: **la falsea**.

- `bin.mt.signature.KillerApplication` (classes21) + `libSignatureKiller.so`
  (MT Manager SignatureKiller, xHook 1.2.0) registran hooks GOT de
  `open/open64/openat/openat64` en todas las librerías cargadas del proceso.
- Toda lectura del propio APK se redirige a `assets/SignatureKiller/origin.apk`
  (el 8 Ball Pool original de Miniclip, 146 MB): cualquier check de firma del juego
  ve el certificado original de Miniclip aunque el APK esté re-firmado.
- El propio mod está firmado con la **AOSP testkey pública** (CN=Android, O=Android,
  sha1RSA de 2008). Re-firmar con esa misma testkey conserva el certificado exacto
  y todo el spoofing por rutas sigue operativo.

## Protecciones que incluye

- **StringFog** (XOR cíclico con clave + Base64, `com.github.megatronking.stringfog`)
  sobre todas las strings del mod: 3.151 strings descifradas en
  `analysis/stringfog_strings.txt`.
- **Ofuscación total de la capa JNI**: símbolos nativos sin sentido
  (`orljmgpg`, `vqesunkz`, `mbdcouus`, ...) mapeados vía tablas `JNINativeMethod`
  reconstruidas desde `.rela.dyn`/`.data.rel.ro`.
- **Ofuscación de nombres Java** (`w4AdI4`, `qwerty.asdfgh`): restos R8 de ad SDKs,
  no es protección real.
- `libgpdeku.so` / `libpglarmor.so`: anti-cheat del juego base, neutralizado por los
  hooks GOT del motor.
- `org.lsposed.hiddenapibypass`: ocultamiento de la hidden API de Android.
- **Cero anti-tamper real**: sin ptrace, sin anti-Frida, sin detección de
  root/emulador, sin hashes de dex. Re-empaquetar y re-firmar no es detectado.

## Sistema de licencias

Flujo original (Java → nativo):

1. `com.aryanispe.login` (login AIDE) → `LicenseAuth.verify()` valida la clave
   guardada en prefs (`samurai_license/license_key`), cifrada AES/GCM con
   AndroidKeyStore (alias `samurai_license_key_v1`).
2. `PwfNative.login(key)` → JNI `orljmgpg()` en `libsamurai.so`.
3. Validación real (muerta en este build): HTTPS + HMAC-SHA256(appSecret) + AES-GCM
   contra `raw.githubusercontent.com/hunttly/bdk`, respuesta JSON
   `{session_id, license_key, expires_at, seller, hwid, enabled}`, persistencia en
   `persistence.json` y heartbeat con callback `onSessionEnded(String,String)`.
4. Gates de UI: `LoginScreen` si `!isLoggedIn`; polling cada 5 s de
   `isSignedIn() && !isLicenseExpired()` (JNI `vqesunkz`/`mbdcouus`); countdown de
   expiración; `onSessionEnded` → logout forzado.

Hallazgo clave: en 1.3.0 `libsamurai.so` ya es un **build de test con la licencia
craqueada** — `isSignedIn` es un stub `mov w0,#1; ret` (file offset 0x638c3c),
`isLicenseExpired` es `mov w0,#0; ret` (0x63ba40), `login` devuelve
`{"success":true,"message":"PWF Auth crypto test"}` constante sin red, y la
expiración es local (`setPermanentExpiry` escribe `valid=1/expiry=INT64_MAX`).
El único gate realmente vivo es la capa Java (`ModMenuState`), y es lo que se parchea.

## Parche aplicado (classes24.dex — 6 puntos)

| # | Clase / método | Parche |
|---|---|---|
| 1 | `PwfNative.isSignedIn()Z` | `const/4 v0, 1` + `return v0` |
| 2 | `PwfNative.isLicenseExpired()Z` | `const/4 v0, 0` + `return v0` |
| 3 | `PwfNative.expiryEpochMillis()J` | `const-wide/16 v0, 0` (muestra "Lifetime") |
| 4 | `PwfNative.onSessionEnded(String,String)V` | cuerpo vacío (no-op) |
| 5 | `ModMenuState.isLoggedIn()Z` | `const/4 v0, 1` + `return v0` |
| 6 | `ModMenuState.getAuthenticated()Z` | `const/4 v0, 1` + `return v0` |

Los `.so` quedaron **intactos** (no hace falta parche nativo) y
`assets/SignatureKiller/origin.apk` se conserva dentro del APK.

Build reproducible: baksmali del classes24 en mini-APK (`apktool d -r`), parcheo con
`patches/patch_v1.py`, rebuild (`apktool b`), swap del dex en una copia del APK
original, borrado de la firma v1 vieja, `zipalign` + firma v1+v2+v3 con la AOSP
testkey real (`patches/build_cracked.sh`). Verificación: re-baksmali del APK final
confirma 6/6 parches, 26 dex intactos, 5.818 entradas del dex preservadas,
origin.apk y libsamurai.so byte-intactos, firma `VERIFIED`.

## Instalación

1. Descarga `SansxdSamurai-1.3.0-cracked.apk` del release.
2. Desinstala el 8 Ball Pool original (el mod usa el mismo package name; si la firma
   difiere no admite instalación encima).
3. Instala permitiendo orígenes desconocidos.
4. Abre el juego: el menú flotante aparece a los ~2 s, ya autenticado
   ("Lifetime", sin LoginScreen ni petición de licencia).

## Estructura del repo

```
Informe_RE_SansxdSamurai-1.3.0.pdf   Informe completo (11 págs)
analysis/                            Reportes: menú mod, nativo, strings StringFog, manifest
patches/                             Parche V1 + scripts de extracción y build reproducibles
```

Herramientas: jadx 1.5.6, apktool 3.0.3, uber-apk-signer 1.3.0, capstone 5.0.7 +
pyelftools (desensamblado ARM64), dumper StringFog propio (`analysis/stringfog_decrypt.py`).
