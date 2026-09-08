[CmdletBinding()]
param(
    [ValidateSet('Setup', 'Start', 'Status', 'Stop', 'Restore', 'RepairProxy')]
    [string]$Action = 'Status',
    [switch]$NoOpen,
    [switch]$NoElevation
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# 脚本用途：管理骏辉 phase37 本机真实域名预览，不触碰公共 DNS、生产或业务数据。
$RepositoryRoot = if ($env:JUNHUI_LOCAL_PREVIEW_ROOT) {
    (Resolve-Path $env:JUNHUI_LOCAL_PREVIEW_ROOT).Path
} else {
    (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}
$LauncherScriptPath = Join-Path $RepositoryRoot 'scripts\Junhui-LocalPreview-Launcher.ps1'
$BaseComposeFile = Join-Path $RepositoryRoot 'docker-compose.yml'
$Phase37ComposeFile = Join-Path $RepositoryRoot 'docker-compose.phase37.yml'
$RuntimeComposeFile = Join-Path $RepositoryRoot 'docker-compose.phase37.runtime.yml'
$LocalComposeFile = Join-Path $RepositoryRoot 'docker-compose.local-domain.yml'
$EnvironmentFile = Join-Path $RepositoryRoot '.env.phase37'
$LocalNginxFile = Join-Path $RepositoryRoot 'infra\nginx\nginx.local-domain.conf'
$PrivateRoot = Join-Path $RepositoryRoot 'data\phase3-7'
$TlsRoot = Join-Path $PrivateRoot 'tls'
$StateRoot = Join-Path $PrivateRoot 'local-domain-state'
$StateFile = Join-Path $StateRoot 'state.json'
$HostsBackupFile = Join-Path $StateRoot 'hosts.before-local-domain'
$HostsPath = Join-Path $env:SystemRoot 'System32\drivers\etc\hosts'
$ClashRoot = Join-Path $env:APPDATA 'io.github.clash-verge-rev.clash-verge-rev'
$ClashProfilesFile = Join-Path $ClashRoot 'profiles.yaml'
$ClashGeneratedFile = Join-Path $ClashRoot 'clash-verge.yaml'
$ClashRuntimeFile = Join-Path $ClashRoot 'config.yaml'
$ClashVergeFile = Join-Path $ClashRoot 'verge.yaml'
$ClashBinary = 'D:\Clash\verge-mihomo.exe'
$ComposeProject = 'junhui-phase37-pilot'
$HostsBegin = '# BEGIN JUNHUI LOCAL PREVIEW'
$HostsEnd = '# END JUNHUI LOCAL PREVIEW'
$ScriptBegin = '/* BEGIN JUNHUI LOCAL PREVIEW */'
$ScriptEnd = '/* END JUNHUI LOCAL PREVIEW */'
$GeneratedHostsBegin = '# BEGIN JUNHUI LOCAL PREVIEW HOSTS'
$GeneratedHostsEnd = '# END JUNHUI LOCAL PREVIEW HOSTS'
$GeneratedDnsBegin = '  # BEGIN JUNHUI LOCAL PREVIEW DNS'
$GeneratedDnsEnd = '  # END JUNHUI LOCAL PREVIEW DNS'
$GeneratedRulesBegin = '# BEGIN JUNHUI LOCAL PREVIEW RULES'
$GeneratedRulesEnd = '# END JUNHUI LOCAL PREVIEW RULES'
$PreviewDomains = @(
    'junhuiscrewbarrel.com',
    'www.junhuiscrewbarrel.com',
    'admin.junhuiscrewbarrel.com',
    'api.junhuiscrewbarrel.com'
)
$PersistentServices = @('postgres', 'redis', 'minio', 'minio-init', 'api', 'worker', 'website', 'admin', 'nginx')

New-Item -ItemType Directory -Force -Path $StateRoot, $TlsRoot | Out-Null

function Test-IsAdministrator {
    <#
    判断当前 PowerShell 是否具有管理员令牌。

    输入：无。
    输出：bool，管理员令牌返回 true。
    #>
    $Identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $Principal = [Security.Principal.WindowsPrincipal]::new($Identity)
    return $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-StablePowerShellExecutable {
    <#
    选择不会依赖 Codex 临时运行时目录的 PowerShell 可执行文件。

    输入：无。
    输出：string，系统安装的 PowerShell 7 或 Windows PowerShell 完整路径。
    #>
    $Candidates = @(
        (Join-Path $env:ProgramFiles 'PowerShell\7\pwsh.exe'),
        (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe')
    )
    foreach ($Candidate in $Candidates) {
        if (Test-Path -LiteralPath $Candidate) {
            return $Candidate
        }
    }
    throw '未找到可供快捷方式长期使用的系统 PowerShell。'
}

function Test-CurrentUserRootCertificate {
    <#
    使用 .NET 证书存储检查当前用户是否信任指定根证书，避免依赖 Cert: PSDrive。

    输入：Certificate 为待检查的 X509Certificate2。
    输出：bool，证书指纹存在于 CurrentUser Root 时返回 true。
    #>
    param([Parameter(Mandatory)] $Certificate)
    $Store = [Security.Cryptography.X509Certificates.X509Store]::new(
        [Security.Cryptography.X509Certificates.StoreName]::Root,
        [Security.Cryptography.X509Certificates.StoreLocation]::CurrentUser
    )
    try {
        $Store.Open([Security.Cryptography.X509Certificates.OpenFlags]::ReadOnly)
        $Matches = $Store.Certificates.Find(
            [Security.Cryptography.X509Certificates.X509FindType]::FindByThumbprint,
            $Certificate.Thumbprint,
            $false
        )
        return $Matches.Count -gt 0
    } finally {
        $Store.Close()
    }
}

function Add-CurrentUserRootCertificate {
    <#
    使用 .NET 证书存储把现有本地 CA 加入当前用户根信任区。

    输入：Certificate 为待加入的 X509Certificate2。
    输出：无。
    #>
    param([Parameter(Mandatory)] $Certificate)
    $Store = [Security.Cryptography.X509Certificates.X509Store]::new(
        [Security.Cryptography.X509Certificates.StoreName]::Root,
        [Security.Cryptography.X509Certificates.StoreLocation]::CurrentUser
    )
    try {
        $Store.Open([Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
        $Store.Add($Certificate)
    } finally {
        $Store.Close()
    }
}

function Restart-ElevatedSetup {
    <#
    以一次 UAC 提示重新运行 Setup。

    输入：无。
    输出：无；等待提升后的子进程结束并传递退出码。
    #>
    $PowerShellExecutable = Get-StablePowerShellExecutable
    $Arguments = @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', ('"{0}"' -f $LauncherScriptPath),
        '-Action', 'Setup',
        '-NoElevation'
    )
    if ($NoOpen) {
        $Arguments += '-NoOpen'
    }
    Write-Host 'Setup 需要一次 Windows UAC，以备份并合并 hosts；不需要提供系统密码给脚本。'
    $Process = Start-Process -FilePath $PowerShellExecutable -ArgumentList $Arguments -Verb RunAs -Wait -PassThru
    exit $Process.ExitCode
}

function Write-Utf8NoBom {
    <#
    以 UTF-8 无 BOM 原子写入文本。

    输入：Path 为目标路径，Content 为完整文本。
    输出：无。
    #>
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [string]$Content
    )
    $Parent = Split-Path -Parent $Path
    if ($Parent) {
        New-Item -ItemType Directory -Force -Path $Parent | Out-Null
    }
    $TemporaryPath = "$Path.junhui-tmp"
    [IO.File]::WriteAllText($TemporaryPath, $Content, [Text.UTF8Encoding]::new($false))
    Move-Item -Force -LiteralPath $TemporaryPath -Destination $Path
}

function Get-ComposeArguments {
    <#
    返回安全运行所需的 Compose 参数。

    输入：LocalDomain 为 true 时追加本机域名覆盖。
    输出：string[]，传给 docker 的参数。
    #>
    param([bool]$LocalDomain)
    $Arguments = @(
        'compose', '--env-file', $EnvironmentFile,
        '-p', $ComposeProject,
        '-f', $BaseComposeFile,
        '-f', $Phase37ComposeFile,
        '-f', $RuntimeComposeFile
    )
    if ($LocalDomain) {
        $Arguments += @('-f', $LocalComposeFile)
    }
    return $Arguments
}

function Invoke-PreviewCompose {
    <#
    运行固定项目和固定覆盖文件的 Docker Compose 命令。

    输入：LocalDomain 指定本机或原保护模式；DockerArguments 为子命令参数。
    输出：无；失败时抛出异常。
    #>
    param(
        [bool]$LocalDomain,
        [Parameter(Mandatory)] [string[]]$DockerArguments
    )
    $Arguments = @(Get-ComposeArguments -LocalDomain $LocalDomain) + $DockerArguments
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose 执行失败，退出码 $LASTEXITCODE。"
    }
}

function Assert-DockerEngineSafe {
    <#
    核对 Docker Engine 主版本满足 loopback 端口安全前提。

    输入：无。
    输出：string，Docker Server 版本。
    #>
    $Version = (& docker version --format '{{.Server.Version}}').Trim()
    if ($LASTEXITCODE -ne 0 -or -not $Version) {
        throw 'Docker Engine 不可用。请先启动 Docker Desktop。'
    }
    $MajorText = ($Version -split '[.-]')[0]
    $Major = 0
    if (-not [int]::TryParse($MajorText, [ref]$Major) -or $Major -lt 28) {
        throw "Docker Engine $Version 低于本机回环发布安全门要求的 28。"
    }
    return $Version
}

function Get-ComposeConfig {
    <#
    读取最终 Compose JSON，仅在内存中解析，避免把 Secret 输出到日志。

    输入：LocalDomain 指定配置组合。
    输出：pscustomobject，Compose 配置对象。
    #>
    param([bool]$LocalDomain)
    $Arguments = @(Get-ComposeArguments -LocalDomain $LocalDomain) + @('config', '--format', 'json')
    $RawConfig = & docker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw '无法解析最终 Compose 配置。'
    }
    return ($RawConfig | ConvertFrom-Json)
}

function Assert-LocalComposeSecurity {
    <#
    确认只有 Nginx 发布 127.0.0.1:443，且 API 不运行 migration/Seed。

    输入：无。
    输出：无；发现公开端口或危险命令时抛出异常。
    #>
    $Config = Get-ComposeConfig -LocalDomain $true
    foreach ($ServiceProperty in $Config.services.PSObject.Properties) {
        $ServiceName = $ServiceProperty.Name
        $Service = $ServiceProperty.Value
        $Ports = @($Service.ports | Where-Object { $null -ne $_ -and $null -ne $_.target })
        if ($ServiceName -eq 'nginx') {
            if ($Ports.Count -ne 1) {
                throw "Nginx 最终端口数量不是 1：$($Ports.Count)。"
            }
            $Port = $Ports[0]
            if ($Port.host_ip -ne '127.0.0.1' -or [string]$Port.published -ne '443' -or [string]$Port.target -ne '443') {
                throw "Nginx 最终绑定不安全：host_ip=$($Port.host_ip), published=$($Port.published), target=$($Port.target)。"
            }
        } elseif ($Ports.Count -gt 0) {
            throw "服务 $ServiceName 意外发布宿主端口。"
        }
        if ($Service.network_mode -eq 'host') {
            throw "服务 $ServiceName 不允许使用 host network。"
        }
    }
    $ApiCommand = @($Config.services.api.command) -join ' '
    if ($ApiCommand -match '(?i)alembic|seed') {
        throw "API 最终命令仍包含 migration/Seed：$ApiCommand"
    }
    if ($Config.services.api.environment.APP_ENV -ne 'staging') {
        throw 'API APP_ENV 必须继续为 staging。'
    }
    if ($Config.services.api.environment.PUBLIC_SITEMAP_ENABLED -ne 'false') {
        throw 'Sitemap 必须继续关闭。'
    }
}

function Get-ActiveClashPaths {
    <#
    从 profiles.yaml 定位当前订阅绑定的持久 Script 文件。

    输入：无。
    输出：pscustomobject，包含当前档案 ID 与 Script 路径。
    #>
    if (-not (Test-Path -LiteralPath $ClashProfilesFile)) {
        throw '未找到 Clash Verge profiles.yaml。'
    }
    $ProfilesText = [IO.File]::ReadAllText($ClashProfilesFile)
    $CurrentMatch = [regex]::Match($ProfilesText, '(?m)^current:\s*(\S+)\s*$')
    if (-not $CurrentMatch.Success) {
        throw '无法确定 Clash Verge 当前档案。'
    }
    $CurrentId = $CurrentMatch.Groups[1].Value
    $ItemPattern = '(?ms)^- uid:\s*' + [regex]::Escape($CurrentId) + '\s*$.*?(?=^- uid:|\z)'
    $ItemMatch = [regex]::Match($ProfilesText, $ItemPattern)
    if (-not $ItemMatch.Success) {
        throw '当前 Clash 档案未出现在 profiles.yaml 中。'
    }
    $ScriptMatch = [regex]::Match($ItemMatch.Value, '(?m)^\s+script:\s*(\S+)\s*$')
    if (-not $ScriptMatch.Success) {
        throw '当前 Clash 档案没有绑定持久 Script。'
    }
    $ScriptId = $ScriptMatch.Groups[1].Value
    $ScriptPath = Join-Path $ClashRoot "profiles\$ScriptId.js"
    if (-not (Test-Path -LiteralPath $ScriptPath)) {
        throw "当前 Clash Script 不存在：$ScriptPath"
    }
    return [pscustomobject]@{
        CurrentProfile = $CurrentId
        ScriptId = $ScriptId
        ScriptPath = $ScriptPath
    }
}

function Add-ManagedClashScript {
    <#
    在当前持久 Script 中包装原 main，并精确追加本地域名、DNS 与 DIRECT 规则。

    输入：ScriptPath 为当前档案绑定脚本。
    输出：bool，发生修改返回 true。
    #>
    param([Parameter(Mandatory)] [string]$ScriptPath)
    $Text = [IO.File]::ReadAllText($ScriptPath)
    if ($Text.Contains($ScriptBegin)) {
        return $false
    }
    $MainPattern = [regex]'function\s+main\s*\('
    if (-not $MainPattern.IsMatch($Text)) {
        throw '当前 Clash Script 没有可包装的 main 函数。'
    }
    $Updated = $MainPattern.Replace($Text, 'function junhuiOriginalMain(', 1)
    $ManagedBlock = @'

/* BEGIN JUNHUI LOCAL PREVIEW */
// 仅为四个骏辉本地域名追加回环解析和 DIRECT；其余订阅规则保持原样。
function main(config, profileName) {
  const nextConfig = junhuiOriginalMain(config, profileName) || config || {};
  const domains = [
    "junhuiscrewbarrel.com",
    "www.junhuiscrewbarrel.com",
    "admin.junhuiscrewbarrel.com",
    "api.junhuiscrewbarrel.com",
  ];

  nextConfig.hosts = nextConfig.hosts && typeof nextConfig.hosts === "object" ? nextConfig.hosts : {};
  for (const domain of domains) {
    nextConfig.hosts[domain] = "127.0.0.1";
  }

  nextConfig.dns = nextConfig.dns && typeof nextConfig.dns === "object" ? nextConfig.dns : {};
  nextConfig.dns["use-hosts"] = true;
  const fakeIpFilter = Array.isArray(nextConfig.dns["fake-ip-filter"])
    ? [...nextConfig.dns["fake-ip-filter"]]
    : [];
  for (const domain of domains) {
    if (!fakeIpFilter.includes(domain)) fakeIpFilter.unshift(domain);
  }
  nextConfig.dns["fake-ip-filter"] = fakeIpFilter;

  const directRules = domains.map((domain) => `DOMAIN,${domain},DIRECT`);
  const existingRules = Array.isArray(nextConfig.rules) ? nextConfig.rules : [];
  nextConfig.rules = [
    ...directRules,
    ...existingRules.filter((rule) => !directRules.includes(rule)),
  ];
  return nextConfig;
}
/* END JUNHUI LOCAL PREVIEW */
'@
    Write-Utf8NoBom -Path $ScriptPath -Content ($Updated.TrimEnd() + "`r`n" + $ManagedBlock.TrimStart())
    return $true
}

function Remove-ManagedClashScript {
    <#
    仅移除本轮 Script 包装，保留用户后续对原函数的其他编辑。

    输入：ScriptPath 为曾经管理的脚本。
    输出：bool，发生修改返回 true。
    #>
    param([Parameter(Mandatory)] [string]$ScriptPath)
    if (-not (Test-Path -LiteralPath $ScriptPath)) {
        return $false
    }
    $Text = [IO.File]::ReadAllText($ScriptPath)
    if (-not $Text.Contains($ScriptBegin)) {
        return $false
    }
    $BlockPattern = '(?s)\r?\n?/\* BEGIN JUNHUI LOCAL PREVIEW \*/.*?/\* END JUNHUI LOCAL PREVIEW \*/\r?\n?'
    $Updated = [regex]::Replace($Text, $BlockPattern, "`r`n")
    $Updated = [regex]::Replace($Updated, 'function\s+junhuiOriginalMain\s*\(', 'function main(', 1)
    Write-Utf8NoBom -Path $ScriptPath -Content ($Updated.TrimEnd() + "`r`n")
    return $true
}

function Add-GeneratedClashRules {
    <#
    为当前运行配置加入带标记的 hosts、fake-ip-filter 和 DIRECT 规则，供立即重载。

    输入：无。
    输出：bool，发生修改返回 true。
    #>
    if (-not (Test-Path -LiteralPath $ClashGeneratedFile)) {
        throw '未找到 Clash Verge 当前生成配置。'
    }
    $Text = [IO.File]::ReadAllText($ClashGeneratedFile)
    if ($Text.Contains($GeneratedHostsBegin)) {
        return $false
    }
    if ([regex]::IsMatch($Text, '(?m)^hosts:\s*$')) {
        throw '当前生成配置已包含未管理的顶层 hosts；为避免覆盖，Setup 已停止。'
    }
    if (-not [regex]::IsMatch($Text, '(?m)^dns:\s*$') -or -not [regex]::IsMatch($Text, '(?m)^rules:\s*$')) {
        throw '当前生成配置缺少预期的 dns/rules 顶层结构。'
    }

    $HostsBlock = @"
$GeneratedHostsBegin
hosts:
  junhuiscrewbarrel.com: 127.0.0.1
  www.junhuiscrewbarrel.com: 127.0.0.1
  admin.junhuiscrewbarrel.com: 127.0.0.1
  api.junhuiscrewbarrel.com: 127.0.0.1
$GeneratedHostsEnd
"@
    $DnsBlock = @"
$GeneratedDnsBegin
  - junhuiscrewbarrel.com
  - www.junhuiscrewbarrel.com
  - admin.junhuiscrewbarrel.com
  - api.junhuiscrewbarrel.com
$GeneratedDnsEnd
"@
    $RulesBlock = @"
$GeneratedRulesBegin
- DOMAIN,junhuiscrewbarrel.com,DIRECT
- DOMAIN,www.junhuiscrewbarrel.com,DIRECT
- DOMAIN,admin.junhuiscrewbarrel.com,DIRECT
- DOMAIN,api.junhuiscrewbarrel.com,DIRECT
$GeneratedRulesEnd
"@

    $DnsRegex = [regex]'(?m)^dns:\s*$'
    $Updated = $DnsRegex.Replace($Text, $HostsBlock.TrimEnd() + "`r`ndns:", 1)
    $Updated = [regex]::Replace($Updated, '(?m)^  use-hosts:\s*.*$', '  use-hosts: true', 1)
    $FilterRegex = [regex]'(?m)^  fake-ip-filter:\s*$'
    if (-not $FilterRegex.IsMatch($Updated)) {
        throw '当前 DNS 配置没有 fake-ip-filter，拒绝猜测插入位置。'
    }
    $Updated = $FilterRegex.Replace($Updated, "  fake-ip-filter:`r`n$($DnsBlock.TrimEnd())", 1)
    $RulesRegex = [regex]'(?m)^rules:\s*$'
    $Updated = $RulesRegex.Replace($Updated, "rules:`r`n$($RulesBlock.TrimEnd())", 1)
    Write-Utf8NoBom -Path $ClashGeneratedFile -Content $Updated
    return $true
}

function Remove-GeneratedClashRules {
    <#
    从当前生成配置移除本轮带标记片段，保留其余订阅配置。

    输入：无。
    输出：bool，发生修改返回 true。
    #>
    if (-not (Test-Path -LiteralPath $ClashGeneratedFile)) {
        return $false
    }
    $Text = [IO.File]::ReadAllText($ClashGeneratedFile)
    $HasManagedMarker =
        $Text.Contains($GeneratedHostsBegin) -or
        $Text.Contains($GeneratedDnsBegin) -or
        $Text.Contains($GeneratedRulesBegin) -or
        $Text.Contains('  # BEGIN JUNHUI LOCAL PREVIEW RULES')
    if (-not $HasManagedMarker) {
        return $false
    }
    # 逐行移除管理区，避免在大型订阅配置上使用易产生灾难性回溯的正则。
    $Lines = $Text -split '\r?\n'
    $ManagedRanges = @(
        @($GeneratedHostsBegin, $GeneratedHostsEnd),
        @($GeneratedDnsBegin, $GeneratedDnsEnd),
        @($GeneratedRulesBegin, $GeneratedRulesEnd),
        # 兼容首次失败 Setup 写入的旧缩进标记，确保可恢复。
        @('  # BEGIN JUNHUI LOCAL PREVIEW RULES', '  # END JUNHUI LOCAL PREVIEW RULES')
    )
    foreach ($Range in $ManagedRanges) {
        $StartMarker = $Range[0]
        $EndMarker = $Range[1]
        $InsideManagedRange = $false
        $FoundStart = $false
        $FoundEnd = $false
        $FilteredLines = foreach ($Line in $Lines) {
            if ($Line -eq $StartMarker) {
                $InsideManagedRange = $true
                $FoundStart = $true
                continue
            }
            if ($Line -eq $EndMarker) {
                $InsideManagedRange = $false
                $FoundEnd = $true
                continue
            }
            if (-not $InsideManagedRange) {
                $Line
            }
        }
        if ($FoundStart -ne $FoundEnd) {
            throw "Clash 生成配置的管理标记不完整：$StartMarker"
        }
        $Lines = @($FilteredLines)
    }
    $Updated = ($Lines -join "`n").TrimEnd() + "`n"
    Write-Utf8NoBom -Path $ClashGeneratedFile -Content $Updated
    return $true
}

function Test-MihomoConfiguration {
    <#
    使用当前 Mihomo 二进制执行配置语法校验。

    输入：无。
    输出：无；校验失败时抛出异常。
    #>
    if (-not (Test-Path -LiteralPath $ClashBinary)) {
        throw "未找到 Mihomo 二进制：$ClashBinary"
    }
    $ValidationOutput = & $ClashBinary -t -f $ClashGeneratedFile 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Mihomo 配置校验失败：$($ValidationOutput -join ' ')"
    }
}

function Reload-MihomoConfiguration {
    <#
    通过仅监听 127.0.0.1 的控制接口重载已校验配置。

    输入：无。
    输出：bool，控制器可用并完成重载返回 true。
    #>
    if (-not (Test-Path -LiteralPath $ClashRuntimeFile)) {
        return $false
    }
    $RuntimeLines = Get-Content -LiteralPath $ClashRuntimeFile
    $SecretLine = $RuntimeLines | Where-Object { $_ -match '^secret:' } | Select-Object -First 1
    $Secret = if ($SecretLine) { ($SecretLine -replace '^secret:\s*', '').Trim().Trim("'", '"') } else { '' }
    $Headers = @{}
    if ($Secret) {
        $Headers.Authorization = "Bearer $Secret"
    }
    try {
        $Body = @{ path = $ClashGeneratedFile } | ConvertTo-Json -Compress
        Invoke-RestMethod -Method Put -Uri 'http://127.0.0.1:9097/configs?force=true' -Headers $Headers -ContentType 'application/json' -Body $Body | Out-Null
        return $true
    } catch {
        throw 'Mihomo 本地控制器未接受配置重载；未输出控制器密钥。'
    }
}

function Update-SystemProxyBypass {
    <#
    为 Clash Verge 与 WinINET 精确加入或移除四个域名绕过，保留其他值。

    输入：Install 为 true 时加入，为 false 时移除。
    输出：无。
    #>
    param([bool]$Install)
    if (-not (Test-Path -LiteralPath $ClashVergeFile)) {
        throw '未找到 Clash Verge verge.yaml。'
    }
    $VergeText = [IO.File]::ReadAllText($ClashVergeFile)
    $BypassMatch = [regex]::Match($VergeText, '(?m)^system_proxy_bypass:\s*(.*)$')
    if (-not $BypassMatch.Success) {
        throw 'verge.yaml 没有 system_proxy_bypass 配置项。'
    }
    $CurrentValue = $BypassMatch.Groups[1].Value.Trim().Trim("'", '"')
    $Items = @($CurrentValue -split '[;,]' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($Install) {
        foreach ($Domain in $PreviewDomains) {
            if ($Items -notcontains $Domain) {
                $Items += $Domain
            }
        }
    } else {
        $Items = @($Items | Where-Object { $PreviewDomains -notcontains $_ })
    }
    $NewValue = ($Items -join ';').Replace("'", "''")
    $UpdatedVerge = [regex]::Replace($VergeText, '(?m)^system_proxy_bypass:\s*.*$', "system_proxy_bypass: '$NewValue'", 1)
    Write-Utf8NoBom -Path $ClashVergeFile -Content $UpdatedVerge

    $InternetSettings = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
    $ExistingOverride = (Get-ItemProperty -Path $InternetSettings -Name ProxyOverride -ErrorAction SilentlyContinue).ProxyOverride
    $OverrideItems = @($ExistingOverride -split ';' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($Install) {
        foreach ($Domain in $PreviewDomains) {
            if ($OverrideItems -notcontains $Domain) {
                $OverrideItems += $Domain
            }
        }
    } else {
        $OverrideItems = @($OverrideItems | Where-Object { $PreviewDomains -notcontains $_ })
    }
    Set-ItemProperty -Path $InternetSettings -Name ProxyOverride -Value ($OverrideItems -join ';')
}

function Install-ManagedHosts {
    <#
    备份并以标记段合并四个 127.0.0.1 域名，不覆盖其他 hosts 内容。

    输入：无。
    输出：bool，发生修改返回 true。
    #>
    $Existing = [IO.File]::ReadAllText($HostsPath)
    if (-not (Test-Path -LiteralPath $HostsBackupFile)) {
        Copy-Item -LiteralPath $HostsPath -Destination $HostsBackupFile
    }
    $WithoutManaged = [regex]::Replace(
        $Existing,
        '(?ms)^# BEGIN JUNHUI LOCAL PREVIEW\r?\n.*?^# END JUNHUI LOCAL PREVIEW\r?\n?',
        ''
    )
    foreach ($Domain in $PreviewDomains) {
        $Conflict = [regex]::Match($WithoutManaged, '(?im)^\s*(?!#)(\S+)\s+.*\b' + [regex]::Escape($Domain) + '\b.*$')
        if ($Conflict.Success) {
            throw "hosts 中已有非本轮管理的 $Domain 条目：$($Conflict.Value.Trim())"
        }
    }
    $ManagedLines = @($HostsBegin) + ($PreviewDomains | ForEach-Object { "127.0.0.1 $_" }) + @($HostsEnd)
    $Updated = $WithoutManaged.TrimEnd() + "`r`n`r`n" + ($ManagedLines -join "`r`n") + "`r`n"
    if ($Updated -eq $Existing) {
        return $false
    }
    Write-Utf8NoBom -Path $HostsPath -Content $Updated
    return $true
}

function Remove-ManagedHosts {
    <#
    仅删除本轮 hosts 标记段，保留其他条目和备份。

    输入：无。
    输出：bool，发生修改返回 true。
    #>
    $Existing = [IO.File]::ReadAllText($HostsPath)
    if (-not $Existing.Contains($HostsBegin)) {
        return $false
    }
    $Updated = [regex]::Replace(
        $Existing,
        '(?ms)^# BEGIN JUNHUI LOCAL PREVIEW\r?\n.*?^# END JUNHUI LOCAL PREVIEW\r?\n?',
        ''
    )
    Write-Utf8NoBom -Path $HostsPath -Content ($Updated.TrimEnd() + "`r`n")
    return $true
}

function Ensure-LocalCertificate {
    <#
    复用现有 Phase 3.7 CA，为四个真实域名创建或复用 SAN 叶子证书并信任 CA。

    输入：无。
    输出：pscustomobject，CA 与叶子证书指纹。
    #>
    $OpenSsl = (Get-Command openssl -ErrorAction Stop).Source
    $CaCertificate = Join-Path $TlsRoot 'ca.crt'
    $CaKey = Join-Path $TlsRoot 'ca.key'
    $LeafKey = Join-Path $TlsRoot 'local-domain.key'
    $LeafRequest = Join-Path $TlsRoot 'local-domain.csr'
    $LeafCertificate = Join-Path $TlsRoot 'local-domain.crt'
    $LeafConfig = Join-Path $TlsRoot 'local-domain.cnf'
    $CaSerial = Join-Path $TlsRoot 'local-domain-ca.srl'
    if (-not (Test-Path -LiteralPath $CaCertificate) -or -not (Test-Path -LiteralPath $CaKey)) {
        throw '现有 Phase 3.7 CA 证书或私钥缺失；拒绝创建第二个 CA。'
    }

    $NeedsCertificate = -not (Test-Path -LiteralPath $LeafCertificate) -or -not (Test-Path -LiteralPath $LeafKey)
    if (-not $NeedsCertificate) {
        $SanText = (& $OpenSsl x509 -in $LeafCertificate -noout -ext subjectAltName 2>&1) -join ' '
        foreach ($Domain in $PreviewDomains) {
            if ($SanText -notmatch ('DNS:' + [regex]::Escape($Domain))) {
                $NeedsCertificate = $true
            }
        }
        & $OpenSsl x509 -checkend 2592000 -noout -in $LeafCertificate | Out-Null
        if ($LASTEXITCODE -ne 0) {
            $NeedsCertificate = $true
        }
    }

    if ($NeedsCertificate) {
        $ConfigLines = @(
            '[req]',
            'prompt = no',
            'distinguished_name = subject',
            'req_extensions = extensions',
            '[subject]',
            'CN = junhuiscrewbarrel.com',
            '[extensions]',
            'basicConstraints = critical,CA:FALSE',
            'keyUsage = critical,digitalSignature,keyEncipherment',
            'extendedKeyUsage = serverAuth',
            'subjectAltName = @alternate_names',
            '[alternate_names]',
            'DNS.1 = junhuiscrewbarrel.com',
            'DNS.2 = www.junhuiscrewbarrel.com',
            'DNS.3 = admin.junhuiscrewbarrel.com',
            'DNS.4 = api.junhuiscrewbarrel.com'
        )
        Write-Utf8NoBom -Path $LeafConfig -Content (($ConfigLines -join "`n") + "`n")
        & $OpenSsl req -newkey rsa:3072 -nodes -keyout $LeafKey -out $LeafRequest -config $LeafConfig
        if ($LASTEXITCODE -ne 0) {
            throw '生成本地域名证书请求失败。'
        }
        & $OpenSsl x509 -req -in $LeafRequest -CA $CaCertificate -CAkey $CaKey -CAserial $CaSerial -CAcreateserial -out $LeafCertificate -days 397 -sha256 -extensions extensions -extfile $LeafConfig
        if ($LASTEXITCODE -ne 0) {
            throw '签发本地域名叶子证书失败。'
        }
    }

    & $OpenSsl verify -CAfile $CaCertificate $LeafCertificate | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw '本地域名叶子证书无法由现有 CA 验证。'
    }
    $CaObject = [Security.Cryptography.X509Certificates.X509Certificate2]::new($CaCertificate)
    $Trusted = Test-CurrentUserRootCertificate -Certificate $CaObject
    if (-not $Trusted) {
        Add-CurrentUserRootCertificate -Certificate $CaObject
    }
    $LeafObject = [Security.Cryptography.X509Certificates.X509Certificate2]::new($LeafCertificate)
    return [pscustomobject]@{
        CaThumbprint = $CaObject.Thumbprint
        LeafThumbprint = $LeafObject.Thumbprint
        LeafNotAfter = $LeafObject.NotAfter.ToString('o')
    }
}

function Save-SetupState {
    <#
    保存不含凭据的本轮状态，供 Status/Restore 精确定位。

    输入：ClashPaths 和证书信息。
    输出：无。
    #>
    param(
        [Parameter(Mandatory)] $ClashPaths,
        [Parameter(Mandatory)] $CertificateInfo
    )
    $State = [ordered]@{
        schema_version = 1
        installed_at = (Get-Date).ToString('o')
        repository = $RepositoryRoot
        compose_project = $ComposeProject
        managed_script_path = $ClashPaths.ScriptPath
        current_profile_at_setup = $ClashPaths.CurrentProfile
        ca_thumbprint = $CertificateInfo.CaThumbprint
        leaf_thumbprint = $CertificateInfo.LeafThumbprint
        leaf_not_after = $CertificateInfo.LeafNotAfter
        domains = $PreviewDomains
    }
    Write-Utf8NoBom -Path $StateFile -Content (($State | ConvertTo-Json -Depth 4) + "`r`n")
}

function New-PreviewShortcut {
    <#
    创建桌面“一键启动并打开”快捷方式。

    输入：无。
    输出：string，快捷方式完整路径。
    #>
    $DesktopPath = [Environment]::GetFolderPath('Desktop')
    $ShortcutPath = Join-Path $DesktopPath '打开骏辉本地官网.lnk'
    $PowerShellExecutable = Get-StablePowerShellExecutable
    $Shell = New-Object -ComObject WScript.Shell
    $Shortcut = $Shell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $PowerShellExecutable
    $Shortcut.Arguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" -Action Start' -f $LauncherScriptPath
    $Shortcut.WorkingDirectory = $RepositoryRoot
    $Shortcut.Description = '启动并打开骏辉 phase37 本机真实域名预览'
    $Shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,220"
    $Shortcut.Save()
    return $ShortcutPath
}

function Test-SetupInstalled {
    <#
    确认 hosts、证书和持久代理 Script 均已安装。

    输入：无。
    输出：无；缺失时抛出异常。
    #>
    $HostsText = [IO.File]::ReadAllText($HostsPath)
    if (-not $HostsText.Contains($HostsBegin)) {
        throw '尚未安装 hosts 管理段，请先运行 Setup。'
    }
    foreach ($Domain in $PreviewDomains) {
        if ($HostsText -notmatch ('(?im)^127\.0\.0\.1\s+' + [regex]::Escape($Domain) + '\s*$')) {
            throw "hosts 缺少 $Domain 的回环映射。"
        }
    }
    $ClashPaths = Get-ActiveClashPaths
    $ScriptText = [IO.File]::ReadAllText($ClashPaths.ScriptPath)
    if (-not $ScriptText.Contains($ScriptBegin)) {
        throw '当前 Clash 档案未启用持久本地域名 Script，请重新运行 Setup。'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $TlsRoot 'local-domain.crt'))) {
        throw '本地域名证书缺失，请重新运行 Setup。'
    }
    $CaCertificate = Join-Path $TlsRoot 'ca.crt'
    $CaObject = [Security.Cryptography.X509Certificates.X509Certificate2]::new($CaCertificate)
    $Trusted = Test-CurrentUserRootCertificate -Certificate $CaObject
    if (-not $Trusted) {
        throw 'Phase 3.7 本地 CA 尚未受到当前用户信任，请重新运行 Setup。'
    }
}

