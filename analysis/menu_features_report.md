# Reporte de análisis — Menú mod "vengine" y StringFog (SansxdSamurai-1.3.0)

Alcance: análisis sobre jadx_24 (classes24.dex del mod)

---

## 1. Algoritmo StringFog (verificado contra código real)

**Archivos**: `jadx_24/sources/com/samurai/vengine/StringFog.java` y `jadx_24/sources/com/github/megatronking/stringfog/xor/StringFogImpl.java`

```java
// StringFogImpl.xor(data, key):
int i = 0, i2 = 0;
while (i < data.length) {
    if (i2 >= key.length) i2 = 0;   // índice de clave cíclico
    data[i] = (byte)(data[i] ^ key[i2]);
    i++; i2++;
}
// decrypt: new String(data, StandardCharsets.UTF_8)
```

- Algoritmo: **XOR cíclico** `plain[i] = data[i] ^ key[i % len(key)]`, resultado decodificado como **UTF-8**. Sin Base64 en runtime (la clase `com.github.megatronking.stringfog.Base64` solo se usa como marcador `k = Base64.NO_WRAP` en los Blob*).
- jadx emite los bytes Java con signo (-128..127) → convertir con `b & 0xFF`.
- **Script creado**: `scripts/stringfog_decrypt.py` (extrae con regex `StringFog.decrypt(new byte[]{...}, new byte[]{...})`, convierte a unsigned, XOR, UTF-8).
- **Resultado**: **3.151 strings descifradas de 54 archivos** → `analysis/stringfog_strings.txt` (formato: `archivo → Llinea: string`).

Verificación de sanidad: `LicenseConfig.BRAND` descifra `SAMURAI`, `VERSION` → `V1.3` (coincide con el banner del login "SAMURAI • V1.3").

---

## 2. Arquitectura "vengine" — qué es y cómo se monta sobre el juego

**"vengine" NO es un motor de juego ni un WebView: es un menú flotante 100% Jetpack Compose** inyectado como overlay dentro de las actividades del juego.

### 2.1 Bootstrap
- `com.samurai.vengine.Application::onCreate` (Application.java:13-16) → `InGameModMenuController.INSTANCE.install(this)`.
  - Esta Application está declarada en el AndroidManifest del APK modificado (classes26 contiene además el wrapper `EightBallPoolActivity`), por lo que TODO el proceso del juego arranca con este controlador registrado.
- `InGameModMenuController::install` (InGameModMenuController.java:371-397):
  1. `FacebookWebLogin.configure(application)` — fuerza login Facebook por WebView (`WEB_VIEW_ONLY`).
  2. `GoogleSignInHooks.install(application)` — parchea el Credential Manager de Android para Google Sign-In propio.
  3. `application.registerActivityLifecycleCallbacks(lifecycleCallbacks)`.

### 2.2 Overlay sobre el juego (sin permisos SYSTEM_ALERT_WINDOW)
- `InGameModMenuController::onActivityCreated` (líneas 400-461):
  - `currentGamePackage(activity)` filtra: solo si `Constants.isSupportedGamePackage(pkg)` con `TARGET_GAME_PACKAGE = "com.miniclip.eightballpool"` (Constants.java:13,21) Y la activity no es de login (`GoogleSignInWebViewActivity`, `androidx.credentials.playservices.*`, `com.google.android.gms.auth.api.signin.internal.SignInHubActivity`, `com.facebook.FacebookActivity`, `CustomTabMainActivity`, `CustomTabActivity` — todas StringFog-descifradas en currentGamePackage, líneas 293-303).
  - Obtiene el `ViewGroup` **`android.R.id.content`** de la activity del juego.
  - Crea un **`ComposeView`** con tag `MENU_VIEW_TAG = "samurai_in_game_mod_menu"` (L44).
  - Le inyecta un **`EmbeddedViewTreeOwner`** (inner class, líneas 115-170): un `SavedStateRegistryOwner`+`LifecycleRegistry` sintético, porque la activity del juego (C++/Unity-like) NO es una ComponentActivity y Compose lo necesita. Maneja ON_CREATE/START/RESUME/PAUSE/DESTROY manualmente desde los callbacks.
  - `composeView2.setContent(ComposableSingletons$InGameModMenuControllerKt.m85getLambda2())` → `Theme { ModMenuScreen(overlay=false, connectNative=true, InGameModMenuController.menuState, ...) }` (ComposableSingletons$InGameModMenuControllerKt.java:34,57).
  - `attachView(content, view)` → `content.addView(view, LayoutParams(-1,-1))` = **MATCH_PARENT añadido al final del content view de la actividad** → se dibuja ENCIMA del juego (es un View normal del mismo proceso, no una ventana overlay del sistema).
  - Visibilidad inicial GONE y `scheduleShow` con **`SHOW_DELAY_MS = 2000`** (L42) → aparece 2 s después de abrir la activity.
