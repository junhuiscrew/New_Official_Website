# 脚本用途：验证 Phase 3.1 本地 Compose 服务与关键 HTTP 端点。
$ErrorActionPreference = "Stop"
$apiHostPort = if ([string]::IsNullOrWhiteSpace($env:API_HOST_PORT)) { 8010 } else { $env:API_HOST_PORT }

docker compose ps

function Assert-HttpStatus {
    <#
    用途：通过 .NET HTTP 请求验证本地端点状态码。
    输入：Url 为目标地址，ExpectedStatus 为预期状态码。
    输出：无；状态不匹配时抛出异常。
    #>
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][int]$ExpectedStatus
    )

    $request = [System.Net.HttpWebRequest]::Create($Url)
    $request.AllowAutoRedirect = $false
    $response = $null
    try {
        $response = $request.GetResponse()
        $actualStatus = [int]$response.StatusCode
    }
    catch [System.Net.WebException] {
        if ($null -eq $_.Exception.Response) {
            throw
        }
        $response = $_.Exception.Response
        $actualStatus = [int]$response.StatusCode
    }
    finally {
        if ($null -ne $response) {
            $response.Close()
        }
    }

    if ($actualStatus -ne $ExpectedStatus) {
        throw "HTTP check failed for $Url. Expected $ExpectedStatus, got $actualStatus."
    }
}

# 分别验证 API、根路径跳转、两种语言、管理后台与 Nginx 代理。
Assert-HttpStatus -Url "http://localhost:$apiHostPort/api/v1/health" -ExpectedStatus 200
Assert-HttpStatus -Url "http://localhost:3000/" -ExpectedStatus 308
Assert-HttpStatus -Url "http://localhost:3000/zh-cn/" -ExpectedStatus 200
Assert-HttpStatus -Url "http://localhost:3000/en/" -ExpectedStatus 200
Assert-HttpStatus -Url "http://localhost:3001/" -ExpectedStatus 200
Assert-HttpStatus -Url "http://localhost:8080/en/" -ExpectedStatus 200

Write-Host "Phase 3.1 local verification passed."