function Wait-PreviewHealthy {
    <#
    等待真实域名 HTTPS 健康检查通过，保持正常 TLS 验证。

    输入：TimeoutSeconds 为最长等待秒数。
    输出：无；超时抛出异常。
    #>
    param([int]$TimeoutSeconds = 180)
    $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            # 直接检查真实中文首页，确保域名、TLS、网关和 Website 正文链路均已就绪。
            $Response = Invoke-WebRequest -Uri 'https://junhuiscrewbarrel.com/zh-cn/' -TimeoutSec 10 -UseBasicParsing
            if ($Response.StatusCode -eq 200 -and $Response.Headers['X-Junhui-Local-Preview'] -eq 'loopback-only') {
                return
            }
        } catch {
            # 服务重建期间继续等待，不放宽 TLS 校验。
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $Deadline)
    throw '本机真实域名预览在等待期限内未健康。'
}

function Start-LocalPreview {
    <#
    安全启动原 phase37 数据栈和本机回环网关。

    输入：无。
    输出：无。
    #>
    Test-SetupInstalled
    $Version = Assert-DockerEngineSafe
    Assert-LocalComposeSecurity
    Write-Host "Docker Server $Version；本机端口安全门通过。"
    Invoke-PreviewCompose -LocalDomain $true -DockerArguments (@('up', '-d', '--no-build') + $PersistentServices)
    Wait-PreviewHealthy
    # 记录不含凭据的启动回执，便于验证桌面快捷方式是否真正执行成功。
    $StartReceipt = [ordered]@{
        started_at = (Get-Date).ToString('o')
        compose_project = $ComposeProject
        entrypoint = if ($env:JUNHUI_LOCAL_PREVIEW_LAUNCHER) { $env:JUNHUI_LOCAL_PREVIEW_LAUNCHER } else { 'direct-main-script' }
        status = 'healthy'
        url = 'https://junhuiscrewbarrel.com/zh-cn/'
    }
    Write-Utf8NoBom -Path (Join-Path $StateRoot 'last-start.json') -Content (($StartReceipt | ConvertTo-Json -Depth 3) + "`r`n")
    Write-Host 'LOCAL_DOMAIN_LOOPBACK_PREVIEW_HEALTHY'
    if (-not $NoOpen) {
        Start-Process 'https://junhuiscrewbarrel.com/zh-cn/'
    }
}