- `onActivityPaused/Resumed` sincronizan el lifecycle sintético y re-atachan la vista si la activity se recreó.
- `menuState` es un **singleton estático** (`InGameModMenuController.menuState`, referenciado en ComposableSingletons) — el estado sobrevive entre activities.

### 2.3 Assets embebidos (BlobXXXKt)
- `com/samurai/vengine/assets/`: imágenes y fuentes embebidas como **strings Base64 en constantes de clases** dentro del propio dex (BlobLOGOKt ~1.1 MB, BlobBALLKt, BlobCOMBATKt, BlobEIGHTKt, BlobNINEKt, BlobPLAY/PAUSEKt, 14× BlobTRAIL_PREVIEW_*, 4× BlobPOCKET_EFFECT_*, 4× BlobRUBIK_*).
- `ModMenuAssets::lazyPainter` (ModMenuAssets.java:70-114): `Base64.decode(blob)` → `BitmapFactory.decodeByteArray` → `BitmapPainter` de Compose (perezoso, con cache `Map<ModMenuImage, Lazy<BitmapPainter>>`, L54-62).
- `ModMenuAssets::rubikFontFamily` (L178-206): escribe los 4 TTF Rubik en `cacheDir/samurai_modmenu_fonts/` y los carga como `FontFamily` (tipografía del menú).
- `QueueModeImageBlobsKt` añade los bitmaps de los modos de mesa para el selector del Auto Queue.

### 2.4 Puente Java↔Nativo (el menú es solo UI; los cheats viven en libsamurai.so)
- `NativeModMenuBridge` (JNI, libsamurai.so) — TODOS los nombres ofuscados:
  | Método Java | JNI nativo | Función |
  |---|---|---|
  | getBoolean/getInt/getFloat/getString | `lvdjcfzv` / `utguaqeq` / `ojiaelry` / `cjgtyndn` | leer config de features |
  | setBoolean/setInt/setFloat/setString | `dbtbwwmb` / `seedgbbf` / `eitkafpe` / (setString) | escribir config |
  | readSnapshot-gate | `hpkdccpm()` | bool: ¿snapshot nativo listo? (si false, readSnapshot devuelve null) |
  | fetchUserInfo | `pzadwwun()` (int[7]) + `xypnkmmw()` (nombre) | stats del jugador |
  | isAutoPlaying / setAutoPlaying | `uybujcgo` / `srdaqygh` | botón play/pause del auto-play |
  | loadSettings / saveSettings | `komkytoc` / `lsyweczd` | SETTINGS FILE (persistencia nativa) |
  | setUserInfoCash/Coins/Level/Name | `doxloecl` / `rwshnrfy` / `tusbjmbm` / `qrymuwow` | changers (legacy, sin UI) |
  | showToastNotification | `pupiwgwf` | toasts nativos |
  | assetSourceRoot (en PwfNative) | `eurhthzn` | URL raíz para descargar skins |
- `NativeModMenuBridge::readSnapshot` (L476-540) lee TODAS las features con rangos `coerceIn` y construye `NativeMenuSnapshot`; `::apply(previous,current)` (L257-414) envía a nativo solo los valores que cambiaron.
- `ModMenuState::syncFromNative$app_release` (ModMenuState.java:1000-1096) copia el snapshot a MutableStates de Compose (la UI reacciona); `ModMenuScreenKt$ModMenuScreen$3$1::invokeSuspend` (ModMenuScreen.kt:405-409) hace polling cada 500 ms hasta que `syncFromNative` tiene éxito y luego observa `snapshotFlow { state.nativeSnapshot() }` para aplicar cambios a nativo.

