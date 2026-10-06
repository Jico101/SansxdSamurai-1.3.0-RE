# Reporte análisis nativo — libsamurai.so + libSignatureKiller.so
**Target:** SansxdSamurai-1.3.0.apk (8 Ball Pool mod) · ARM64
**Fecha:** análisis estático puro con capstone 5.0.7 + pyelftools (r2 no terminó de compilar; Ghidra no fue necesario). **Los .so NO fueron modificados** (solo lectura).

---

## 0) RESUMEN EJECUTIVO (TL;DR)

**libsamurai.so 1.3.0 es un build de TEST del propio modder: el sistema de licencias ya viene parcheado de fábrica.**
- `vqesunkz` (isSignedIn) **YA devuelve 1** (`mov w0,#1; ret`) — la lógica real quedó como código muerto debajo.
- `mbdcouus` (isLicenseExpired) **YA devuelve 0** (`mov w0,#0; ret`).
- `orljmgpg` (login) **YA devuelve el JSON constante** `{"success":true,"message":"PWF Auth crypto test"}` — jamás contacta al servidor.
- `ofqdipvs` (expiryEpochMillis) devuelve 0. `eurhthzn` (segundos restantes) lee un global que `qOooOo` y TODOS los setters de config del menú re-escriben con **INT64_MAX** (nunca expira).
- **NO existe ningún check de integuidad nativo** (sin verificación de firma vía JNI, sin hash de classes.dex, sin anti-frida/anti-root/anti-ptrace, sin CRC). El hooking (xHook + MSHookFunction + A64HookFunctionV) es infraestructura del cheat, no anti-tamper.
- El "servidor de licencias" es un repo de GitHub: `https://raw.githubusercontent.com/hunttly/bdk/refs/heads/main` (solo config remota; el login real está muerto).
- libSignatureKiller.so = SignatureKiller clásico de MT Manager: GOT-hook de `open/open64/openat/openat64` en todos los .so para redirigir lecturas del APK mod → `assets/SignatureKiller/origin.apk` (APK original Miniclip).
- **Conclusión del plan de parche: NO se requiere parchear nada en el .so.** El gate nativo ya está abierto. El trabajo se concentra en la capa Java.

---

## 1) TRIAGE ELF — libsamurai.so

| Propiedad | Valor |
|---|---|
| Ruta | `lib/arm64-v8a/libsamurai.so` |
| Tamaño | 10.371.944 bytes (10.4 MB) |
| SHA-256 | `297fde056ca9f6a407221df41d510d81923524c30f915ec29754805c1fbf986a` |
| Tipo | ELF64 LSB **shared object**, **AArch64**, Android (API 23+), NDK r29 (14206865) |
| BuildID | ec667924ae87d9ea7a60e1957ed209af4b957d7f |
| Stripped | SÍ (sin .symtab), pero **conserva .dynsym completo (≈11.607 símbolos, 5.243 FUNC GLOBAL exportadas)** |
| Compilador | clang 21.0.0 (+pgo,+bolt,+lto,+mlgo) — Android r563880c |
| Secciones | 28, normales; sin packer, sin secciones raras, sin entropy anomalies |
| Note | `.note.android.ident`, `.note.gnu.build-id` estándar |

**Composición:** es un **monolito estático** que arrastra:
- OpenSSL/BoringSSL completo (SSL_*, X509_*, EVP_*, CRYPTO_gcm128_*, MD5/SHA, BIO…) — 5.000+ exports
- libc++ (`_ZNSt6__ndk1…`) completo
- **ImGui** (mod-menu overlay OpenGL ES 3.0: `#version 300 es`, Dear ImGui strings)
- **nlohmann::json** (parsing de respuestas/config)
- **xHook 1.2.0 aarch64** (qiyi GOT hooker: `Java_com_qiyi_xhook_NativeHandler_*`, `xhook_register/refresh/clear/ignore`)
- **MSHookFunction + A64HookFunctionV** (inline hook tipo Substrate/And64)
- Motor del mod: strings de juego ("AutoPlayFast: nomination timeout", "TableSkin: restoring the native table artwork", clases `GoldenShot::Prepare(double,double)` = aimbot, "golden ball index", "opening 8-ball tables"…)

