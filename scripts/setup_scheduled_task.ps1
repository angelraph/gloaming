# Registers the Windows Scheduled Task that runs Gloaming Agent unattended.
#
# Fires every 15 minutes, 24/7 - agent_loop.py's run_once() checks
# is_nyse_closed() itself on every invocation and silently no-ops the hours the
# real market is open, so there is no need to encode NYSE hours into the trigger
# itself. All paths inside agent_loop.py are resolved from __file__, so the
# task's working directory does not matter.
#
# IMPORTANT - what this can and cannot survive:
#   - Sleep:    SURVIVED. WakeToRun below wakes the machine for each firing.
#   - Shutdown: NOT survived. A fully powered-off PC cannot run anything local,
#               scheduled or otherwise. Keep this machine powered on (sleep is
#               fine) for the ~2-week log to stay continuous.
#   - Missed firing (PC briefly off despite the above): StartWhenAvailable
#     below catches it up as soon as the PC is back, instead of silently
#     skipping until the next 15-minute mark.
#
# Re-run this script any time to update the task (it replaces the existing one).
# To remove it: Unregister-ScheduledTask -TaskName GloamingAgentLoop -Confirm:$false

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot "engine\.venv\Scripts\python.exe"
$Script = Join-Path $RepoRoot "gloaming_agent\agent_loop.py"
$TaskName = "GloamingAgentLoop"

if (-not (Test-Path $Python)) {
    Write-Error "Python venv not found at $Python - run engine setup first."
    exit 1
}

$ScriptArg = '"' + $Script + '" --run'
$Action = New-ScheduledTaskAction -Execute $Python -Argument $ScriptArg -WorkingDirectory $RepoRoot

# TimeSpan]::MaxValue produces a duration string Task Scheduler's XML schema
# rejects outright - 10 years is effectively indefinite for a hackathon and
# stays within the valid range.
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration (New-TimeSpan -Days 3650)

$Settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Gloaming Agent off-hours rToken paper-trading loop. Self-gates on NYSE hours internally." -ErrorAction Stop | Out-Null

Write-Host "Scheduled task $TaskName created - fires every 15 minutes, wakes the PC from sleep."
Write-Host "Check status:  Get-ScheduledTaskInfo -TaskName $TaskName"
Write-Host "View activity: Get-Content $RepoRoot\gloaming_agent\scheduler.log -Tail 20"
Write-Host "Remove it:     Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
