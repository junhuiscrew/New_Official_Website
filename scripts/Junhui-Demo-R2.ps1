[CmdletBinding()]
param(
    [ValidateSet('Setup', 'Start', 'Status', 'Stop', 'Restore')]
    [string]$Action = 'Status',
    [switch]$NoOpen,
    [switch]$NoElevation
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# 脚本用途：管理与原 phase37 数据完全分离的 Demo R2 本机域名环境。
$RepositoryRoot = if ($env:JUNHUI_DEMO_R2_ROOT) {
    (Resolve-Path $env:JUNHUI_DEMO_R2_ROOT).Path
} else {
    (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}
$LauncherPath = Join-Path $RepositoryRoot 'scripts\Junhui-Demo-R2-Launcher.ps1'
$BaseCompose = Join-Path $RepositoryRoot 'docker-compose.yml'
$Phase37Compose = Join-Path $RepositoryRoot 'docker-compose.phase37.yml'
$RuntimeCompose = Join-Path $RepositoryRoot 'docker-compose.phase37.runtime.yml'
$LocalCompose = Join-Path $RepositoryRoot 'docker-compose.local-domain.yml'
$DemoEdgeCompose = Join-Path $RepositoryRoot 'docker-compose.local-domain.demo-edge.yml'
$DemoCompose = Join-Path $RepositoryRoot 'docker-compose.demo-r2.yml'
$Phase37Environment = Join-Path $RepositoryRoot '.env.phase37'
$DemoEnvironment = Join-Path $RepositoryRoot '.env.demo-r2'
$DemoStateRoot = Join-Path $RepositoryRoot 'data\demo-r2\local-domain-state'
$DemoStateFile = Join-Path $DemoStateRoot 'state.json'
$DemoCertificate = Join-Path $RepositoryRoot 'data\demo-r2\tls\local-domain-demo-edge.crt'
$DemoKey = Join-Path $RepositoryRoot 'data\demo-r2\tls\local-domain-demo-edge.key'
$MainCertificateAuthority = Join-Path $RepositoryRoot 'data\phase3-7\tls\ca.crt'
$MainStateFile = Join-Path $RepositoryRoot 'data\phase3-7\local-domain-state\state.json'
$HostsPath = Join-Path $env:SystemRoot 'System32\drivers\etc\hosts'
$ClashRoot = Join-Path $env:APPDATA 'io.github.clash-verge-rev.clash-verge-rev'
$ClashGeneratedFile = Join-Path $ClashRoot 'clash-verge.yaml'
$ClashRuntimeFile = Join-Path $ClashRoot 'config.yaml'
$ClashVergeFile = Join-Path $ClashRoot 'verge.yaml'
$ClashBinary = 'D:\Clash\verge-mihomo.exe'
$HostsBegin = '# BEGIN JUNHUI DEMO R2'
$HostsEnd = '# END JUNHUI DEMO R2'
$BaseHostsBegin = '# BEGIN JUNHUI LOCAL PREVIEW'
$BaseHostsEnd = '# END JUNHUI LOCAL PREVIEW'
$BaseDomains = @(
    'junhuiscrewbarrel.com',
    'www.junhuiscrewbarrel.com',
    'admin.junhuiscrewbarrel.com',
    'api.junhuiscrewbarrel.com'
)
$DemoDomains = @(
    'demo.junhuiscrewbarrel.com',
    'admin-demo.junhuiscrewbarrel.com',
    'api-demo.junhuiscrewbarrel.com'
)
$DemoServices = @('postgres', 'redis', 'minio', 'minio-init', 'api', 'worker', 'website', 'admin')
$MainServices = @('postgres', 'redis', 'minio', 'minio-init', 'api', 'worker', 'website', 'admin')

New-Item -ItemType Directory -Force -Path $DemoStateRoot | Out-Null

function Test-IsAdministrator {
    <# 输入：无。输出：bool，当前进程是否具有管理员令牌。 #>
    $Identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $Principal = [Security.Principal.WindowsPrincipal]::new($Identity)
    return $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-StablePowerShellExecutable {
    <# 输入：无。输出：string，快捷方式可长期调用的 PowerShell 路径。 #>
    foreach ($Candidate in @(
        (Join-Path $env:ProgramFiles 'PowerShell\7\pwsh.exe'),
        (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe')
    )) {
        if (Test-Path -LiteralPath $Candidate) { return $Candidate }
    }
    throw '未找到可供快捷方式长期使用的 PowerShell。'
}

function Write-Utf8NoBom {
    <# 输入：Path 为文件路径，Content 为完整内容。输出：无；以 UTF-8 无 BOM 原子写入。 #>
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [string]$Content
    )
    $TemporaryPath = "$Path.demo-r2-tmp"
    [IO.File]::WriteAllText($TemporaryPath, $Content, [Text.UTF8Encoding]::new($false))
    Move-Item -Force -LiteralPath $TemporaryPath -Destination $Path
}

function Restart-ElevatedSetup {
    <# 输入：无。输出：无；通过一次 UAC 重新执行 Setup。 #>
    $PowerShell = Get-StablePowerShellExecutable
    $Arguments = @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', ('"{0}"' -f $LauncherPath),
        '-Action', 'Setup', '-NoElevation'
    )
    if ($NoOpen) { $Arguments += '-NoOpen' }
    Write-Host 'Demo R2 Setup 需要一次 UAC 以合并 hosts；脚本不会索取系统密码。'
    $Process = Start-Process -FilePath $PowerShell -ArgumentList $Arguments -Verb RunAs -Wait -PassThru
    exit $Process.ExitCode
}

function Get-MainComposeArguments {
    <# 输入：IncludeDemoEdge 指示是否挂接 Demo 边缘网络。输出：string[]，Compose 参数。 #>
    param([bool]$IncludeDemoEdge)
    $Arguments = @(
        'compose', '--env-file', $Phase37Environment,
        '-p', 'junhui-phase37-pilot',
        '-f', $BaseCompose,
        '-f', $Phase37Compose,
        '-f', $RuntimeCompose,
        '-f', $LocalCompose
    )
    if ($IncludeDemoEdge) { $Arguments += @('-f', $DemoEdgeCompose) }
    return $Arguments
}

function Get-DemoComposeArguments {
    <# 输入：无。输出：string[]，独立 Demo Compose 参数。 #>
    return @(
        'compose', '--env-file', $DemoEnvironment,
        '-p', 'junhui-demo-r2',
        '-f', $BaseCompose,
        '-f', $DemoCompose
    )
}

function Invoke-Compose {
    <# 输入：Arguments 为 docker 参数，Tail 为 Compose 子命令。输出：无，失败时抛错。 #>
    param(
        [Parameter(Mandatory)] [string[]]$Arguments,
        [Parameter(Mandatory)] [string[]]$Tail
    )
    & docker @($Arguments + $Tail)
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose 执行失败，退出码 $LASTEXITCODE。" }
}

function Get-ComposeConfig {
    <# 输入：Arguments 为 Compose 参数。输出：pscustomobject，合并后的运行配置。 #>
    param([Parameter(Mandatory)] [string[]]$Arguments)
    $Raw = & docker @($Arguments + @('config', '--format', 'json'))
    if ($LASTEXITCODE -ne 0) { throw '无法解析 Compose 最终配置。' }
    return ($Raw | ConvertFrom-Json)
}

function Assert-LoopbackIsolation {
    <# 输入：无。输出：无；验证共享入口与 Demo 服务没有直出端口和自动写库命令。 #>
    $MainConfig = Get-ComposeConfig -Arguments (Get-MainComposeArguments -IncludeDemoEdge $true)
    foreach ($Property in $MainConfig.services.PSObject.Properties) {
        $Ports = @($Property.Value.ports | Where-Object { $null -ne $_ -and $null -ne $_.target })
        if ($Property.Name -eq 'nginx') {
            if ($Ports.Count -ne 1 -or $Ports[0].host_ip -ne '127.0.0.1' -or [string]$Ports[0].published -ne '443') {
                throw '共享 Nginx 不是唯一的 127.0.0.1:443 入口。'
            }
        } elseif ($Ports.Count -gt 0) {
            throw "原实例服务 $($Property.Name) 意外发布宿主端口。"
        }
    }

    $DemoConfig = Get-ComposeConfig -Arguments (Get-DemoComposeArguments)
    foreach ($Property in $DemoConfig.services.PSObject.Properties) {
        $Ports = @($Property.Value.ports | Where-Object { $null -ne $_ -and $null -ne $_.target })
        if ($Ports.Count -gt 0) { throw "Demo 服务 $($Property.Name) 意外发布宿主端口。" }
        if ($Property.Value.network_mode -eq 'host') { throw "Demo 服务 $($Property.Name) 禁止使用 host network。" }
    }
    $ApiCommand = @($DemoConfig.services.api.command) -join ' '
    if ($ApiCommand -match '(?i)alembic|seed|demo-r2-setup') {
        throw "Demo API 普通启动命令包含迁移或初始化：$ApiCommand"
    }
    if ($DemoConfig.services.api.environment.DEMO_MODE -ne 'true') { throw 'Demo API 未显式启用 DEMO_MODE。' }
    if ($DemoConfig.services.api.environment.PUBLIC_SITEMAP_ENABLED -ne 'false') { throw 'Demo Sitemap 必须保持关闭。' }
}

function Install-DemoHosts {
    <# 输入：无。输出：无；以独立标记段把三个 Demo 域名精确映射到回环。 #>
    $Existing = [IO.File]::ReadAllText($HostsPath)
    $WithoutManaged = [regex]::Replace(
        $Existing,
        '(?ms)^# BEGIN JUNHUI DEMO R2\r?\n.*?^# END JUNHUI DEMO R2\r?\n?',
        ''
    )
    foreach ($Domain in $DemoDomains) {
        $Conflict = [regex]::Match($WithoutManaged, '(?im)^\s*(?!#)(\S+)\s+.*\b' + [regex]::Escape($Domain) + '\b.*$')
        if ($Conflict.Success) { throw "hosts 中已有非 Demo 管理的 $Domain 条目。" }
    }
    $Block = @($HostsBegin) + ($DemoDomains | ForEach-Object { "127.0.0.1 $_" }) + @($HostsEnd)
    Write-Utf8NoBom -Path $HostsPath -Content ($WithoutManaged.TrimEnd() + "`r`n`r`n" + ($Block -join "`r`n") + "`r`n")
}

function Install-BasePreviewHosts {
    <# 输入：无。输出：无；幂等恢复原 phase37 的四个回环 hosts，不改其他条目。 #>
    $Existing = [IO.File]::ReadAllText($HostsPath)
    $WithoutManaged = [regex]::Replace(
        $Existing,
        '(?ms)^# BEGIN JUNHUI LOCAL PREVIEW\r?\n.*?^# END JUNHUI LOCAL PREVIEW\r?\n?',
        ''
    )
    foreach ($Domain in $BaseDomains) {
        $Conflict = [regex]::Match($WithoutManaged, '(?im)^\s*(?!#)(\S+)\s+.*\b' + [regex]::Escape($Domain) + '\b.*$')
        if ($Conflict.Success) { throw "hosts 中已有非原预览管理的 $Domain 条目。" }
    }
    $Block = @($BaseHostsBegin) + ($BaseDomains | ForEach-Object { "127.0.0.1 $_" }) + @($BaseHostsEnd)
    Write-Utf8NoBom -Path $HostsPath -Content ($WithoutManaged.TrimEnd() + "`r`n`r`n" + ($Block -join "`r`n") + "`r`n")
}

function Remove-DemoHosts {
    <# 输入：无。输出：无；仅移除 Demo R2 标记段。 #>
    $Existing = [IO.File]::ReadAllText($HostsPath)
    $Updated = [regex]::Replace(
        $Existing,
        '(?ms)^# BEGIN JUNHUI DEMO R2\r?\n.*?^# END JUNHUI DEMO R2\r?\n?',
        ''
    )
    Write-Utf8NoBom -Path $HostsPath -Content ($Updated.TrimEnd() + "`r`n")
}

function Get-MainManagedScriptPath {
    <# 输入：无。输出：string，原本地域名 Setup 已登记的持久 Clash Script。 #>
    if (-not (Test-Path -LiteralPath $MainStateFile)) { throw '原本地域名状态文件不存在。' }
    $State = Get-Content -Raw -LiteralPath $MainStateFile | ConvertFrom-Json
    if (-not $State.managed_script_path -or -not (Test-Path -LiteralPath $State.managed_script_path)) {
        throw '无法定位原本地域名持久 Clash Script。'
    }
    return [string]$State.managed_script_path
}

function Ensure-BasePersistentClashScript {
    <# 输入：无。输出：无；恢复原持久包装并一次写入主站与 Demo 精确域名。 #>
    $ScriptPath = Get-MainManagedScriptPath
    $Text = [IO.File]::ReadAllText($ScriptPath)
    if ($Text.Contains('/* BEGIN JUNHUI LOCAL PREVIEW */')) { return }
    $MainPattern = [regex]'function\s+main\s*\('
    if (-not $MainPattern.IsMatch($Text)) { throw '当前 Clash Script 没有可安全包装的 main 函数。' }
    $Updated = $MainPattern.Replace($Text, 'function junhuiOriginalMain(', 1)
    $ManagedBlock = @'

/* BEGIN JUNHUI LOCAL PREVIEW */
// Exact loopback and DIRECT rules for the Junhui main preview and isolated Demo R2.
function main(config, profileName) {
  const nextConfig = junhuiOriginalMain(config, profileName) || config || {};
  const domains = [
    "junhuiscrewbarrel.com",
    "www.junhuiscrewbarrel.com",
    "admin.junhuiscrewbarrel.com",
    "api.junhuiscrewbarrel.com",
    "demo.junhuiscrewbarrel.com",
    "admin-demo.junhuiscrewbarrel.com",
    "api-demo.junhuiscrewbarrel.com",
  ];

  nextConfig.hosts = nextConfig.hosts && typeof nextConfig.hosts === "object" ? nextConfig.hosts : {};
  for (const domain of domains) nextConfig.hosts[domain] = "127.0.0.1";

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
  nextConfig.rules = [...directRules, ...existingRules.filter((rule) => !directRules.includes(rule))];
  return nextConfig;
}
/* END JUNHUI LOCAL PREVIEW */
'@
    Write-Utf8NoBom -Path $ScriptPath -Content ($Updated.TrimEnd() + "`r`n" + $ManagedBlock.TrimStart())
}

function Assert-BasePreviewInstalled {
    <# 输入：无。输出：无；确认原 phase37 本地域名规则已存在，避免重建或覆盖。 #>
    $Hosts = [IO.File]::ReadAllText($HostsPath)
    foreach ($Domain in $BaseDomains) {
        if ($Hosts -notmatch ('(?im)^127\.0\.0\.1\s+' + [regex]::Escape($Domain) + '\s*$')) {
            throw "原 phase37 hosts 缺少 $Domain。"
        }
    }
    $Script = [IO.File]::ReadAllText((Get-MainManagedScriptPath))
    if (-not $Script.Contains('/* BEGIN JUNHUI LOCAL PREVIEW */')) {
        throw '原 phase37 持久 Clash 管理块缺失。'
    }
}

function Test-MihomoConfiguration {
    <# 输入：无。输出：无；使用现有 Mihomo 校验当前运行配置语法。 #>
    if (-not (Test-Path -LiteralPath $ClashBinary)) { throw "未找到 Mihomo：$ClashBinary" }
    $Validation = & $ClashBinary -t -f $ClashGeneratedFile 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Mihomo 配置校验失败：$($Validation -join ' ')" }
}

function Reload-MihomoConfiguration {
    <# 输入：无。输出：无；通过回环控制器重载配置，密钥不写入日志。 #>
    $RuntimeLines = Get-Content -LiteralPath $ClashRuntimeFile
    $SecretLine = $RuntimeLines | Where-Object { $_ -match '^secret:' } | Select-Object -First 1
    $Secret = if ($SecretLine) { ($SecretLine -replace '^secret:\s*', '').Trim().Trim("'", '"') } else { '' }
    $Headers = @{}
    if ($Secret) { $Headers.Authorization = "Bearer $Secret" }
    $Body = @{ path = $ClashGeneratedFile } | ConvertTo-Json -Compress
    try {
        Invoke-RestMethod -Method Put -Uri 'http://127.0.0.1:9097/configs?force=true' -Headers $Headers -ContentType 'application/json' -Body $Body | Out-Null
    } catch {
        throw 'Mihomo 回环控制器未接受配置重载；控制器密钥未输出。'
    }
}

function Add-DemoProxyRules {
    <# 输入：无。输出：无；把三个域名加入现有持久/运行 DIRECT 与本地解析规则。 #>
    $ScriptPath = Get-MainManagedScriptPath
    $Script = [IO.File]::ReadAllText($ScriptPath)
    if (-not $Script.Contains('/* BEGIN JUNHUI LOCAL PREVIEW */')) { throw '原 Clash 安全管理块缺失。' }
    if (-not $Script.Contains('"demo.junhuiscrewbarrel.com"')) {
        $Needle = '    "api.junhuiscrewbarrel.com",'
        $Addition = @(
            $Needle,
            '    "demo.junhuiscrewbarrel.com",',
            '    "admin-demo.junhuiscrewbarrel.com",',
            '    "api-demo.junhuiscrewbarrel.com",'
        ) -join "`r`n"
        if (-not $Script.Contains($Needle)) { throw '无法在持久 Clash Script 中定位域名数组。' }
        Write-Utf8NoBom -Path $ScriptPath -Content ($Script.Replace($Needle, $Addition))
    }

    $Generated = [IO.File]::ReadAllText($ClashGeneratedFile)
    $Insertions = @(
        @('  api.junhuiscrewbarrel.com: 127.0.0.1', @(
            '  demo.junhuiscrewbarrel.com: 127.0.0.1',
            '  admin-demo.junhuiscrewbarrel.com: 127.0.0.1',
            '  api-demo.junhuiscrewbarrel.com: 127.0.0.1'
        )),
        @('  - api.junhuiscrewbarrel.com', @(
            '  - demo.junhuiscrewbarrel.com',
            '  - admin-demo.junhuiscrewbarrel.com',
            '  - api-demo.junhuiscrewbarrel.com'
        )),
        @('- DOMAIN,api.junhuiscrewbarrel.com,DIRECT', @(
            '- DOMAIN,demo.junhuiscrewbarrel.com,DIRECT',
            '- DOMAIN,admin-demo.junhuiscrewbarrel.com,DIRECT',
            '- DOMAIN,api-demo.junhuiscrewbarrel.com,DIRECT'
        ))
    )
    foreach ($Insertion in $Insertions) {
        $Needle = [string]$Insertion[0]
        $Lines = [string[]]$Insertion[1]
        if (-not $Generated.Contains($Lines[0])) {
            if (-not $Generated.Contains($Needle)) { throw "无法在 Clash 运行配置定位：$Needle" }
            $Generated = $Generated.Replace($Needle, $Needle + "`r`n" + ($Lines -join "`r`n"))
        }
    }
    Write-Utf8NoBom -Path $ClashGeneratedFile -Content $Generated
    Update-ProxyBypass -Install $true
}

function Remove-DemoProxyRules {
    <# 输入：无。输出：无；只移除三个 Demo 域名，不影响原站与其他代理规则。 #>
    $Paths = @($ClashGeneratedFile)
    try { $Paths += Get-MainManagedScriptPath } catch {}
    foreach ($Path in $Paths | Select-Object -Unique) {
        if (-not (Test-Path -LiteralPath $Path)) { continue }
        $Lines = [IO.File]::ReadAllLines($Path)
        $Filtered = @($Lines | Where-Object {
            $Line = $_
            -not ($DemoDomains | Where-Object { $Line.Contains($_) })
        })
        Write-Utf8NoBom -Path $Path -Content (($Filtered -join "`r`n").TrimEnd() + "`r`n")
    }
    Update-ProxyBypass -Install $false
}

function Update-ProxyBypass {
    <# 输入：Install 指示添加或删除。输出：无；更新 Clash 与 Windows 的精确代理绕过项。 #>
    param([bool]$Install)
    $Verge = [IO.File]::ReadAllText($ClashVergeFile)
    $Match = [regex]::Match($Verge, '(?m)^system_proxy_bypass:\s*(.*)$')
    if (-not $Match.Success) { throw 'Clash Verge 缺少 system_proxy_bypass。' }
    $Items = @($Match.Groups[1].Value.Trim().Trim("'", '"') -split '[;,]' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($Install) {
        foreach ($Domain in $DemoDomains) { if ($Items -notcontains $Domain) { $Items += $Domain } }
    } else {
        $Items = @($Items | Where-Object { $DemoDomains -notcontains $_ })
    }
    $NewValue = ($Items -join ';').Replace("'", "''")
    $Verge = [regex]::Replace($Verge, '(?m)^system_proxy_bypass:\s*.*$', "system_proxy_bypass: '$NewValue'", 1)
    Write-Utf8NoBom -Path $ClashVergeFile -Content $Verge

    $RegistryPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
    $Current = (Get-ItemProperty -Path $RegistryPath -Name ProxyOverride -ErrorAction SilentlyContinue).ProxyOverride
    $RegistryItems = @($Current -split ';' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($Install) {
        foreach ($Domain in $DemoDomains) { if ($RegistryItems -notcontains $Domain) { $RegistryItems += $Domain } }
    } else {
        $RegistryItems = @($RegistryItems | Where-Object { $DemoDomains -notcontains $_ })
    }
    Set-ItemProperty -Path $RegistryPath -Name ProxyOverride -Value ($RegistryItems -join ';')
}

function Assert-DemoCertificate {
    <# 输入：无。输出：无；验证证书由现有本地 CA 签发并覆盖三个 Demo 域名。 #>
    foreach ($Path in @($DemoCertificate, $DemoKey, $MainCertificateAuthority)) {
        if (-not (Test-Path -LiteralPath $Path)) { throw "Demo TLS 文件缺失：$Path" }
    }
    $OpenSsl = (Get-Command openssl -ErrorAction Stop).Source
    & $OpenSsl verify -CAfile $MainCertificateAuthority $DemoCertificate | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Demo TLS 证书无法由现有本地 CA 验证。' }
    $San = (& $OpenSsl x509 -in $DemoCertificate -noout -ext subjectAltName 2>&1) -join ' '
    foreach ($Domain in $DemoDomains) {
        if ($San -notmatch ('DNS:' + [regex]::Escape($Domain))) { throw "Demo TLS 证书缺少 $Domain。" }
    }
}

function Test-DemoInstalled {
    <# 输入：无。输出：无；确认日常 Start 所需的一次性配置已存在。 #>
    $Hosts = [IO.File]::ReadAllText($HostsPath)
    foreach ($Domain in $DemoDomains) {
        if ($Hosts -notmatch ('(?im)^127\.0\.0\.1\s+' + [regex]::Escape($Domain) + '\s*$')) {
            throw "hosts 缺少 $Domain；请先运行 Setup。"
        }
    }
    Assert-DemoCertificate
}

function New-DemoShortcut {
    <# 输入：无。输出：string，桌面快捷方式完整路径。 #>
    $ShortcutPath = Join-Path ([Environment]::GetFolderPath('Desktop')) '打开骏辉完整演示站.lnk'
    $Shell = New-Object -ComObject WScript.Shell
    $Shortcut = $Shell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = Get-StablePowerShellExecutable
    $Shortcut.Arguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" -Action Start' -f $LauncherPath
    $Shortcut.WorkingDirectory = $RepositoryRoot
    $Shortcut.Description = '启动并打开骏辉独立 Demo R2 中英文官网'
    $Shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,220"
    $Shortcut.Save()
    return $ShortcutPath
}

function Wait-DemoHealthy {
    <# 输入：TimeoutSeconds 为最长等待时长。输出：无；验证真实 HTTPS 正文和后台登录页。 #>
    param([int]$TimeoutSeconds = 240)
    $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            $Website = Invoke-WebRequest -Uri 'https://demo.junhuiscrewbarrel.com/zh-cn/' -TimeoutSec 10 -UseBasicParsing
            $Admin = Invoke-WebRequest -Uri 'https://admin-demo.junhuiscrewbarrel.com/login' -TimeoutSec 10 -UseBasicParsing
            if (
                $Website.StatusCode -eq 200 -and
                $Admin.StatusCode -eq 200 -and
                $Website.Headers['X-Junhui-Local-Preview'] -eq 'demo-r2-loopback-only' -and
                $Website.Content -match 'JUNHUI'
            ) { return }
        } catch {
            # 服务重建期间继续等待，绝不跳过 TLS 验证。
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $Deadline)
    throw 'Demo R2 在等待期限内未通过真实域名健康检查。'
}

function Install-Demo {
    <# 输入：无。输出：无；一次性安装 hosts、DIRECT、证书校验和快捷方式。 #>
    if (-not (Test-IsAdministrator)) {
        if ($NoElevation) { throw 'Setup 需要管理员权限写 hosts；UAC 提升未成功。' }
        Restart-ElevatedSetup
    }
    Install-BasePreviewHosts
    Ensure-BasePersistentClashScript
    Assert-BasePreviewInstalled
    Assert-DemoCertificate
    Assert-LoopbackIsolation
    Install-DemoHosts
    Add-DemoProxyRules
    Test-MihomoConfiguration
    Reload-MihomoConfiguration
    $Shortcut = New-DemoShortcut
    $State = [ordered]@{
        schema_version = 1
        installed_at = (Get-Date).ToString('o')
        repository = $RepositoryRoot
        compose_project = 'junhui-demo-r2'
        domains = $DemoDomains
        shortcut = $Shortcut
    }
    Write-Utf8NoBom -Path $DemoStateFile -Content (($State | ConvertTo-Json -Depth 4) + "`r`n")
    Write-Host "DEMO_R2_SETUP_OK SHORTCUT=$Shortcut"
}

function Start-Demo {
    <# 输入：无。输出：无；启动独立 Demo 数据栈和共享回环入口，不执行迁移或 Seed。 #>
    Test-DemoInstalled
    Assert-LoopbackIsolation
    & docker network inspect junhui_demo_r2_edge | Out-Null
    if ($LASTEXITCODE -ne 0) {
        & docker network create junhui_demo_r2_edge | Out-Null
        if ($LASTEXITCODE -ne 0) { throw '无法创建 Demo 边缘网络。' }
    }
    Invoke-Compose -Arguments (Get-DemoComposeArguments) -Tail (@('up', '-d', '--no-build') + $DemoServices)
    Invoke-Compose -Arguments (Get-MainComposeArguments -IncludeDemoEdge $false) -Tail (@('up', '-d', '--no-build') + $MainServices)
    Invoke-Compose -Arguments (Get-MainComposeArguments -IncludeDemoEdge $true) -Tail @('up', '-d', '--no-build', '--force-recreate', 'nginx')
    Wait-DemoHealthy
    Write-Host 'DEMO_R2_LOOPBACK_PREVIEW_HEALTHY'
    Write-Host 'Website: https://demo.junhuiscrewbarrel.com/zh-cn/'
    Write-Host 'Admin:   https://admin-demo.junhuiscrewbarrel.com/'
    if (-not $NoOpen) { Start-Process 'https://demo.junhuiscrewbarrel.com/zh-cn/' }
}

function Stop-Demo {
    <# 输入：无。输出：无；停止 Demo 服务并恢复原本地域名网关，保留全部 Demo 卷。 #>
    Invoke-Compose -Arguments (Get-DemoComposeArguments) -Tail (@('stop') + $DemoServices)
    Invoke-Compose -Arguments (Get-MainComposeArguments -IncludeDemoEdge $false) -Tail @('up', '-d', '--no-build', '--force-recreate', 'nginx')
    Write-Host 'DEMO_R2_STOPPED_DATA_PRESERVED_MAIN_PREVIEW_RUNNING'
}

function Restore-Demo {
    <# 输入：无。输出：无；仅撤回 Demo 域名/代理/快捷方式，保留原站和 Demo 数据卷。 #>
    if (-not (Test-IsAdministrator)) { throw 'Restore 需要管理员 PowerShell 以移除 Demo hosts 标记段。' }
    try { Stop-Demo } catch { Write-Warning $_.Exception.Message }
    Remove-DemoProxyRules
    Remove-DemoHosts
    Test-MihomoConfiguration
    Reload-MihomoConfiguration
    $Shortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) '打开骏辉完整演示站.lnk'
    if (Test-Path -LiteralPath $Shortcut) { Remove-Item -LiteralPath $Shortcut }
    Write-Host 'DEMO_R2_LOCAL_SETTINGS_RESTORED_DATA_PRESERVED'
}

function Show-DemoStatus {
    <# 输入：无。输出：无；显示脱敏配置、监听、解析和容器状态。 #>
    Write-Host "Repository: $RepositoryRoot"
    try { Assert-LoopbackIsolation; Write-Host 'Compose loopback isolation: PASS' } catch { Write-Host "Compose loopback isolation: FAIL - $($_.Exception.Message)" }
    $Hosts = [IO.File]::ReadAllText($HostsPath)
    foreach ($Domain in $DemoDomains) {
        $Managed = $Hosts -match ('(?im)^127\.0\.0\.1\s+' + [regex]::Escape($Domain) + '\s*$')
        Write-Host "Hosts $Domain -> $(if ($Managed) { '127.0.0.1' } else { 'NOT_INSTALLED' })"
    }
    try { Assert-DemoCertificate; Write-Host 'TLS SAN and CA verification: PASS' } catch { Write-Host "TLS: FAIL - $($_.Exception.Message)" }
    & docker ps -a --filter 'label=com.docker.compose.project=junhui-demo-r2' --format '{{.Names}}|{{.Status}}|{{.Ports}}'
    Get-NetTCPConnection -State Listen -LocalPort 443 -ErrorAction SilentlyContinue |
        Select-Object LocalAddress, LocalPort, OwningProcess |
        Format-Table -AutoSize
    Write-Host 'URLs:'
    Write-Host '  https://demo.junhuiscrewbarrel.com/zh-cn/'
    Write-Host '  https://demo.junhuiscrewbarrel.com/en/'
    Write-Host '  https://admin-demo.junhuiscrewbarrel.com/'
}

switch ($Action) {
    'Setup' { Install-Demo }
    'Start' { Start-Demo }
    'Status' { Show-DemoStatus }
    'Stop' { Stop-Demo }
    'Restore' { Restore-Demo }
}