function Stop-LocalPreview {
    <#
    仅停止本项目持久服务，保留容器、卷、hosts、证书和代理规则。

    输入：无。
    输出：无。
    #>
    Invoke-PreviewCompose -LocalDomain $true -DockerArguments (@('stop') + @('nginx', 'admin', 'website', 'worker', 'api', 'minio', 'redis', 'postgres'))
    Write-Host 'JUNHUI_LOCAL_PREVIEW_STOPPED_DATA_PRESERVED'
}

function Install-LocalPreview {
    <#
    完成本机 Setup：安全配置校验、证书、hosts、代理规则和快捷方式。

    输入：无。
    输出：无。
    #>
    if (-not (Test-IsAdministrator)) {
        if ($NoElevation) {
            throw 'Setup 需要管理员权限写 hosts；UAC 提升未成功。'
        }
        Restart-ElevatedSetup
    }
    $Version = Assert-DockerEngineSafe
    Assert-LocalComposeSecurity
    if (-not (Test-Path -LiteralPath $LocalNginxFile)) {
        throw '本机 Nginx 配置缺失。'
    }
    $CertificateInfo = Ensure-LocalCertificate
    $ClashPaths = Get-ActiveClashPaths
    try {
        Add-ManagedClashScript -ScriptPath $ClashPaths.ScriptPath | Out-Null
        Add-GeneratedClashRules | Out-Null
        Test-MihomoConfiguration
        Update-SystemProxyBypass -Install $true
        Reload-MihomoConfiguration | Out-Null
        Install-ManagedHosts | Out-Null
        Save-SetupState -ClashPaths $ClashPaths -CertificateInfo $CertificateInfo
        $ShortcutPath = New-PreviewShortcut
    } catch {
        try { Remove-ManagedClashScript -ScriptPath $ClashPaths.ScriptPath | Out-Null } catch {}
        try { Remove-GeneratedClashRules | Out-Null } catch {}
        try { Update-SystemProxyBypass -Install $false } catch {}
        try { Remove-ManagedHosts | Out-Null } catch {}
        throw
    }
    Write-Host "SETUP_OK Docker=$Version"
    Write-Host "CA_SHA1=$($CertificateInfo.CaThumbprint)"
    Write-Host "LEAF_SHA1=$($CertificateInfo.LeafThumbprint)"
    Write-Host "SHORTCUT=$ShortcutPath"
}

