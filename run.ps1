# Ежедневный запуск отчёта (для Планировщика заданий Windows)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Создаю venv…"
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
}

& .\.venv\Scripts\python.exe .\main.py @args
exit $LASTEXITCODE
