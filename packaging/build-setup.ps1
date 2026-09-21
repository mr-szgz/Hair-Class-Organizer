#Requires -Version 7.0
param(
    [string]$IsccPath = "$env:LOCALAPPDATA/Programs/Inno Setup 6/ISCC.exe"
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
Set-Location (Split-Path $PSScriptRoot -Parent)
$version = (Select-String -Path pyproject.toml -Pattern '^version = "(.+)"$').Matches.Groups[1].Value
$uvVersion = "0.11.11"
$uvSha256 = "2f75a0db2c3530b6b3c24434dc38137f61ff1f4e5f2d7b4ddc5bcd142cf58b65"
New-Item -ItemType Directory -Force build/bootstrap | Out-Null
Invoke-WebRequest "https://github.com/astral-sh/uv/releases/download/$uvVersion/uv-x86_64-pc-windows-msvc.zip" -OutFile build/bootstrap/uv.zip
certutil -hashfile build/bootstrap/uv.zip SHA256 | findstr /I /C:$uvSha256 | Out-Null
Expand-Archive -LiteralPath build/bootstrap/uv.zip -DestinationPath build/bootstrap/uv -Force
Invoke-WebRequest "https://raw.githubusercontent.com/astral-sh/uv/$uvVersion/LICENSE-MIT" -OutFile build/bootstrap/LICENSE-MIT
Invoke-WebRequest "https://raw.githubusercontent.com/astral-sh/uv/$uvVersion/LICENSE-APACHE" -OutFile build/bootstrap/LICENSE-APACHE
& build/bootstrap/uv/uv.exe lock --check
& $IsccPath "/DAppVersion=$version" packaging/installer.iss
