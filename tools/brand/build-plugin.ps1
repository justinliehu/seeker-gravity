# Rebuild the SeekerWallet Godot 3 Android plugin (in-app Seeker wallet payment) and install it
# into android/plugins/ where the export preset picks it up (plugins/SeekerWallet=true).
#
# Only needed after editing tools/seekerwallet-plugin/src/**. The exported APK is built by Godot's
# gradle build (custom_build/use_custom_build=true), which pulls the MWA client library listed in
# android/plugins/SeekerWallet.gdap from Maven Central.
#
# Needs: JDK 17 (JAVA_HOME), Android SDK at %LOCALAPPDATA%\Android\Sdk, internet for Maven.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$plugin = Join-Path (Join-Path $root 'tools') 'seekerwallet-plugin'
$sdk = Join-Path (Join-Path $env:LOCALAPPDATA 'Android') 'Sdk'

if (-not $env:JAVA_HOME) { throw 'JAVA_HOME is not set (needs a JDK 17).' }
if (-not (Test-Path $sdk)) { throw "Android SDK not found: $sdk" }
Set-Content -Path (Join-Path $plugin 'local.properties') -Value ('sdk.dir=' + ($sdk -replace '\\', '/')) -Encoding ascii

# godot-lib classes for compiling against the plugin API (extracted from the installed build template)
$aar = Join-Path (Join-Path (Join-Path (Join-Path $root 'android') 'build') 'libs') 'release'
$aar = Join-Path $aar 'godot-lib.release.aar'
if (-not (Test-Path $aar)) { throw "Android build template not installed ($aar missing). In the Godot editor: Project > Install Android Build Template, or unzip android_source.zip into android/build." }
$libs = Join-Path $plugin 'libs'
New-Item -ItemType Directory -Force -Path $libs | Out-Null
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($aar)
try {
    $entry = $zip.GetEntry('classes.jar')
    [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, (Join-Path $libs 'godot-lib-release-classes.jar'), $true)
} finally { $zip.Dispose() }

Write-Host 'Building SeekerWallet.aar (gradle)...' -ForegroundColor Cyan
& (Join-Path $plugin 'gradlew.bat') -p $plugin assembleRelease --no-daemon -q
if ($LASTEXITCODE -ne 0) { throw 'gradle failed - scroll up for the error.' }

$out = Join-Path (Join-Path (Join-Path (Join-Path $plugin 'build') 'outputs') 'aar') 'SeekerWallet.aar'
$dest = Join-Path (Join-Path (Join-Path $root 'android') 'plugins') 'SeekerWallet.aar'
Copy-Item $out $dest -Force
Write-Host "Installed $dest ($([math]::Round((Get-Item $dest).Length / 1KB)) KB)" -ForegroundColor Green