### 2.5 Descarga de skins (red externa controlada por nativo)
- `TableSkinCatalog` (L18,33): VERSION `"web73372-layout1"`, 18 mesas: monaco, london, sydney, lisbon, tokyo, lasvegas, jakarta, toronto, cairo, dubai, shanghai, paris, rome, bangkok, seoul, mumbai, berlin, osaka (archivos `tableMonaco-hd.png` etc.).
- `CueSkinCatalog` (L16,20): VERSION `"web73372-cues-v1"`, decenas de tacos (archon, firestorm, valkyrie, necromancer, axion, kraken, excalibur, ... `Table_Archon_Cue-hd.png`).
  - "web73372" es el bucket web del 8 Ball Pool de Miniclip.
- `TableSkinCatalog::getSourceRoot$app_release` (L51-53) = `PwfNative.assetSourceRoot()` → **la URL raíz la decide libsamurai.so (nativo), no Java**.
- `TableSkinAtlasDownload::downloadVerifiedImage` (L197+): valida URI estricta — esquema `https`, mismo host que sourceRoot, sin puerto/userinfo/query/fragment — luego **descarga con Socket/HTTP crudo** (parseo manual de headers HTTP: "Incomplete atlas HTTP headers", "Invalid atlas HTTP line ending"). Nota UI: "Browser theme artwork. Download once; stored locally." (L29400).

---

## 3. Lista COMPLETA de features del menú (labels exactos que ve el usuario)

Estructura: `ModMenuPanel` → `MenuHeader` + pestañas (`MenuTab`: **Visuals / Combat / Queue / Misc / Settings** — MenuTab.java:31-52) → `MenuBody` switch (ModMenuScreenKt.java:10186-10214).

### Pestaña VISUALS (`VisualsTab`, ModMenuScreenKt.java:31653+)
| Sección | Control UI | Clave nativa | Setter (evidencia) |
|---|---|---|---|
| **ENGINE** | Toggle "Enable ESP" | `bESP` | `VisualsTab` L31703-31728 → setEspEnabled |
| **PREDICTION** | Toggle "Prediction Lines" (líneas de trayectoria = aim/guidelines) | `bESP_DrawPredictionLine` | L31730-31754 → setPredictionLines |
| **TRAJECTORY TURN STYLE** | Tarjetas "Normal Turns" / "Smooth Curves" | `iESP_PredictionLineStyle` (0/1) | L31789/31815 → setPredictionLineStyle(0|1) |
| ↑ | Toggle "Prediction Positions" (posiciones finales bola) | `bESP_DrawPredictionPos` | L31847 → setPredictionPositions |
| ↑ | Toggle "Initial Positions" | `bESP_DrawInitialPos` | L31872 → setInitialPositions |
| ↑ | Toggle "Prediction Pockets" (banderas de tronera) | `bESP_DrawPockets` | L31897 → setPredictionPockets |
| ↑ | Toggle "Prediction Shot State" | `bESP_DrawPocketsShotState` | L31922 → setShotState |
| ↑ | Sliders "Line Thickness" (1-6), "Pockets Thickness", "Shot State Thickness" | `fESP_PredictionLineThickness`, `fESP_PocketsThickness`, `fESP_PocketsShotStateThickness` | L31947/31972/31997 |
| ↑ | Sliders "Lines Alpha", "Pockets Alpha", "Shot State Alpha" (0-100) | `fESP_PredictionLineAlpha`, `fESP_PocketsAlpha`, `fESP_PocketsShotStateAlpha` | L32022/32047/32072 |
| ↑ | Slider "Pocket Size" (4-100) | `fESP_PocketSize` | L32097 |
| **TABLE SETTINGS** | "Table Mode" segmented Custom/Auto | `iTable_Mode` (1=Custom) | L32123-32153 → setTableMode |
| ↑ | Toggle "Draw Table Shape" | `bESP_DrawTableShape` | L32161-32179 → setDrawTableShape |
| ↑ | Sliders "Table Offset X"/"Table Offset Y" (-500..500), "Table Size" (0.5-2.0) | `fESP_TableShapeOffsetX/Y`, `fESP_TableShapeSize` | L32186-32254 |

Nota: existe además `bAntiCapture` (B_ANTI_CAPTURE, snapshot+apply) sincronizado desde nativo pero **sin toggle visible** en esta versión de la UI (anti-captura de pantalla, controlado nativamente).

