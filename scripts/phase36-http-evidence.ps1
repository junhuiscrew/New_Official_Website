# 脚本用途：保存不含凭据、RFQ 编号和私有路径的真实 API/SSR 断言证据。
[CmdletBinding()]
param(
    [string]$BaseUrl = 'http://localhost:8080'
)

$ErrorActionPreference = 'Stop'
$homeResponse = Invoke-RestMethod "$BaseUrl/api/v1/public/home/en"
$pageTwo = Invoke-RestMethod "$BaseUrl/api/v1/public/products/en?page=2&page_size=24"
$temporary = Invoke-RestMethod "$BaseUrl/api/v1/public/products/en?page=1&page_size=12"
$outOfRange = Invoke-WebRequest -UseBasicParsing -SkipHttpErrorCheck "$BaseUrl/api/v1/public/products/en?page=99&page_size=24"
$ssr = Invoke-WebRequest -UseBasicParsing -SkipHttpErrorCheck "$BaseUrl/en/"
$html = $ssr.Content
$ids = [regex]::Matches($html, ' id="([^"]+)"') | ForEach-Object { $_.Groups[1].Value }
$duplicates = @($ids | Group-Object | Where-Object Count -gt 1 | Select-Object -ExpandProperty Name)

$evidence = [ordered]@{
    generated_at = (Get-Date).ToUniversalTime().ToString('o')
    home_api = [ordered]@{
        success = $homeResponse.success
        canonical = $homeResponse.data.seo.canonical
        robots = $homeResponse.data.seo.robots
        description_present = [bool]$homeResponse.data.seo.description
        schema_count = @($homeResponse.data.schema).Count
        featured_product_media_present = [bool]$homeResponse.data.featured_products[0].media.src
        knowledge_author_present = [bool]$homeResponse.data.knowledge[0].author
        knowledge_published_at_present = [bool]$homeResponse.data.knowledge[0].published_at
    }
    listing_api = [ordered]@{
        page_two_canonical = $pageTwo.data.seo.canonical
        page_two_items = @($pageTwo.data.items).Count
        temporary_page_size_robots = $temporary.data.seo.robots
        temporary_page_size_hreflang_count = @($temporary.data.seo.hreflang.PSObject.Properties).Count
        out_of_range_status = $outOfRange.StatusCode
    }
    home_ssr = [ordered]@{
        status = $ssr.StatusCode
        description_present = $html -match '<meta name="description"'
        self_canonical_present = $html -match 'https://junhuiscrewbarrel.com/en/'
        alternate_present = $html -match 'hreflang="zh-CN"'
        json_ld_present = $html -match 'application/ld\+json'
        main_count = [regex]::Matches($html, '<main(?:\s|>)').Count
        main_content_count = [regex]::Matches($html, 'id="main-content"').Count
        h1_count = [regex]::Matches($html, '<h1(?:\s|>)').Count
        duplicate_ids = $duplicates
        skip_link_present = $html -match 'href="#main-content"'
    }
}

if (
    -not $evidence.home_api.success -or
    $evidence.home_api.canonical -ne 'https://junhuiscrewbarrel.com/en/' -or
    $evidence.home_api.schema_count -lt 1 -or
    -not $evidence.home_api.featured_product_media_present -or
    $evidence.listing_api.page_two_canonical -ne 'https://junhuiscrewbarrel.com/en/products/?page=2' -or
    $evidence.listing_api.temporary_page_size_robots -ne 'noindex, follow' -or
    $evidence.listing_api.temporary_page_size_hreflang_count -ne 0 -or
    $evidence.listing_api.out_of_range_status -ne 404 -or
    $evidence.home_ssr.status -ne 200 -or
    $evidence.home_ssr.main_count -ne 1 -or
    $evidence.home_ssr.main_content_count -ne 1 -or
    $evidence.home_ssr.h1_count -ne 1 -or
    $evidence.home_ssr.duplicate_ids.Count -ne 0
) {
    throw 'Phase 3.6 HTTP/SSR evidence assertions failed.'
}

New-Item -ItemType Directory -Force artifacts/phase3-6-remediation | Out-Null
$json = $evidence | ConvertTo-Json -Depth 8
Set-Content -LiteralPath artifacts/phase3-6-remediation/http-ssr-evidence.json -Value $json -Encoding utf8
$json
