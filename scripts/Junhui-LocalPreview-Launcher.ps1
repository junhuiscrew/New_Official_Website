[CmdletBinding()]
param(
    [ValidateSet('Setup', 'Start', 'Status', 'Stop', 'Restore', 'RepairProxy')]
    [string]$Action = 'Status',
    [switch]$NoOpen,
    [switch]$NoElevation
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$mainScriptPath = Join-Path $repositoryRoot 'scripts\Junhui-LocalPreview.ps1'
$env:JUNHUI_LOCAL_PREVIEW_ROOT = $repositoryRoot
$env:JUNHUI_LOCAL_PREVIEW_LAUNCHER = 'system-powershell-utf8-launcher'

# Read the UTF-8 main script explicitly so Windows PowerShell 5.1 can execute it reliably.
$mainScriptText = [IO.File]::ReadAllText($mainScriptPath, [Text.Encoding]::UTF8)
$mainScript = [ScriptBlock]::Create($mainScriptText)
try {
    & $mainScript -Action $Action -NoOpen:$NoOpen -NoElevation:$NoElevation
} catch {
    $stateRoot = Join-Path $repositoryRoot 'data\phase3-7\local-domain-state'
    New-Item -ItemType Directory -Force -Path $stateRoot | Out-Null
    $errorPath = Join-Path $stateRoot 'last-launch-error.txt'
    [IO.File]::WriteAllText($errorPath, ((Get-Date).ToString('o') + ' ' + $_.Exception.Message), [Text.Encoding]::UTF8)
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(
        "Junhui local preview failed to start. See:`n$errorPath",
        'Junhui Local Preview'
    ) | Out-Null
    exit 1
}