### Pestaña COMBAT (`CombatTab`, ModMenuScreenKt.java:3344+)
| Sección | Control UI | Clave nativa | Evidencia |
|---|---|---|---|
| **AUTO PLAY** | Toggle "Auto Play" (el juego juega solo) | `bAutoPlay` | L3393-3412 → setAutoPlay |
| ↑ | "Autoplay Style": **Human / Fast / Hacker** | `iAutoPlayMode` (0-2) | L3419-3438 |
| **9-BALL** | "9-Ball Mode": **Normal / Target 9** | `iAutoPlay9BallMode` | L3446-3465 → setNineBallMode |
| **AUTO-PLAY PHYSICS** | Toggle "Random Spin" | `bAutoPlayRandomSpin` | L3473-3491 |
| ↑ | Toggle "Cushion Shot" (tiro a banda) | `bAutoPlay_MultiPockets` (clave corrupta; cushion) | L3498-3516 → setCushionShot |
| ↑ | (snapshot) "Clean Table" | `bAutoPlay_MultiPocgkets` (clave corrupta; cleanTable) | apply() L318-320 |
| **GOLDEN SHOT** | Toggle "Golden Shot" | `bGoldenShot` | L3524-3542 |
| ↑ | "Target Ring": **1 (Smallest) / Ring 2 / Ring 3 / 4 (Largest)** | `iGoldenShotTarget` (0-4) | L3549-3571 |

### Pestaña QUEUE (`QueueTab`, ModMenuScreenKt.java:27166+)
| Sección | Control UI | Clave nativa | Evidencia |
|---|---|---|---|
| **AUTO QUEUE** | Toggle "Auto Queue" (auto-búsqueda de partidas) | `bAutoQueue` | L27215-27234 |
| ↑ | "Queue Mode": **8Ball / 9Ball** | `iAutoQueue_GameMode` (0/1) | L27241-27260 |
| **FIXED TABLE** | Selector de mesa fija **M1..M17** (M1=100, M2=200, M3=1K, M4=5K, M5=20K, M6=100K, M7=200K, M8=500K, M9=1M, M10=2M, M11=5M, M12=8M, M13=10M, M14=20M, M15=30M, M16=50M, M17=200M monedas) | `sAutoQueue_FixedMode` | L27267-27290 (lista `QueueModes`, L236) |
| ↑ | (9Ball) selector de apuesta **100 / 500 / 2.5K / 10K / 50K / 100K / 500K / 2.5M / 10M** | `iAutoQueue9Ball_Bet` (NINE_BALL_QUEUE_BETS, NativeModMenuBridge.java:75) | L27300-27319 |
| ↑ | Toggle "Select Highest Table Available" | `bAutoPgy` (clave corrupta; selectHighestTable) | L27328-27346 |
| ↑ | Toggle "Stop at Coin Limit" | `bAutoPlaltiPock` (clave corrupta; stopAutoQueue) | L27353-27371 |
| — | `iAutoQueue_Mode` se fuerza a **2** siempre | apply() L386-387 | — |

### Pestaña MISC (`MiscTab`, ModMenuScreenKt.java:12722+) — sub-pestañas "Cosmetics" / "Skins" (L12453)
**Cosmetics**:
| Sección | Control UI | Clave nativa | Evidencia |
|---|---|---|---|
| **CUE BALL TRAIL** | "Trail Length": **Short / Long** | `iCueTrail_Length` (0/1) | L11742-11763 |
| ↑ | Selector de estilo de estela: **Off, Trail 55, Trail 119, Trail 122, Trail 68, Trail 78, Trail 112, Trail 116, Trail 114, Trail 109, Trail 106, Trail 102, Trail 82, Trail 84** (13 trails con preview animada) | `iCueTrail_Style` (0-13) | L11811-11872 (lista `CueTrailStyles` L238) |
| **BALL IMPACT EFFECT** | **Off, Spark Burst, Shockwave Ring, Star Flash, Particle Spray, Ice Shatter, Plasma Splash, Electric Rail** | `iBallImpact_Style` (0-7) | L11906-12011 (lista L239) |
| **CUSHION IMPACT EFFECT** | **Off, Rail Sparks, Cushion Shockwave, Diamond Burst, Rail Flash, Frost Scatter, Plasma Rail, Arc Burst** | `iCushionImpact_Style` (0-7) | L12068-12165 (lista L240) |
| **POCKET EFFECT** | **Off, Pocket Effect 1, Pocket Effect 2, Pocket Effect 3, Pocket Effect 5** | `iPocketFx_Style` (0-4) | L12216-12315 (lista L241) |