**Prueba de que fue compilado EN UN TELÉFONO con un IDE on-device** (AIDE-style, paquete `com.nullij.androidcodestudio`):
```
/data/user/0/com.nullij.androidcodestudio/files/home/SAMURAI-MOD/app/src/main/Native/jni/...
```
El autor se firma como **"xHuntx"** (tag de log `xHuntx` @ 0xe8268; repo GitHub `hunttly/bdk`).

**Protección/ofuscación detectada:**
1. **Strings sensibles cifradas en runtime**, dos esquemas:
   - **XOR con clave deslizante de 64 bits**: `key=0xdb596d4d2ba93527`, `out[i]=enc[i]^((key>>((i&7)*8))&0xff)` (así se descifran las URLs; ver §4).
   - **VM aritmética propia** (jumptable con `a+b-2*(a&b)`≈XOR + restas por caso) para strings de ~11–29 bytes (nombres de funciones hookeadas, nombres de clase JNI). Ejemplo: la cadena de 27 bytes decodificada en el instalador de GOT-hooks @0x61b674. No se decodificaron estáticamente (requeriría emulación); no afectan al análisis de licencias.
2. Nada de OLLVM real (el código es legible, control flow normal). No hay packer/entropía anómala.

**Strings legibles:** sí, miles (OpenSSL, ImGui, mensajes del sistema de licencia, rutas del autor). Ejemplos clave con offset (file==VA en .rodata):
```
0x1cbde2  onSessionEnded
0x1cbd33  /data/user/0/com.miniclip.eightballpool/files/persistence.json
0x1cbd77  hwid
0x268392  success
0x2683ac  HMAC-SHA256 hashing
0x2f8139  message
0x2f8141  The license server answered with HTTP status 
0x339e31  The license server must use HTTPS.
0x339e54  The heartbeat failure limit must be positive.
0x339e82  session_id
0x339e8d  The license server rejected the session.
0x359128  Generating the AES IV
0x35911c  license_key
0x359177  expires_at
0x359182  %d-%d-%dT%d:%d:%dZ%c   (ISO-8601)
0x384758  Connecting to the license server failed: 
0x38478b  seller
0x384792  name
0x3ec4f4  enabled
0x1ce06?? pL9v: libloader.so found at base=0x%lx, injecting GOT hooks  (0x1ece06)
```

### Program headers (para conversión VA→file offset)
```
LOAD  off=0x000000 vaddr=0x000000 filesz=0x9a4410 R E   → VA == file offset (0x0..0x9a4410)
LOAD  off=0x9a4410 vaddr=0x9a8410 filesz=0x31450  RW    → VA = off + 0x4000 (0x9a4410..0x9d5860)
LOAD  off=0x9d5860 vaddr=0x9dd860 filesz=0xe190   RW    → VA = off + 0x8000 (0x9d5860..0x9e39f0)
```
`.text` 0x588e50–0x997170 (VA==offset) · `.rodata` 0xe5ac0–0x541cb8 (VA==offset) · `.data` VA 0x9dd860 (file 0x9d5860) · `.bss` VA 0x9ec000–0xa3abe8.

---

## 2) MAPA DE EXPORTS / JNI NATIVES

Los natives NO se llaman `Java_com_samurai_...` — se registran con **RegisterNatives** en `JNI_OnLoad` y ADEMÁS quedan exportados con el nombre ofuscado como símbolo dinámico. Las tablas JNINativeMethod están en `.data.rel.ro`:

- **Tabla ConfigNative (25 métodos) @ VA 0x9aad20** — clase `com/samurai/vengine/utils/ConfigNative` (config del menú + URLs)
- **Tabla PwfNative (11 métodos) @ VA 0x9ab850** — clase `com/samurai/vengine/utils/PwfNative` (licencias)

