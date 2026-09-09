[CmdletBinding()]
param(
    [ValidateSet('Setup', 'Start', 'Status', 'Stop', 'Restore')]
    [string]$Action = 'Status',
    [switch]$NoOpen,
    [switch]$NoElevation
)

$ErrorActionPreference = 'Stop'
$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$MainScriptPath = Join-Path $RepositoryRoot 'scripts\Junhui-Demo-R2.ps1'
$env:JUNHUI_DEMO_R2_ROOT = $RepositoryRoot

# Read the UTF-8 main script explicitly for Windows PowerShell 5.1.
$MainScriptText = [IO.File]::ReadAllText($MainScriptPath, [Text.Encoding]::UTF8)
$MainScript = [ScriptBlock]::Create($MainScriptText)
try {
    # Forward switches through a plain hashtable for Windows PowerShell 5.1.
    $InvocationParameters = @{
        Action = [string]$Action
        NoOpen = [bool]$NoOpen
        NoElevation = [bool]$NoElevation
    }
    & $MainScript @InvocationParameters
} catch {
    $StateRoot = Join-Path $RepositoryRoot 'data\demo-r2\local-domain-state'
    New-Item -ItemType Directory -Force -Path $StateRoot | Out-Null
    $ErrorPath = Join-Path $StateRoot 'last-launch-error.txt'
    [IO.File]::WriteAllText(
        $ErrorPath,
        ((Get-Date).ToString('o') + ' ' + $_.Exception.Message),
        [Text.Encoding]::UTF8
    )
    Write-Error "Junhui Demo R2 failed. Details: $ErrorPath"
    exit 1
}