**Skins** (nota en UI: *"Visual only. Cue stats stay unchanged."* L3802):
- **CUE SKINS** (L12961): galería con previews; descarga desde el CDN (web73372-cues-v1) → `iCueSkin_Mode`(0=off/1=custom), `sCueSkin_Path`, `sCueSkin_Id`, `iCueSkin_Revision` (apply L333-341).
- **TABLE SKINS** (L12963): galería (18 mesas + "Original"/"Custom Tokyo table" como extras, L29655/29661) → `iTableSkin_Mode`(0-2), `sTableSkin_Path`, `sTableSkin_Id`, `iTableSkin_Revision`.

### Pestaña SETTINGS (`SettingsTab`, ModMenuScreenKt.java:27608+, ModMenuScreen.kt:2623)
| Sección | Contenido | Evidencia |
|---|---|---|
| **GAME INFORMATION** | Tarjeta "8 BALL POOL" + versión del juego (`resolveGameVersion`, L33102-33120, lee PackageInfo de com.miniclip.eightballpool, fallback "---") | L27662 |
| **GAME SETTINGS** | Toggle "Block Ads" → `bBlockAds` | L27666-27684 |
| **USER INFO** (lectura) | Level, Coins, Cash, Total Games Played, Games Won, Win Streak, Tournaments Won (de `fetchUserInfo` → int[7]+nombre) | L27691-27698 |
| **SETTINGS FILE** | Botones **Save Settings / Load Settings** → `NativeModMenuBridge.saveSettings()/loadSettings()` (nativo `lsyweczd`/`komkytoc`) | L27699, L27733, L27744 |
| **ABOUT US** | "Official Telegram" → intent VIEW **https://t.me/Samurai_8BP** (fallback toast "Unable to open Telegram") | L27777-27861 |

### Botones flotantes (siempre visibles sobre el juego)
- `FloatingMenuButtons-AFY4PWA` (ModMenuScreenKt.java:8483+): botón LOGO **arrastrable** (detectDragGestures, `ModMenuScreenKt$FloatingMenuButtons$2$1`) con contentDescription "Open mod menu" (L3167) → `setMenuOpen(true)` (L13854+); y botón PLAY/PAUSE con tooltips "Play autoplay"/"Pause autoplay" (L1365-1442) que alterna `setAutoPlaying` + `NativeModMenuBridge.setAutoPlaying` (L13802-13803).
- Header del panel: "Samurai", badge **"ACTIVE | PREMIUM ACCESS"** (L8288-8326), contador **"ACCESS EXPIRES IN" D/H/M/S** (L8372-8410, formato `%02d::%02d::%02d::%02d` L33053); tarjeta licencia: "Seller", "Expiry Date" (`yyyy-MM-dd HH:mm:ss`, L33042), "Time Remaining" / "Lifetime" (L9781-9783, L33040).

### Features nativas sin UI (presentes en snapshot/apply/state)
- `bAntiCapture` (anti-captura), `iLogo_Mode`/`iLogo_customposition`/`iLogo_Width`/`iLogo_Height` (marca de agua del mod), `iMenuScaleSetr` (escala del menú) — sincronizan desde nativo (ModMenuState.java:1059-1063) pero no hay controles en esta UI.
- Changers legacy sin UI: `nameChanger/coinsChanger/cashChanger/levelChanger` (ModMenuState.java:45-58) y `NativeModMenuBridge.setUserInfo*` — código muerto en 1.3.0.

---

## 4. Flujo UI y GATES de licencia (clase::metodo exacta)