function Restore-OriginalPreview {
    <#
    撤回本轮 hosts/代理/回环网关，恢复带 Basic Auth 的原保护模式并保留数据。

    输入：无。
    输出：无。
    #>
    if (-not (Test-IsAdministrator)) {
        throw 'Restore 需要管理员权限移除 hosts 管理段。请从管理员 PowerShell 运行。'
    }
    try {
        Invoke-PreviewCompose -LocalDomain $true -DockerArguments (@('stop') + @('nginx', 'admin', 'website', 'worker', 'api', 'minio', 'redis', 'postgres'))
    } catch {
        Write-Warning '本机模式未运行或无法停止，将继续撤回精确配置。'
    }
    $ManagedScriptPath = $null
    if (Test-Path -LiteralPath $StateFile) {
        $State = Get-Content -Raw -LiteralPath $StateFile | ConvertFrom-Json
        $ManagedScriptPath = $State.managed_script_path
    }
    if (-not $ManagedScriptPath) {
        $ManagedScriptPath = (Get-ActiveClashPaths).ScriptPath
    }
    Remove-ManagedClashScript -ScriptPath $ManagedScriptPath | Out-Null
    Remove-GeneratedClashRules | Out-Null
    Test-MihomoConfiguration
    Update-SystemProxyBypass -Install $false
    Reload-MihomoConfiguration | Out-Null
    Remove-ManagedHosts | Out-Null

    $DesktopPath = [Environment]::GetFolderPath('Desktop')
    $ShortcutPath = Join-Path $DesktopPath '打开骏辉本地官网.lnk'
    if (Test-Path -LiteralPath $ShortcutPath) {
        Remove-Item -LiteralPath $ShortcutPath
    }
    Invoke-PreviewCompose -LocalDomain $false -DockerArguments (@('up', '-d', '--no-build') + $PersistentServices)
    Write-Host 'ORIGINAL_PHASE37_BASIC_PROTECTED_MODE_RESTORED'
}