### PwfNative (licencias) — tabla @0x9ab850, direcciones = exports dynsym
| Método Java | Símbolo nativo | VA (=file off) | Tamaño | Estado |
|---|---|---|---|---|
| orljmgpg(appSecret, licenseKey)→String | orljmgpg | **0x637dac** | 836 | **STUB: devuelve `{"success":true,"message":"PWF Auth crypto test"}`** (tail-call `env->NewStringUTF` @ 0x637dc0; string @0x2cf5ca) |
| yvoanier(String)→String | yvoanier | **0x6384cc** | 1628 | VIVO: heartbeat/consulta de sesión → JSON `{"success":false,"code":"NOT_SIGNED_IN",...}` si no hay sesión (strings 0x1793b3/0x203ee6/0x21f448/0x14408d/0x2b826b) |
| ijapttvh(String)→String | ijapttvh | **0x638b28** | 276 | VIVO: logout → llama 0x637868 (end session server-side) y devuelve JSON |
| vqesunkz()→boolean | vqesunkz | **0x638c3c** | 292 | **STUB: `mov w0,#1; ret`** — isSignedIn()==true SIEMPRE |
| rfeuqvzl(String)→void | rfeuqvzl | **0x638d60** | 400 | VIVO: **endSession(reason)** — pide fin de sesión: flag atómico (session+0x128), notify_all(session+0x154), join del thread heartbeat (vía 0x620b1c). NO es setAppSecret |
| ubhdevbb()→void | ubhdevbb | **0x638ef0** | 332 | VIVO: termina sesión (llama 0x61d644 sobre el objeto sesión) |
| ofqdipvs()→long | ofqdipvs | **0x63903c** | 12 | **STUB: `mov w0,#0; ret`** — expiryEpochMillis()==0 |
| eurhthzn()→long | eurhthzn | **0x639048** | 124 | VIVO: ver §3 |
| pvskhmnc()→String | pvskhmnc | **0x6390c4** | 412 | VIVO: sellerName — lee struct en .bss 0xa212c8–0xa212e0 (con mutex 0xa21298) |
| qOooOo()→String | qOooOo | **0x639260** | 1928 | VIVO: assetSourceRoot — **Y ADEMÁS escribe expiración permanente** (ver §3) |
| mbdcouus()→boolean | mbdcouus | **0x63ba40** | 24 | **STUB: `mov w0,#0; ret`** — isLicenseExpired()==false SIEMPRE |
| (callback) onSessionEnded(String,String) | — | invocador @0x635e44 | — | VIVO pero dormido: thread que hace AttachCurrentThread + FindClass(PwfNative) + GetMethodID("onSessionEnded","(Ljava/lang/String;Ljava/lang/String;)V") + CallVoidMethod |

