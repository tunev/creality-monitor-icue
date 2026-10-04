# Validates and packs CrealityMonitor_Template into an .icuewidget file
# for import into iCUE, using the official iCUE Widget CLI.
# Usage:  powershell -ExecutionPolicy Bypass -File .\pack.ps1
#
# Requires: npm install -g icuewidget-cli

$ErrorActionPreference = 'Stop'

$root     = Split-Path -Parent $MyInvocation.MyCommand.Path
$template = Join-Path $root 'CrealityMonitor_Template'
$version  = (Get-Content (Join-Path $template 'manifest.json') -Raw | ConvertFrom-Json).version
$outName  = "CrealityMonitor-v$version"
$widget   = Join-Path $root "$outName.icuewidget"

if (-not (Test-Path $template)) { throw "Missing folder: $template" }
if (-not (Get-Command icuewidget -ErrorAction SilentlyContinue)) {
    throw "icuewidget CLI not found. Install it with: npm install -g icuewidget-cli"
}

Remove-Item $widget -ErrorAction SilentlyContinue

icuewidget validate $template
icuewidget package $template

# icuewidget names the output after the widget's slugified name; rename it
# to the versioned filename this script (and the repo) expects.
$produced = Get-ChildItem -Path $root -Filter '*.icuewidget' |
    Where-Object { $_.Name -ne "$outName.icuewidget" -and $_.LastWriteTime -ge (Get-Date).AddMinutes(-1) } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if ($produced) { Move-Item $produced.FullName $widget -Force }

Write-Host "Done: $widget" -ForegroundColor Green
Write-Host "Import it in iCUE -> Xeneon Edge -> Add Widget -> Import." -ForegroundColor Gray