function Show-PreviewStatus {
    <#
    显示不含凭据的域名、代理、证书、Compose 和运行状态。

    输入：无。
    输出：无，打印可读状态。
    #>
    Write-Host "Repository: $RepositoryRoot"
    Write-Host "Compose project: $ComposeProject"
    try {
        $Version = Assert-DockerEngineSafe
        Write-Host "Docker Server: $Version"
        Assert-LocalComposeSecurity
        Write-Host 'Compose loopback guard: PASS'
    } catch {
        Write-Host "Compose/Docker: FAIL - $($_.Exception.Message)"
    }

    $HostsText = [IO.File]::ReadAllText($HostsPath)
    $HostsManaged = $HostsText.Contains($HostsBegin)
    Write-Host "Hosts managed block: $HostsManaged"
    foreach ($Domain in $PreviewDomains) {
        if ($HostsManaged) {
            $Resolved = @([Net.Dns]::GetHostAddresses($Domain) | ForEach-Object { $_.IPAddressToString }) -join ','
            Write-Host "Resolve $Domain -> $Resolved"
        } else {
            Write-Host "Resolve $Domain -> NOT_CHECKED_WITHOUT_MANAGED_HOSTS"
        }
    }

    try {
        $ClashPaths = Get-ActiveClashPaths
        $ScriptText = [IO.File]::ReadAllText($ClashPaths.ScriptPath)
        # 状态输出不暴露订阅档案内部标识，只确认当前档案已被安全解析。
        Write-Host 'Clash current profile: active-profile-resolved'
        Write-Host "Persistent DIRECT script: $($ScriptText.Contains($ScriptBegin))"
        $RuntimeText = [IO.File]::ReadAllText($ClashRuntimeFile)
        $AllowLan = [regex]::Match($RuntimeText, '(?m)^allow-lan:\s*(\S+)').Groups[1].Value
        $TunEnabled = (Get-Content -LiteralPath $ClashVergeFile | Where-Object { $_ -match '^enable_tun_mode:' } | Select-Object -First 1)
        Write-Host "Clash allow-lan: $AllowLan"
        Write-Host "Clash $TunEnabled"
    } catch {
        Write-Host "Clash status: FAIL - $($_.Exception.Message)"
    }

    $CertificatePath = Join-Path $TlsRoot 'local-domain.crt'
    if (Test-Path -LiteralPath $CertificatePath) {
        $Certificate = [Security.Cryptography.X509Certificates.X509Certificate2]::new($CertificatePath)
        $CaCertificate = [Security.Cryptography.X509Certificates.X509Certificate2]::new((Join-Path $TlsRoot 'ca.crt'))
        $Trusted = Test-CurrentUserRootCertificate -Certificate $CaCertificate
        Write-Host "TLS leaf: $($Certificate.Thumbprint) expires $($Certificate.NotAfter.ToString('o'))"
        Write-Host "CA trusted for current user: $Trusted"
    } else {
        Write-Host 'TLS leaf: MISSING'
    }

    & docker ps -a --filter "label=com.docker.compose.project=$ComposeProject" --format '{{.Names}}|{{.Status}}|{{.Ports}}'
    Get-NetTCPConnection -State Listen -LocalPort 443 -ErrorAction SilentlyContinue |
        Select-Object LocalAddress, LocalPort, OwningProcess |
        Format-Table -AutoSize
    Write-Host 'URLs:'
    Write-Host '  https://junhuiscrewbarrel.com/zh-cn/'
    Write-Host '  https://junhuiscrewbarrel.com/en/'
    Write-Host '  https://admin.junhuiscrewbarrel.com/'
}

function Repair-PartialProxySetup {
    <#
    撤回失败 Setup 留下的代理标记并验证原生成配置；不修改 hosts、证书或容器。

    输入：无。
    输出：无。
    #>
    $ClashPaths = Get-ActiveClashPaths
    Remove-ManagedClashScript -ScriptPath $ClashPaths.ScriptPath | Out-Null
    Remove-GeneratedClashRules | Out-Null
    Update-SystemProxyBypass -Install $false
    Test-MihomoConfiguration
    Reload-MihomoConfiguration | Out-Null
    Write-Host 'PARTIAL_PROXY_SETUP_REPAIRED'
}

switch ($Action) {
    'Setup' { Install-LocalPreview }
    'Start' { Start-LocalPreview }
    'Status' { Show-PreviewStatus }
    'Stop' { Stop-LocalPreview }
    'Restore' { Restore-OriginalPreview }
    'RepairProxy' { Repair-PartialProxySetup }
}