### 4.1 Render gate (LoginScreen vs ModMenuScreen)
- **`ModMenuScreenKt::ModMenuScreen`** (ModMenuScreen.kt:74 en origen; jadx 13442):
  ```java
  // L13647-13653
  if (!modMenuState3.isLoggedIn()) {
      LoginScreenKt.LoginScreen(modMenuState3, composer2, 0);   // ← LOGIN
      return;
  }
  // else: AnimatedVisibility(menuOpen) → ModMenuPanel(...)      // ← MENÚ
  ```
  → **El único gate visible en Compose es `ModMenuState.isLoggedIn`**.

### 4.2 ¿Quién pone isLoggedIn? (3 fuentes)
1. **Login OK**: `LoginScreenKt$LoginScreen$submit$1::invokeSuspend` (LoginScreen.kt:122; jadx 49-79): tras `LicenseAuth.verify(candidate)` == null (éxito) → save + `setLicenseKey` + `setSellerName(PwfNative.sellerName())` + `setAuthenticated(true)` + **`setLoggedIn(true)`**.
2. **Auto-login al montar LoginScreen**: `LoginScreenKt$LoginScreen$1::invokeSuspend` (jadx 157-214): si no hay `sessionNotice`, hace `LicenseAuth.loadSaved(context)` → si existe, re-verifica (`LicenseAuth.verify(saved)`) → éxito ⇒ `setLoggedIn(true)`; fallo ⇒ `LicenseAuth.clear(context)` y muestra formulario.
3. **Poll cada 5 s**: `ModMenuScreenKt$MenuBody$2$1::invokeSuspend` (ModMenuScreen.kt:696/704; jadx 121-124):
   ```java
   do { this.$state.setLoggedIn(PwfNative.INSTANCE.isSignedIn() && !PwfNative.INSTANCE.isLicenseExpired()); }
   while (DelayKt.delay(5000L, this) != COROUTINE_SUSPENDED);
   ```
   → **`PwfNative.isSignedIn()` (JNI `vqesunkz`) && `!PwfNative.isLicenseExpired()` (JNI `mbdcouus`)** — el gate de verdad lo responde libsamurai.so; Java solo lo consulta.

### 4.3 Countdown de expiración (cierra sesión desde Java)
- `ModMenuScreenKt$MenuBody$1::invokeSuspend` (ModMenuScreen.kt:679; jadx 432-478, var "pwfManaged"):
  - Al iniciar: `setSellerName(PwfNative.sellerName())`, `setExpiryEpochMillis(PwfNative.expiryEpochMillis())` (JNI `ofqdipvs`), `setRemainingSeconds(PwfNative.expirySecondsRemaining())` (JNI `ijapttvh`); si epoch<=0 ⇒ `remainingSeconds = Integer.MAX_VALUE` (licencia **Lifetime**).
  - Bucle de 1 s (`delay(1000)`) decrementando `remainingSeconds`; al llegar a 0: **`LicenseAuth.clear(context)` + `setSessionNotice("License expired")` + `setAuthenticated(false)` + `setLoggedIn(false)`** ⇒ recomposición → LoginScreen.

### 4.4 onSessionEnded (callback JNI desde nativo)
- `PwfNative::onSessionEnded(code,message)` (PwfNative.java:134-138) es llamado por C++ → `_sessionEnded.tryEmit(new SessionEnd(code,message))` (SharedFlow buffer 8).
- Dos coleccionistas:
  1. `ModMenuScreenKt$ModMenuScreen$5$1::invokeSuspend` (ModMenuScreen.kt:424; jadx 47-63): `setAuthenticated(false)`, `setSellerName("")`, `setSessionNotice(message ?: code ?: "Session ended")`.
  2. `ModMenuScreenKt$MenuBody$2$1$C00001` (jadx 68-80): `setLoggedIn(false)` — el menú se desmonta al instante y vuelve el LoginScreen con el aviso.
- Resultado neto: **si el nativo emite SessionEnd, la UI regresa a LoginScreen aunque el polling 5 s aún no haya corrido.** El polling también lo revertiría en ≤5 s si `isSignedIn()` pasa a false.

### 4.5 Otros efectos del menú
- `ModMenuScreenKt$ModMenuScreen$3$1` (ModMenuScreen.kt:405/409): si `connectNative=true` → retry cada 500 ms de `state.syncFromNative$app_release()` (requiere `hpkdccpm()` true en nativo) y luego `snapshotFlow` → `NativeModMenuBridge.apply(previous,current)` — **si el nativo nunca da snapshot, el menú queda en estado default pero la licencia sigue siendo lo único gate-ado**.
- `ModMenuScreenKt$ModMenuScreen$4$1` (ModMenuScreen.kt:419): mientras `menuOpen`, cada 10 s `state.setUserInfo(NativeModMenuBridge.fetchUserInfo())`.

