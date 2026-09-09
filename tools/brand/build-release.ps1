# Build the signed RELEASE APK for Seeker Gravity (Godot 3.6.1).
#
#   powershell -ExecutionPolicy Bypass -File C:\Users\justi\Desktop\games\rota\tools\brand\build-release.ps1
#
# Godot 3 has no environment-variable keystore override (that arrived in Godot 4.2), and we will not
# put your password into export_presets.cfg. So the export is signed with the public Android DEBUG
# key first, then re-signed in place with your release keystore by apksigner, which asks for the
# password on the terminal and never writes it anywhere.
#
# Output: build\android\seeker-gravity-release.apk  (also copied to web\static\game.apk)

param(
    [string]$GodotBin = 'C:\Users\justi\godot3\Godot_v3.6.1-stable_win64.exe',
    [string]$Keystore = '',
    [string]$Alias = 'seekergravity',
    [string]$BuildTools = 'C:\Users\justi\AppData\Local\Android\Sdk\build-tools\35.0.0',
    [switch]$SkipWebCopy,
    [switch]$SignOnly   # skip the 2-minute export, just (re-)sign build/android/seeker-gravity-release.apk
)

$ErrorActionPreference = 'Stop'
# Windows PowerShell 5.1 writes UTF-8 WITH a BOM; Godot's parsers reject that ("Expected '['", no presets found).
function Write-Utf8NoBom([string]$Path, [string]$Text) { [System.IO.File]::WriteAllText($Path, $Text, (New-Object System.Text.UTF8Encoding($false))) }
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if ([string]::IsNullOrWhiteSpace($Keystore)) {
    $Keystore = Join-Path $projectRoot (Join-Path 'keys' 'seeker-gravity-release.keystore')
}
$outApk = Join-Path $projectRoot (Join-Path 'build' (Join-Path 'android' 'seeker-gravity-release.apk'))
$debugKeystore = Join-Path (Join-Path $env:APPDATA 'Godot') (Join-Path 'keystores' 'debug.keystore')
$sharedDebugKeystore = 'C:\Users\justi\godot3\keys\debug.keystore'

if (-not (Test-Path $GodotBin)) { throw "Godot 3.6.1 not found: $GodotBin" }
if (-not (Test-Path $Keystore)) {
    throw "Release keystore not found: $Keystore`nRun tools\brand\new-release-key.ps1 first."
}

# --- preflight: Godot 3 export templates must be on THIS user's disk --------------------------
$templateDir = Join-Path (Join-Path (Join-Path $env:APPDATA 'Godot') 'templates') '3.6.1.stable'
foreach ($name in @('android_debug.apk', 'android_release.apk')) {
    $t = Join-Path $templateDir $name
    if (-not (Test-Path $t)) {
        throw "Godot 3.6.1 export template missing: $t`nCopy C:\Users\justi\godot3\templates\templates\android_*.apk and version.txt into $templateDir and run again."
    }
}
if (-not (Test-Path $debugKeystore)) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $debugKeystore) | Out-Null
    Copy-Item $sharedDebugKeystore $debugKeystore
    Write-Host "  installed debug keystore -> $debugKeystore" -ForegroundColor DarkGray
}

# --- gradle build preflight (1.3.0+: the export runs Godot's gradle build so the SeekerWallet plugin is compiled in) --
$buildVersion = Join-Path (Join-Path $projectRoot 'android') '.build_version'
if (-not (Test-Path $buildVersion)) { throw "Android build template not installed (android/.build_version missing). Unzip C:/Users/justi/godot3/templates/templates/android_source.zip into android/build and write 3.6.1.stable (no newline) into android/.build_version, or use Project > Install Android Build Template in the editor." }
$pluginAar = Join-Path (Join-Path (Join-Path $projectRoot 'android') 'plugins') 'SeekerWallet.aar'
if (-not (Test-Path $pluginAar)) { throw "android/plugins/SeekerWallet.aar missing - run tools/brand/build-plugin.ps1 first." }
if (-not $env:JAVA_HOME) { throw 'JAVA_HOME is not set (the gradle build needs a JDK 17).' }
Write-Host "  gradle build: template $((Get-Content $buildVersion).Trim()), plugin $([math]::Round((Get-Item $pluginAar).Length / 1KB)) KB, JAVA_HOME=$env:JAVA_HOME" -ForegroundColor DarkGray

# --- version ---------------------------------------------------------------------------------------
$presets = Get-Content -Raw (Join-Path $projectRoot 'export_presets.cfg')
$versionCode = [Regex]::Match($presets, '^version/code=(\d+)\s*$', 'Multiline').Groups[1].Value
$versionName = [Regex]::Match($presets, '^version/name="([^"]+)"\s*$', 'Multiline').Groups[1].Value
Write-Host "Building Seeker Gravity $versionName ($versionCode)" -ForegroundColor Cyan

