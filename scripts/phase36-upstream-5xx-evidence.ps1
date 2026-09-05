# 脚本用途：本地短暂停止 API，证明 Nuxt SSR 将真实上游故障保留为可恢复的 500。
[CmdletBinding()]
param(
    [string]$BaseUrl = 'http://localhost:8080',
    [string]$RateLimitNamespace = 'rfq:public:qa36:remediation-20260905'
)

$ErrorActionPreference = 'Stop'
$failureResponse = $null

try {
    docker compose stop api | Out-Null
    Start-Sleep -Seconds 2
    $failureResponse = Invoke-WebRequest `
        -UseBasicParsing `
        -SkipHttpErrorCheck `
        "$BaseUrl/en/products/?qa-upstream-failure=1"
}
finally {
    # 无论断言是否成功都恢复本地 API，并保留本轮独立限流命名空间。
    $env:RFQ_RATE_LIMIT_NAMESPACE = $RateLimitNamespace
    docker compose up -d api | Out-Null
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $health = Invoke-WebRequest `
                -UseBasicParsing `
                -TimeoutSec 2 `
                "$BaseUrl/api/v1/health/ready"
            if ($health.StatusCode -eq 200) {
                break
            }
        }
        catch {
            Start-Sleep -Seconds 1
        }
    }
}

$body = if ($null -ne $failureResponse) { $failureResponse.Content } else { '' }
$evidence = [ordered]@{
    generated_at = (Get-Date).ToUniversalTime().ToString('o')
    upstream_unavailable_status = $failureResponse.StatusCode
    friendly_recovery_present = $body -match 'temporarily unavailable'
    internal_error_absent = $body -notmatch '(Traceback|asyncpg|redis://|postgresql://)'
    api_restored_status = $health.StatusCode
}

if (
    $evidence.upstream_unavailable_status -ne 500 -or
    -not $evidence.friendly_recovery_present -or
    -not $evidence.internal_error_absent -or
    $evidence.api_restored_status -ne 200
) {
    throw 'Phase 3.6 upstream 5xx evidence assertions failed.'
}

New-Item -ItemType Directory -Force artifacts/phase3-6-remediation | Out-Null
$json = $evidence | ConvertTo-Json -Depth 4
Set-Content `
    -LiteralPath artifacts/phase3-6-remediation/upstream-5xx-evidence.json `
    -Value $json `
    -Encoding utf8
$json
