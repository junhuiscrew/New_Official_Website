param(
    [switch]$InstallTrustAndHosts
)

$ErrorActionPreference = 'Stop'

# 脚本用途：生成 Phase 3.7 隔离环境的随机凭据、本地 CA、三域名证书和 Basic Auth 文件。
$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$PrivateRoot = Join-Path $RepositoryRoot 'data\phase3-7'
$TlsRoot = Join-Path $PrivateRoot 'tls'
$AuthRoot = Join-Path $PrivateRoot 'auth'
$EnvironmentFile = Join-Path $RepositoryRoot '.env.phase37'
$OpenSsl = (Get-Command openssl -ErrorAction Stop).Source

New-Item -ItemType Directory -Force -Path $TlsRoot, $AuthRoot | Out-Null

function New-Phase37Secret {
    <#
    生成不含 URL 保留字符的随机 Secret。

    输入：无。
    输出：string，64 位小写十六进制随机值。
    #>
    $Bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($Bytes)
    return [Convert]::ToHexString($Bytes).ToLowerInvariant()
}

function New-Phase37AdminPassword {
    <#
    生成满足既有管理员密码强度门禁的随机密码。

    输入：无。
    输出：string，包含大小写字母、数字和特殊字符的随机值。
    #>
    return "Jh9!$(New-Phase37Secret)"
}

if (-not (Test-Path -LiteralPath $EnvironmentFile)) {
    $DatabasePassword = New-Phase37Secret
    $MinioSecret = New-Phase37Secret
    $AdminPassword = New-Phase37AdminPassword
    $BasicPassword = New-Phase37Secret
    $EnvironmentLines = @(
        'POSTGRES_DB=junhui_phase37'
        'POSTGRES_USER=junhui_phase37'
        "POSTGRES_PASSWORD=$DatabasePassword"
        "DATABASE_URL=postgresql+asyncpg://junhui_phase37:$DatabasePassword@postgres:5432/junhui_phase37"
        'MINIO_ACCESS_KEY=phase37-local-admin'
        "MINIO_SECRET_KEY=$MinioSecret"
        "JWT_SIGNING_SECRET=$(New-Phase37Secret)"
        "REFRESH_TOKEN_SECRET=$(New-Phase37Secret)"
        'CORS_ALLOWED_ORIGINS=["https://junhui.test","https://admin.junhui.test","https://api.junhui.test"]'
        'PHASE37_BASIC_USER=phase37-review'
        "PHASE37_BASIC_PASSWORD=$BasicPassword"
        'PHASE37_ADMIN_EMAIL=phase37-review@example.com'
        "PHASE37_ADMIN_PASSWORD=$AdminPassword"
        'PHASE37_ADMIN_DISPLAY_NAME=Phase 3.7 Local Reviewer'
        'PHASE37_CA_CERT=/workspace/data/phase3-7/tls/ca.crt'
    )
    Set-Content -LiteralPath $EnvironmentFile -Value $EnvironmentLines -Encoding utf8NoBOM
}

$CertificateConfig = Join-Path $TlsRoot 'server.cnf'
$CertificateConfigLines = @(
    '[req]'
    'prompt = no'
    'distinguished_name = subject'
    'req_extensions = extensions'
    '[subject]'
    'CN = junhui.test'
    '[extensions]'
    'subjectAltName = @alternate_names'
    '[alternate_names]'
    'DNS.1 = junhui.test'
    'DNS.2 = admin.junhui.test'
    'DNS.3 = api.junhui.test'
)
Set-Content -LiteralPath $CertificateConfig -Value $CertificateConfigLines -Encoding ascii

$CaKey = Join-Path $TlsRoot 'ca.key'
$CaCertificate = Join-Path $TlsRoot 'ca.crt'
$ServerKey = Join-Path $TlsRoot 'server.key'
$ServerRequest = Join-Path $TlsRoot 'server.csr'
$ServerCertificate = Join-Path $TlsRoot 'server.crt'