if ($SignOnly) {
    if (-not (Test-Path $outApk)) { throw "-SignOnly: nothing to sign, $outApk does not exist - run without -SignOnly first." }
    Write-Host "SignOnly: skipping the export, re-signing $outApk" -ForegroundColor Cyan
}
else {
    # --- editor settings: SDK path + debug keystore (Godot 3 reads these from editor_settings-3.tres) --
    # Written from scratch every run: a hand-patched file from an earlier attempt can be unparsable
    # ("Parse Error: Expected '['"), which makes Godot fall back to an EMPTY debug keystore path and the
    # export dies with "Could not find keystore". Nothing else in this file matters for a headless export.
    $editorSettings = Join-Path (Join-Path $env:APPDATA 'Godot') 'editor_settings-3.tres'
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $editorSettings) | Out-Null
    if (Test-Path $editorSettings) { Copy-Item $editorSettings "$editorSettings.bak" -Force }
    $es = @(
        '[gd_resource type="EditorSettings" format=2]',
        '',
        '[resource]',
        ('export/android/java_sdk_path = "' + ($env:JAVA_HOME -replace '\\', '/') + '"'),
        'export/android/android_sdk_path = "C:/Users/justi/AppData/Local/Android/Sdk"',
        ('export/android/debug_keystore = "' + ($debugKeystore -replace '\\', '/') + '"'),
        'export/android/debug_keystore_user = "androiddebugkey"',
        'export/android/debug_keystore_pass = "android"'
    ) -join "`n"
    Write-Utf8NoBom $editorSettings ($es + "`n")

    # --- export (release template, debug-signed for now) ----------------------------------------------
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $outApk) | Out-Null
    $presetPath = Join-Path $projectRoot 'export_presets.cfg'
    $backup = Get-Content -Raw $presetPath
    $patched = $backup
    $patched = $patched -replace '(?m)^keystore/release=.*$',          ('keystore/release="' + ($debugKeystore -replace '\\', '/') + '"')
    $patched = $patched -replace '(?m)^keystore/release_user=.*$',     'keystore/release_user="androiddebugkey"'
    $patched = $patched -replace '(?m)^keystore/release_password=.*$', 'keystore/release_password="android"'
    # The gradle build ends with a Copy task (copyAndRenameReleaseApk) that drops the APK into the output
    # directory. Gradle skips that task as UP-TO-DATE when the freshly built APK is byte-identical to the
    # previous build AND the output directory looks unchanged - the requested file name is not one of its
    # inputs, so the export "succeeds" and no file appears (bit us on 2026-09-05). A never-seen directory
    # per run defeats the check; the APK is then moved to its final name.
    $exportDir = Join-Path (Split-Path -Parent $outApk) ('export-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    New-Item -ItemType Directory -Force -Path $exportDir | Out-Null
    $exportApk = Join-Path $exportDir (Split-Path -Leaf $outApk)
    try {
        Write-Utf8NoBom $presetPath $patched
        # Godot's Windows build is a GUI-subsystem exe: the call operator (&) would return at once while
        # Godot keeps running in the background, this script would then "see" no APK and restore the preset
        # under Godot's feet (Godot then reads an empty release keystore -> "Could not find keystore").
        # Start-Process -Wait blocks until the export has really finished.
        $godotArgs = @('--no-window', '--path', ('"' + $projectRoot + '"'), '--export', 'Android', ('"' + $exportApk + '"'))
        $godot = Start-Process -FilePath $GodotBin -ArgumentList $godotArgs -Wait -NoNewWindow -PassThru
        Write-Host "  godot exited with code $($godot.ExitCode)" -ForegroundColor DarkGray
        if (-not (Test-Path $exportApk)) { throw 'Godot export produced no APK - scroll up for the error.' }
        if (Test-Path $outApk) { Remove-Item $outApk -Force }
        Move-Item $exportApk $outApk
    }
    finally {
        Write-Utf8NoBom $presetPath $backup
        Remove-Item $exportDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# --- re-sign with YOUR release key (apksigner prompts for the password) ---------------------------
Write-Host ''
Write-Host "Re-signing with $Keystore (alias $Alias). apksigner will ask for the password:" -ForegroundColor Cyan
$signed = $false
for ($attempt = 1; $attempt -le 3 -and -not $signed; $attempt++) {
    if ($attempt -gt 1) { Write-Host "Password rejected. Try again ($attempt/3)..." -ForegroundColor Yellow }
    & (Join-Path $BuildTools 'apksigner.bat') sign --ks $Keystore --ks-key-alias $Alias --v1-signing-enabled true --v2-signing-enabled true $outApk
    if ($LASTEXITCODE -eq 0) { $signed = $true }
}
if (-not $signed) {
    throw ("apksigner rejected the keystore password 3 times. The exported APK is still at $outApk (signed with the debug key only).`n" +
           "  Check the password yourself:  keytool -list -keystore $Keystore`n" +
           "  Then re-sign without rebuilding:  build-release.ps1 -SignOnly`n" +
           "  Password lost and nothing published yet? Rename the keystore file, run new-release-key.ps1, then build-release.ps1 -SignOnly")
}

Write-Host ''
Write-Host 'Verifying...' -ForegroundColor Cyan
& (Join-Path $BuildTools 'apksigner.bat') verify --print-certs $outApk
& (Join-Path $BuildTools 'aapt.exe') dump badging $outApk | Select-String -Pattern "^package:|application-label:'|native-code:|targetSdk"
& (Join-Path $BuildTools 'aapt.exe') dump permissions $outApk

if (-not $SkipWebCopy) {
    $webStatic = Join-Path (Split-Path -Parent $projectRoot) (Join-Path 'heli' (Join-Path 'web' 'static-gravity'))
    if (Test-Path $webStatic) {
        Copy-Item $outApk (Join-Path $webStatic 'game.apk') -Force
        Write-Utf8NoBom (Join-Path $webStatic 'version.txt') "$versionName`n"
        Write-Host "Copied to heli\web\static-gravity\game.apk (download site; commit + push heli\web to publish)" -ForegroundColor Green
    }
}

$sizeMb = [math]::Round((Get-Item $outApk).Length / 1MB, 1)
Write-Host ''
Write-Host "READY: $outApk  ($sizeMb MB)" -ForegroundColor Green
