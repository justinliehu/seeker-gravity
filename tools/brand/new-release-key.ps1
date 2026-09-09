# Create the Seeker Gravity RELEASE signing key. Run this once, yourself.
#
#   powershell -ExecutionPolicy Bypass -File C:\Users\justi\Desktop\games\rota\tools\brand\new-release-key.ps1
#
# keytool asks you for a password - pick one, type it here, and BACK IT UP together with the file.
# Losing either means you can never publish an update to com.justinliehu.seekergravity again.
# The keystore is written to keys\seeker-gravity-release.keystore (gitignored).

param(
    [string]$Alias = 'seekergravity',
    [int]$ValidityDays = 10000
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$keyDir = Join-Path $projectRoot 'keys'
$keystore = Join-Path $keyDir 'seeker-gravity-release.keystore'

if (Test-Path $keystore) {
    Write-Host "A keystore already exists at $keystore - refusing to overwrite (that would break app updates)." -ForegroundColor Yellow
    exit 1
}
New-Item -ItemType Directory -Force -Path $keyDir | Out-Null

$keytool = 'keytool'
if (-not (Get-Command $keytool -ErrorAction SilentlyContinue)) {
    $found = Get-Item "${env:ProgramFiles}\Eclipse Adoptium\jdk-17*\bin\keytool.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $found) { throw 'keytool not found. Install a JDK 17 or add keytool to PATH.' }
    $keytool = $found.FullName
}

Write-Host ''
Write-Host 'Creating the RELEASE keystore. keytool will ask for a password, then name/org/city/country,' -ForegroundColor Cyan
Write-Host 'then "ja"/"y" to confirm, then Enter to reuse the password for the key.'
Write-Host ''
& $keytool -genkeypair -v -keystore $keystore -alias $Alias -keyalg RSA -keysize 2048 -validity $ValidityDays
if ($LASTEXITCODE -ne 0) { throw "keytool failed with exit code $LASTEXITCODE" }

Write-Host ''
Write-Host "Created: $keystore  (alias: $Alias)" -ForegroundColor Green
Write-Host 'BACK THIS FILE UP NOW, together with the password.' -ForegroundColor Yellow
Write-Host 'Next:  powershell -ExecutionPolicy Bypass -File C:\Users\justi\Desktop\games\rota\tools\brand\build-release.ps1'