if (-not (Test-Path -LiteralPath $CaCertificate)) {
    & $OpenSsl req -x509 -newkey rsa:3072 -sha256 -days 825 -nodes `
        -keyout $CaKey -out $CaCertificate -subj '/CN=Junhui Phase 3.7 Local CA'
}
if (-not (Test-Path -LiteralPath $ServerCertificate)) {
    & $OpenSsl req -newkey rsa:3072 -nodes -keyout $ServerKey -out $ServerRequest `
        -config $CertificateConfig
    & $OpenSsl x509 -req -in $ServerRequest -CA $CaCertificate -CAkey $CaKey `
        -CAcreateserial -out $ServerCertificate -days 397 -sha256 `
        -extensions extensions -extfile $CertificateConfig
}

$PrivateEnvironment = Get-Content -LiteralPath $EnvironmentFile
$PrivateEnvironment = $PrivateEnvironment | ForEach-Object {
    if ($_ -eq 'PHASE37_ADMIN_EMAIL=phase37-review@junhui.test') {
        'PHASE37_ADMIN_EMAIL=phase37-review@example.com'
    } else {
        $_
    }
}
Set-Content -LiteralPath $EnvironmentFile -Value $PrivateEnvironment -Encoding utf8NoBOM
$ExistingAdminPassword = ($PrivateEnvironment | Where-Object { $_ -like 'PHASE37_ADMIN_PASSWORD=*' }) -replace '^[^=]+=', ''
if (
    $ExistingAdminPassword.Length -lt 12 -or
    $ExistingAdminPassword -cnotmatch '[A-Z]' -or
    $ExistingAdminPassword -cnotmatch '[a-z]' -or
    $ExistingAdminPassword -notmatch '[0-9]' -or
    $ExistingAdminPassword -notmatch '[^A-Za-z0-9]'
) {
    # 尚未成功 Bootstrap 的弱随机值可安全轮换；只写私有 env，不打印新值。
    $ReplacementPassword = New-Phase37AdminPassword
    $PrivateEnvironment = $PrivateEnvironment | ForEach-Object {
        if ($_ -like 'PHASE37_ADMIN_PASSWORD=*') {
            "PHASE37_ADMIN_PASSWORD=$ReplacementPassword"
        } else {
            $_
        }
    }
    Set-Content -LiteralPath $EnvironmentFile -Value $PrivateEnvironment -Encoding utf8NoBOM
}
$BasicUser = ($PrivateEnvironment | Where-Object { $_ -like 'PHASE37_BASIC_USER=*' }) -replace '^[^=]+=', ''
$BasicPassword = ($PrivateEnvironment | Where-Object { $_ -like 'PHASE37_BASIC_PASSWORD=*' }) -replace '^[^=]+=', ''
$PasswordHash = & $OpenSsl passwd -apr1 $BasicPassword
Set-Content -LiteralPath (Join-Path $AuthRoot 'phase37.htpasswd') `
    -Value "${BasicUser}:$PasswordHash" -Encoding ascii

if ($InstallTrustAndHosts) {
    # 只有显式开关才改变当前用户信任库和 Windows hosts；hosts 写入通常需要管理员权限。
    Import-Certificate -FilePath $CaCertificate -CertStoreLocation 'Cert:\CurrentUser\Root' | Out-Null
    $HostsPath = Join-Path $env:SystemRoot 'System32\drivers\etc\hosts'
    $ExistingHosts = Get-Content -LiteralPath $HostsPath -Raw
    foreach ($Hostname in @('junhui.test', 'admin.junhui.test', 'api.junhui.test')) {
        if ($ExistingHosts -notmatch "(?m)^\s*127\.0\.0\.1\s+.*\b$([regex]::Escape($Hostname))\b") {
            Add-Content -LiteralPath $HostsPath -Value "127.0.0.1 $Hostname" -Encoding ascii
        }
    }
    Write-Host 'Local CA trusted for current user and three .test host mappings installed.'
} else {
    Write-Host 'Generated private Phase 3.7 credentials, TLS files and htpasswd.'
    Write-Host 'No trust-store or hosts changes were made.'
    Write-Host 'Re-run with -InstallTrustAndHosts only when local machine installation is approved.'
}
