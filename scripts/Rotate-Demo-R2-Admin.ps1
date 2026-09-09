[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

# 脚本用途：为独立 Demo R2 创建可通过 EmailStr 校验的新管理员，并安全更新本地私有凭据。
$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$EnvironmentFile = Join-Path $RepositoryRoot '.env.demo-r2'
$CredentialFile = Join-Path $RepositoryRoot 'data\demo-r2\private\demo-admin-credentials.txt'
$AdminEmail = 'demo.admin@example.com'
$AdminDisplayName = 'Demo R2 Administrator'
$AdminPassword = 'Jh9!' + [Guid]::NewGuid().ToString('N') + 'R2'

function Write-Utf8NoBom {
    <# 输入：Path 为文件路径，Content 为完整内容。输出：无；以 UTF-8 无 BOM 原子写入。 #>
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [string]$Content
    )
    $TemporaryPath = "$Path.rotate-admin-tmp"
    [IO.File]::WriteAllText($TemporaryPath, $Content, [Text.UTF8Encoding]::new($false))
    Move-Item -Force -LiteralPath $TemporaryPath -Destination $Path
}

if (-not (Test-Path -LiteralPath $EnvironmentFile)) {
    throw '独立 Demo 环境文件不存在。'
}

# 明文密码只在当前进程和私有忽略文件中存在，不出现在命令参数或输出。
$env:BOOTSTRAP_ADMIN_EMAIL = $AdminEmail
$env:BOOTSTRAP_ADMIN_PASSWORD = $AdminPassword
$env:BOOTSTRAP_ADMIN_DISPLAY_NAME = $AdminDisplayName
$ComposeArguments = @(
    'compose', '--env-file', $EnvironmentFile,
    '-p', 'junhui-demo-r2',
    '-f', (Join-Path $RepositoryRoot 'docker-compose.yml'),
    '-f', (Join-Path $RepositoryRoot 'docker-compose.demo-r2.yml'),
    'run', '--rm', '--no-deps',
    '-e', 'BOOTSTRAP_ADMIN_EMAIL',
    '-e', 'BOOTSTRAP_ADMIN_PASSWORD',
    '-e', 'BOOTSTRAP_ADMIN_DISPLAY_NAME',
    'api', 'python', '-m', 'app.cli', 'create-super-admin'
)
$BootstrapOutput = & docker @ComposeArguments 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Demo 管理员创建失败：$($BootstrapOutput -join ' ')"
}

$EnvironmentText = [IO.File]::ReadAllText($EnvironmentFile)
$EnvironmentText = [regex]::Replace(
    $EnvironmentText,
    '(?m)^BOOTSTRAP_ADMIN_EMAIL=.*$',
    "BOOTSTRAP_ADMIN_EMAIL=$AdminEmail",
    1
)
$EnvironmentText = [regex]::Replace(
    $EnvironmentText,
    '(?m)^BOOTSTRAP_ADMIN_PASSWORD=.*$',
    "BOOTSTRAP_ADMIN_PASSWORD=$AdminPassword",
    1
)
$EnvironmentText = [regex]::Replace(
    $EnvironmentText,
    '(?m)^BOOTSTRAP_ADMIN_DISPLAY_NAME=.*$',
    "BOOTSTRAP_ADMIN_DISPLAY_NAME=$AdminDisplayName",
    1
)
Write-Utf8NoBom -Path $EnvironmentFile -Content ($EnvironmentText.TrimEnd() + "`r`n")

$CredentialText = @(
    '# Demo R2 本地后台凭据（私有，不得提交或进入证据包）',
    'URL=https://admin-demo.junhuiscrewbarrel.com/',
    "EMAIL=$AdminEmail",
    "PASSWORD=$AdminPassword"
) -join "`r`n"
Write-Utf8NoBom -Path $CredentialFile -Content ($CredentialText + "`r`n")

$env:BOOTSTRAP_ADMIN_PASSWORD = $null
$AdminPassword = $null
Write-Host "DEMO_ADMIN_ROTATED email=$AdminEmail credentials=$CredentialFile"
