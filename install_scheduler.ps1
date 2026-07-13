# Регистрация ежедневной задачи в Планировщике Windows (09:00 по умолчанию)
param(
    [string]$Time = "09:00",
    [string]$TaskName = "GitDailyReportBot"
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$script = Join-Path $root "run.ps1"

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`"" `
    -WorkingDirectory $root

$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force |
    Out-Null

Write-Host "Задача '$TaskName' зарегистрирована. Ежедневно в $Time."
Write-Host "Перед этим заполни config.yaml (токен бота и chat_id)."