### 4.6 Implicación para el crack (coherente con Task 1)
- Bypass Java puro: forzar `isSignedIn()==true` y `isLicenseExpired()==false` hace que `MenuBody$2$1` ponga `loggedIn=true` en ≤5 s; también habría que acallar `onSessionEnded` (nativo) y el countdown (`expiryEpochMillis`). El gate más robusto está en nativo (`vqesunkz`/`mbdcouus`/`ofqdipvs`/`ijapttvh`), por lo que parchear libsamurai.so o los 4 métodos JNI de PwfNative sigue siendo la vía completa.

---

## 5. Strings descifradas más relevantes (top, con archivo y línea)

**Identidad/versión** (LicenseConfig.java):
- L13 `SAMURAI` (BRAND) · L14 `V1.3` (VERSION) · LoginScreenKt L507 `SAMURAI • V1.3`

**Persistencia/Keystore** (LicenseAuth.java):
- L45 `samurai_license` (PREFS) · L46 `license_key` (KEY_LICENSE) · L47 `AndroidKeyStore` (KEYSTORE) · L48 `samurai_license_key_v1` (KEY_ALIAS) · L83/107 `AES/GCM/NoPadding`

**Mensajes de licencia** (LicenseAuth.java / LoginScreenKt):
- L237 `Enter your license key` (hint) · L257 `Login service unavailable. Merge libsamurai.so and retry.` · L273 `Login failed` · L279 `Login succeeded but no active session` · L287 `Login failed (bad server reply)` · L262 `success`, L263 `message`, L269 `error_code` (campos de respuesta JSON del login) · LoginScreenKt L510 `Welcome back`, L512 `Enter your license key to continue`, L515 `LICENSE KEY` · ModMenuScreenKt L450/474 `License expired`, L8324-8326 `ACTIVE | PREMIUM ACCESS`, L8372 `ACCESS EXPIRES IN`, L33040 `Lifetime`

**Nativo/config** (Constants.java / PwfNative.java):
- L12 `libsamurai.so` (NON_ROOT_LIBRARY_NAME) · L13 `com.miniclip.eightballpool` (TARGET_GAME_PACKAGE) · PwfNative L105 `samurai` (lib), L113 `PwfNative`/`Failed to load libsamurai.so`, L288 `orljmgpg failed`, L152 `seller`/`success` (parse respuesta login)

**URLs externas**:
- ModMenuScreenKt L27848 `https://t.me/Samurai_8BP` (Telegram oficial del mod)
- GoogleSignInWebViewActivity L262 `https://accounts.google.com/o/oauth2/v2/auth`; L130 `https://localhost/?` (redirect OAuth); L25/235 `697261581904-997ch5oh85im8rcq2lt172jbu92gjha6.apps.googleusercontent.com`
- GoogleSignInHelper L37 `https://api-project-697261581904.firebaseapp.com/__/auth/handler` (handler Firebase del proyecto 697261581904 = el OAuth client real de 8 Ball Pool)
- Descarga de skins: raíz = `PwfNative.assetSourceRoot()` (nativo), catálogos `web73372-layout1` / `web73372-cues-v1` (CDN web de Miniclip)

**Overlay/infra**:
- InGameModMenuController L44 `samurai_in_game_mod_menu` (tag de la vista), TAG `InGameModMenu`, `Unable to create the in-game menu view`; decoys de log `SamuraiGoogleSignIn` / `SamuraiFacebookLogin` con mensajes falsos tipo `[GSI] bootstrap-enter build=gsi-sdkpair-v3`.

**Catálogos**: 17 mesas M1-M17 (100→200M), 9 apuestas 9-ball, 14 trails, 7+1 impactos, 7+1 cushion, 4+1 pocket FX, 18 mesas y decenas de cues (`tableMonaco-hd.png`, `Table_Archon_Cue-hd.png`...).

Tabla completa (3.151 strings): `re/analysis/stringfog_strings.txt`.

---

## 6. Hallazgos inesperados / riesgos