### ConfigNative — tabla @0x9aad20 (resumen)
hpkdccpm()Z, lvdjcfzv(String,Z)Z, ojiaelry(String,F)F, utguaqeq(String,I)I, cjgtyndn(String,String)String, dbtbwwmb(String,Z)V, eitkafpe(String,F)V, seedgbbf(String,I)V, tqcbtoco(String,String)V, uybujcgo()Z (lee bool .bss@0xa1fd14), srdaqygh(Z)V, pupiwgwf(String)V, lsyweczd()V, komkytoc()V, pzadwwun()[I, xypnkmmw()String, rwshnrfy(I)V, doxloecl(I)V, tusbjmbm(I)V, qrymuwow(String)V, **nativeGetBaseUrl→nhjgmdnm@0x5d5adc**, **nativeGetResellerUrl→jrqpdgsw@0x5d5bf8**, **nativeGetGameVerUrl→aocxwaae@0x5d5e3c**, **nativeGetBannersUrl→eqidilew@0x5d6080**, nativeGetDefaultGameVersion→lzsvorot@0x5d62c4 (devuelve "56.29.2").

`JNI_OnLoad` @ **0x5d635c** (3324 bytes) hace:
1. log `__android_log_print(4, "xHuntx", "JNI_OnLoad", ...)`,
2. cachea el JavaVM en .bss @0x9edd60,
3. decodifica por VM el nombre de clase y hace **RegisterNatives** (log "[JNI] bound %d natives on %s"),
4. `dl_iterate_phdr` + parseo manual de `.dynamic` (DT_STRTAB=5/DT_SYMTAB=6/DT_FLAGS=0x6ffffef5) de los módulos cargados (infraestructura xHook para localizar libloader.so),
5. lanza **2 threads detached**: `pthread_create(…, 0x58a5a0, 0x5d2508)` (dispatcher del menú: log "[M] call type=void addr=0x%lx caller=%s:%d", tag "angousana") y `pthread_create(…, 0x5d7058, NULL)` ( AttachCurrentThread + llamadas JNI — puente con NativeModMenuBridge `com/samurai/vengine/screens/modmenu/NativeModMenuBridge` @0x2cf592).
6. Espera con `usleep(300000)` hasta localizar **libloader.so** e **"inyectar GOT hooks"** (log "pL9v: libloader.so found at base=0x%lx, injecting GOT hooks" @0x1ece06, referenciado desde 0x61b5e0; símbolos objetivo ofuscados con la VM).

`.init_array` (0x9d1c58, 19 ctors): inicializadores C++ estándar del menú (0x59xxxx–0x5cxxxx), OpenSSL (0x7344d8, 0x73459c) y del framework de hooks (0x7abd6c, 0x7ad42c). Nada anti-tamper.

---

## 3) LÓGICA DE vqesunkz / mbdcouus (y eurhthzn/ofqdipvs)

### vqesunkz (isSignedIn) @0x638c3c — YA PARCHEADO
```
0x638c3c: 20 00 80 52  mov w0, #1
0x638c40: c0 03 5f d6  ret
```
**Devuelve true incondicional.** El código real queda después (muerto, inalcanzable tras el `ret`):
```c
// dead code @0x638c44..:
bool real_isSignedIn() {
    initJavaVMOnce();                    // GetJavaVM -> 0xa21248
    lock(g_mutex@0xa21268);              // std::mutex
    Session* s = g_session@0xa21258;
    bool r = s ? s->isSignedIn() : false;   // 0x620c24: lock(s+0x58); return (string s+0x80 "session_id") != ""
    unlock;
    return r;
}
```
Es decir: el check original = **"existe session_id"** (string en el struct Session @+0x80, protegido por mutex @+0x58). Estado global en .bss: JavaVM* @0xa21248, Session* @0xa21258, guards @0xa21260/0xa21290, mutex @0xa21268.

### mbdcouus (isLicenseExpired) @0x63ba40 — YA PARCHEADO
```
0x63ba40: 00 00 80 52  mov w0, #0
0x63ba44: c0 03 5f d6  ret
```
**Devuelve false incondicional.** El código real muerto (@0x63ba48+) lee los mismos globals que eurhthzn (ver abajo) y devuelve `!(expiry > now)`.

### eurhthzn (expirySecondsRemaining) @0x639048 — VIVO, lee estado LOCAL
```c
long eurhthzn() {                       // globals en .data:
    long valid = *(u64*)0x9de580;       // file off 0x9d6580, init = 0xFFFFFFFFFFFFFFFF (-1)
    if (valid < 1) return 0;            // sin sesión -> 0
    long exp = *(u64*)0x9de588;         // file off 0x9d6588, init = -1  (steady_clock ms)
    long now = steady_clock::now();     // PLT 0x997770 (monótono, desde boot)
    long ms = now / 1000000;            // magic 0xbce4217d28490cb2 >>18  ==  /1e6
    long secs = (ms + exp) / 1000;      // magic 0x20c49ba5e353f7cf >>7   ==  /1e3
    return secs > 0 ? secs : 0;         // bic x0,x8,x8,asr#63 (clamp a 0)
}
```
**DATO CLAVE:** usa `steady_clock` (relativo al boot), NO wall-clock → la expiración se guarda como marca monótona local (no se consulta al servidor; cambiar la hora del device NO la extiende, pero un reboot resetea steady_clock).

### ofqdipvs (expiryEpochMillis) @0x63903c — STUB → 0

### ¿Quién escribe 0x9de580/0x9de588?
- `setPermanentExpiry()` @ **0x639ae8** (función estática):
```
0x639ae8: mov w8,#1; stlr w8,[0xa212e8]      ; flag .bss
0x639b00: str x10=1,   [0x9de580]            ; valid = 1
0x639b04..0x639b14: x11 = 0x7FFFFFFFFFFFFFFF ; INT64_MAX
          str x11,   [0x9de588]              ; expiry = INT64_MAX (NUNCA expira)
0x639b18: mov w0,#1; ret
```
- **Callers de 0x639ae8 (bl):** 0x5965a0, 0x5a648c, 0x5a6a44, 0x5a8854, 0x5aa024, 0x5aee44, 0x5b98d4, 0x5bff3c, 0x5c20c0, 0x5c24b0 (motor del menú) y **los setters de config de ConfigNative: dbtbwwmb(setBool)+0x24, eitkafpe(setFloat), seedgbbf(setInt), tqcbtoco(setString), rwshnrfy, doxloecl, tusbjmbm, qrymuwow, y 0x5d31dc/0x5d344c/0x5d36b4/0x5d391c/0x5d3c38**.
→ **Cada vez que el menú guarda una config, re-afirma expiración = INT64_MAX.** Además el flujo de sesión real (0x636ee8/0x636f54/0x636fcc y 0x63bce8/0x63bd70 — setExpiry desde login/heartbeat) también escribe estos globals, pero está dormido.

---

## 4) FLUJO DE orljmgpg (LOGIN) — REAL vs STUB

### Stub (lo que ejecuta)
`orljmgpg(env, clazz, appSecret, licenseKey)`:
```
0x637dac: adrp x8, 0x2cf5ca ; '{"success":true,"message":"PWF Auth crypto test"}'
0x637db4: ldr x9,[x0]; ldr x9,[x9,#0x538]   ; env->NewStringUTF
0x637dc0: br x9                              ; return NewStringUTF("{\"success\":true,...}")
```
**Ignora appSecret y licenseKey por completo. No hay red, no hay crypto, no guarda estado. El JSON es éxito fijo.**

### Flujo REAL (código muerto documentado por strings — así era el diseño original)
1. **Constructor de petición**: "Generating the AES IV" (0x359128) → **AES-GCM** (la lib trae CRYPTO_gcm128_*) con IV aleatoria; payload firmado con **"HMAC-SHA256 hashing"** (0x2683ac) usando el **appSecret**.
2. **HTTPS obligatorio**: assert "The license server must use HTTPS." (0x339e31). Cliente TLS = OpenSSL estático (mismas rutinas exportadas).
3. **POST/GET al license server**; errores tipados:
   - "Connecting to the license server failed: " (0x384758)
   - "The license server answered with HTTP status %d" (0x2f8141)
4. **Respuesta JSON** (nlohmann) con claves: `success`, `message`, `session_id`, `license_key`, `expires_at` (ISO-8601 "%d-%d-%dT%d:%d:%dZ", 0x359182), `seller{name}`, `hwid`, `enabled`. Error de expiración: "The login reply did not contain a valid expiry." (0x35913e).
5. **Sesión persistida en disco**: `/data/user/0/com.miniclip.eightballpool/files/persistence.json` (0x1cbd33, usada por komkytoc@0x5d4c2c y 0x5d476c). **HWID** derivado de props `ro.product.device` (0x26839a) / `ro.product.model` (0x2f816f) + algo de `__system_property_get`.
6. **Heartbeat periódico** con límite de fallos configurable: "The heartbeat failure limit must be positive." (0x339e54); rechazo: "The license server rejected the session." (0x339e82) → si el heartbeat falla N veces → **onSessionEnded(String,String)** vía el thread @0x635e44 (AttachCurrentThread→FindClass(PwfNative)→GetMethodID→CallVoidMethod→Detach).
7. Con la sesión viva, `expiry` se guarda en los globals .data (0x9de580/0x9de588) en unidades de **steady_clock ms**.

### URLs del "servidor" (descifradas estáticamente, XOR key 0xdb596d4d2ba93527, data @0x4c5aa8+)
| Getter | URL descifrada |
|---|---|
| nativeGetBaseUrl (nhjgmdnm) | `https://raw.githubusercontent.com/hunttly/bdk/refs/heads/main` (61 bytes, enc@0x4c5aa8) |
| nativeGetResellerUrl (jrqpdgsw) | base + `/resller.json` (13 bytes, enc@0x4c5ae8) |
| nativeGetGameVerUrl (aocxwaae) | base + `/gamever.json` (enc@0x4c5af8) |
| nativeGetBannersUrl (eqidilew) | base + `/banners.json` (enc@0x4c5b08) |
Script de descifre: `out[i]=enc[i]^((0xdb596d4d2ba93527>>((i&7)*8))&0xff)`.
**Es GitHub raw — un canal de config/remotas del modder (revendedores, banners, versiones), no un backend de validación por sesión.** El repo `hunttly/bdk` puede morir en cualquier momento sin afectar al login (que ya no lo usa).

---

## 5) INVENTARIO DE CHECKS DE INTEGRIDAD NATIVOS

**Resultado: CERO checks de integridad / anti-tamper / anti-debug / anti-root orientados a defender el APK.** Detalle de la búsqueda:

| Vector buscado | Resultado | Evidencia |
|---|---|---|
| Validación de firma vía JNI (PackageManager/getPackageInfo/getSignatures) | **NO EXISTE** | 0 strings `android/content/pm/...`, `getPackageInfo`, `GET_SIGNATURES` en todo el .so. Las únicas llamadas JNI a Java desde nativo son FindClass de sus propias clases (PwfNative, NativeModMenuBridge) |
| Hash hardcodeado de classes.dex / base.apk / CRC | **NO EXISTE** | 0 strings `classes.dex`, `base.apk`, `crc32` de APK. Único hash suelto: `d41d8cd98f00b204e9800998ecf8427e` (MD5 de cadena vacía, tabla interna OpenSSL @0x5112f8) — no es un check |
| Hex constantes MD5/SHA-1/SHA-256 (32/40/64 chars) tipo firma de cert | **NO EXISTE** | grep exhaustivo: solo el MD5("") anterior y outputs de libcrypto |
| Anti-debug ptrace | **NO** | 0 imports ptrace/prctl/tgkill (dynsym UND: 362 símbolos, ninguno) |
| Anti-frida (frida/gum/gmain/27042/27043) | **NO** | 0 matches |
| Anti-root (su, magisk, supersu) | **NO** | 0 matches de `/system/bin/su`, `/system/xbin/su`, `magisk` |
| Detección emulador (goldfish/qemu/generic/test-keys) | **NO** | 0 matches (solo `ro.product.device/model` para HWID de licencia) |
| `/proc/self/maps` | **SÍ, pero es infraestructura de hooking** (xHook necesita enumerar módulos) | string @0x129751; usado por xhook_refresh de ambos .so; "fopen /proc/self/maps failed" @0x42d922 |
| `dl_iterate_phdr` + parseo .dynamic | **SÍ, idem: localiza libloader.so para inyectar GOT hooks del cheat** | JNI_OnLoad @0x5d6670; instalador con usleep-wait @0x61b5c0, log "pL9v: libloader.so found at base=0x%lx, injecting GOT hooks" (ref @0x61b5e0) |
| MSHookFunction / A64HookFunctionV / xhook | **SÍ — motor de cheats** (inline hook ARM64 + GOT hook) | exports 0x7abee4 / 0x7ac2c0 / 0x7ad494+; targets con nombres VM-ofuscados |
| onSessionEnded callback | **SÍ pero dormido** — solo dispara si hay sesión activa y el heartbeat la revoca; con login stubbed jamás se crea sesión | thread @0x635e44; Session::requestEnd @0x620b1c (flag atómico +0x128, condvar +0x154, join thread +0x120) |
| Thread de integridad/heartbeat propio | Solo los 2 threads de JNI_OnLoad (menú dispatcher 0x58a5a0 y bridge JNI 0x5d7058) + heartbeat por sesión (dormido) | — |

**Conclusión:** reempaquetar/re-firmar el APK **no será detectado por libsamurai.so**. Los hooks que instala son para manipular al juego (libloader.so), no para vigilarse a sí mismo.

---

## 6) EL appSecret

- Java (`LicenseAuth`/`PwfNative`, capa Java) construye el appSecret y la licenseKey y llama `orljmgpg(appSecret, licenseKey)`. La key se guarda en prefs cifrada con AES/GCM vía Android Keystore.
- **En nativo, el stub ignora ambos parámetros.** En el diseño original (muerto) el appSecret era la clave de firma HMAC-SHA256 de las peticiones al server y/o la clave AES-GCM del payload ("Generating the AES IV" + "HMAC-SHA256 hashing"), y el `hwid` (ro.product.device/model) viajaba en el JSON.
- `rfeuqvzl(String)` **NO** es setAppSecret: es `endSession(reason)` (ver §2). No existe ninguna función "setSecret" viva; el appSecret viajaba dentro del propio orljmgpg.
- No hay clave embebida utilizable: los blobs base64 enormes del .so (0x366075, 0x394c4e, 0x1cb900, tablas `__samurai_online_table_`/`__samurai_table_tokyo_2c6db260cf91056f`) son **PNG de skins de mesa** (magic `\x89PNG` junto a `__samurai_table_tokyo_...`), assets del mod, no cripto.

---

## 7) libSignatureKiller.so (21.184 bytes) — ANÁLISIS COMPLETO

- ELF64 AArch64 shared object, Android API 21+, **NDK r24**, LLD 14, stripped; embebe **xHook 1.2.0 (aarch64)** (strings "libxhook 1.2.0", "xh_refresh_loop", protección SIGSEGV con sigsetjmp/siglongjmp).
- **Export único Java: `Java_bin_mt_signature_KillerApplication_hookApkPath` @0x1a38** (+ wrappers xhook_register/refresh/ignore/clear @0x1c98-0x1ca4). Es el SignatureKiller de **MT Manager** (paquete `bin.mt.signature.KillerApplication`, ya visto en classes21 del APK junto a org.lsposed.hiddenapibypass).
- **`hookApkPath(String pathMod, String pathOrigin)`** (JNI, x2/x3 → GetStringUTFChars vía env+0x548):
```
0x1a64: str x0, [0x6ae8]   ; .bss g_pathA  (ruta A = APK instalado/mod)
0x1a98: str x0, [0x6af0]   ; .bss g_pathB  (ruta B = origin.apk original)
xhook_register(".*\.so$", "openat64", hook@0x1b20, &old@0x6af8)
xhook_register(".*\.so$", "openat",   hook@0x1b84, &old@0x6b00)
xhook_register(".*\.so$", "open64",   hook@0x1be8, &old@0x6b08)
xhook_register(".*\.so$", "open",     hook@0x1c40, &old@0x6b10)
xhook_refresh()
```
- **Hook (ej. openat64 @0x1b20):**
```c
int hook_openat64(int dirfd, const char* path, int flags, mode_t mode) {
    if (strcmp_like(path, g_pathA) == 0)      // 0x4600 con g_@0x6ae8
        path = g_pathB;                        // redirige a origin.apk
    return ((openat64_t)old@0x6af8)(dirfd, path, flags, mode);  // tail-jump
}
```
  Es decir: **cuando cualquier .so (incluida la lógica del juego/libloader) abre el APK instalado para leer su firma/contenido ZIP, se le sirve en su lugar `assets/SignatureKiller/origin.apk`** (APK original Miniclip de 146MB con el certificado real). La parte Java del SignatureKiller (KillerApplication + proxy de PackageManager) cubre los checks en Java.
- **Implicación para el re-pack:** mientras no se toque `assets/SignatureKiller/origin.apk` ni la clase KillerApplication, el spoofing de firma sigue funcionando igual tras re-firmar con la AOSP testkey (los nativos solo comparan RUTAS, no hashes). El plan de re-firmar con la misma testkey mantiene además el hash del certificado del APK mod (coincide con el actual).

---

## 8) PROPUESTA DE PARCHE NATIVO (file offsets EXACTOS)

### Estado actual: **YA ESTÁ PARCHEADO — NO HAY QUE TOCAR NADA**
Verificación raw (VA==file offset en .text, segmento LOAD 1 vaddr=off):
```
vqesunkz  @ file 0x638c3c: 20 00 80 52 c0 03 5f d6   ; mov w0,#1 ; ret   → isSignedIn()==true
mbdcouus  @ file 0x63ba40: 00 00 80 52 c0 03 5f d6   ; mov w0,#0 ; ret   → isLicenseExpired()==false
ofqdipvs  @ file 0x63903c: 00 00 80 52 c0 03 5f d6   ; mov w0,#0 ; ret   → expiryEpochMillis()==0
orljmgpg  @ file 0x637dac: adrp+add→NewStringUTF("{\"success\":true,\"message\":\"PWF Auth crypto test\"}")
```
**Cálculo VA→file offset (documentado):** los 4 símbolos están en `.text` (section addr 0x588e50 = offset 0x588e50; PHDR LOAD#1 off=0 vaddr=0, 0x4000-aligned) ⇒ **file_offset = VA** para TODO el rango 0x0–0x9a4410. Solo .data.rel.ro/.got usan VA=off+0x4000 y .data VA=off+0x8000.

### Parche idempotente (por si se quiere "asegurar" contra builds futuros del mismo mod)
| Función | VA=file offset | Bytes a escribir | Instrucciones |
|---|---|---|---|
| vqesunkz → 1 | **0x638c3c** | `20 00 80 52 c0 03 5f d6` | mov w0,#1; ret |
| mbdcouus → 0 | **0x63ba40** | `00 00 80 52 c0 03 5f d6` | mov w0,#0; ret |

(ARM64 puro; el .so NO es multi-ABI ni Thumb — ELFCLASS64 EM_AARCH64 único. Las variantes Thumb no aplican.)
**En este binario, escribir esos bytes es un no-op** (ya son exactamente esos valores).

### ¿Java o nativo? — RECOMENDACIÓN
**No tocar el nativo.** Razones:
1. El gate nativo ya está abierto por el propio modder (build de test "PWF Auth crypto test"); cualquier parche adicional al .so solo añade riesgo (p.ej. si alguien re-distribuye el .so y el modder publicara un build "real", habría que re-analizar).
2. **Cero checks nativos de integridad** → re-firmar/re-empaquetar el APK no dispara nada en libsamurai.so.
3. El único punto de fricción restante está en la **capa Java** (p.ej. `LicenseAuth.verify()` / flujo de login de com.aryanispe.login / StringFog). Si el gate Java ya llama a los natives y confía en `isSignedIn()/isLicenseExpired()`, con el estado actual del .so **la app ya pasa el gate sin ningún cambio**.
4. Parchear Java (smali) es reversible, no invalida el spoofing de firma de libSignatureKiller (que compara rutas, no contenidos), y evita tocar un binario de 10.4MB que el mod podría cargar con checksums propios en el futuro.

**Checklist si aun así se re-empaqueta:** conservar intactos `lib/arm64-v8a/*`, `assets/SignatureKiller/origin.apk`, y re-firmar con AOSP testkey (ya es la firma actual → mismo cert-hash).

---

## 9) EXPIRACIÓN Y POSIBLES CONTRADICCIONES ENTRE CHECKS

- **¿La expiración es local o del servidor?** El valor que Java puede leer (`ofqdipvs`, `eurhthzn`) sale de **globals locales en .data** (0x9de580/0x9de588, file 0x9d6580/0x9d6588), escritos por (a) el flujo de sesión real (muerto) a partir de `expires_at` del JSON del server — convertido a marca steady_clock, y (b) **`setPermanentExpiry`@0x639ae8** que pone INT64_MAX. Con el stub, (a) nunca corre y (b) se ejecuta desde qOooOo y desde cada setter de config del menú → la expiración efectiva es **local e infinita**. `ofqdipvs` ni siquiera lee el global (devuelve 0). Ningún polling al servidor toca la expiración mientras no exista sesión.
- **¿Puede un parche de isSignedIn/isLicenseExpired quedar desmentido por otros checks nativos?** En este build, NO:
  - No hay segundos gatekeepers: el menú (ConfigNative/NativeModMenuBridge) no consulta la sesión para las features; de hecho sus setters FUERZAN expiración infinita.
  - Las funciones vivas con semántica de sesión (`yvoanier` → "NOT_SIGNED_IN", `pvskhmnc` → seller, `ubhdevbb`/`rfeuqvzl` → end session, heartbeat/onSessionEnded) solo actúan si alguien crea una sesión — imposible con orljmgpg stubbed. En el peor caso devuelven JSON de error, pero no matan el proceso ni revocan features.
  - El único "vigilante" real es el heartbeat (y su callback onSessionEnded), dormido por diseño del stub.
  - Riesgo residual: si el modder publica un 1.4.0 con orljmgpg REAL restaurado, el heartbeat sí podría llamar `onSessionEnded` y cerrar el menú — en ese hipotético build habría que stubear `rfeuqvzl`/heartbeat o parchear `orljmgpg` a mano con los offsets de arriba (el layout de símbolos cambiaría, habría que re-localizar por dynsym).

---

## Anexo A — Herramientas y artefactos
- `re/analysis/native/aadis.py` — mini-disassembler capstone+pyelftools con resolución de PLT (pltmap.json) y símbolos.
- `re/analysis/native/xref.py` — escáner de xrefs adrp+add sobre .text.
- `re/analysis/native/{jnionload,yvoanier,jrqpdgsw,aocxwaae,eqidilew}.txt` — volcados de desensamblado.
- r2: no llegó a compilar (clone/build en background no completó); todo el análisis se hizo con capstone 5.0.7 + pyelftools sin Ghidra (RAM conservada).