1. **Google Sign-In sustituido por implementación propia del mod** (`com.samurai.vengine.app`):
   - `GoogleSignInHooks::install` engancha el binder `android.credentials.ICredentialManager` del Credential Manager y **intercepta** las peticiones del juego ("[GSI] framework-intercepted oauthClientSource=sdk-reference"), usando el client_id REAL de Miniclip `697261581904-997ch5oh85im8rcq2lt172jbu92gjha6.apps.googleusercontent.com`.
   - `GoogleSignInWebViewActivity` abre `accounts.google.com/o/oauth2/v2/auth` en un **WebView embebido** (los IDs de Google normalmente prohíben user-agents embebidos → maneja `disallowed_useragent`, `redirect_uri_mismatch`, etc.), redirect a `https://localhost/?...` y extrae el `id_token`.
   - `GoogleSignInHelper` valida el JWT (aud, nonce, issuer, exp — "token-rejected"/"token-validated") y lo reinyecta al juego como `android.credentials.Credential`/`SignInCredential` ("framework-response-dispatched backendAcceptance=unverified").
   - `GoogleSignInInstrumentation` hookea `execStartActivity`. `FacebookWebLogin` fuerza `WEB_VIEW_ONLY` en el SDK de Facebook.
   - **Riesgo**: el flujo OAuth pasa por el WebView del mod; el token llega al juego de Miniclip (backend "unverified" en el log). Es para que el login funcione en APK re-firmado, pero implica que el mod toca credenciales de la cuenta Google del usuario.
2. **Decoys de log**: logs con tags imitando SDKs reales (`[GSI] bootstrap-enter build=gsi-sdkpair-v3`, `[FB] bootstrap-enter strategy=facebook-sdk-webview`) para camuflar la instrumentación.
3. **Anti-análisis menor**: strings XOR (StringFog), nombres JNI ofuscados, y 4 claves de config con bytes corruptos intencionales o bug del packer (`bAutoPlay_MultiPocgkets`, `bAutoPgy`, `bAutoPlaltiPock`, `iMenuScaleSetr`) — deben existir tal cual en el .so (parchear Java sin conocerlas rompería el match de claves).
4. **Sin telemetría propia detectada en Java**: no hay URLs de telemetría del modder salvo el Telegram; la validación de licencia y la descarga de skins salen por `PwfNative`/libsamurai.so (recomendado confirmar en análisis del .so qué servidor valida la licencia — `PwfNative.login` → JNI `orljmgpg`).
5. `bAntiCapture` (anti-captura de pantalla) existe en el puente pero sin toggle UI en 1.3.0 — potencialmente activable remotamente por el vendedor de licencias vía snapshot nativo.
6. El botón de autoplay y `setUserInfo*` (cambiar nombre/monedas/nivel mostrados) revelan que la parte nativa tiene más capacidades de las que expone la UI actual.

---

## 7. Anexo — flujo completo resumido

```
Application.onCreate (proceso del juego)
 └─ InGameModMenuController.install(app)
     ├─ FacebookWebLogin.configure / GoogleSignInHooks.install
     └─ registerActivityLifecycleCallbacks
         └─ onActivityCreated(com.miniclip.eightballpool.*)
             └─ ComposeView(tag="samurai_in_game_mod_menu")
                 + EmbeddedViewTreeOwner (lifecycle sintético)
                 + setContent { Theme { ModMenuScreen(connectNative=true) } }
                 + addView(android.R.id.content, MATCH_PARENT)  ← overlay
                 + show tras 2000 ms

ModMenuScreen
 ├─ LaunchedEffect: syncFromNative() (retry 500 ms) + snapshotFlow→apply()
 ├─ LaunchedEffect: sessionEnded.collect → authenticated=false, notice
 ├─ LaunchedEffect(menuOpen): fetchUserInfo cada 10 s
 ├─ MenuBody: cada 5 s loggedIn = isSignedIn() && !isLicenseExpired()
 │            + countdown expirySecondsRemaining() → "License expired"
 └─ if (!loggedIn) LoginScreen
      └─ submit → LicenseAuth.verify → PwfNative.login(orljmgpg, libsamurai.so)
                  ├─ OK  → save prefs (AES/GCM + Keystore) → loggedIn=true
                  └─ FAIL → error
```
