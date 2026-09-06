# 脚本用途：保存不含凭据、RFQ 编号和私有路径的真实 API/SSR 断言证据。
[CmdletBinding()]
param(
    [string]$BaseUrl = 'http://localhost:8080',
    [string]$RunId = 'remediation-20260905',
    [string]$OutputDir = "artifacts/phase3-6-qa-closeout/$RunId"
)

$ErrorActionPreference = 'Stop'
$homeResponse = Invoke-RestMethod "$BaseUrl/api/v1/public/home/en"
$homeZhResponse = Invoke-RestMethod "$BaseUrl/api/v1/public/home/zh-cn"
$productDetail = Invoke-RestMethod "$BaseUrl/api/v1/public/products/en/qa36-$RunId-screws/qa36-$RunId-extrusion-screw"
$company = Invoke-RestMethod "$BaseUrl/api/v1/public/company-profile/en"
$caseStudy = Invoke-RestMethod "$BaseUrl/api/v1/public/case-studies/en/qa36-$RunId-anonymous-case"
$capability = Invoke-RestMethod "$BaseUrl/api/v1/public/trust/capabilities/en/qa36-$RunId-capability"
$downloads = Invoke-RestMethod "$BaseUrl/api/v1/public/downloads/en"
$material = Invoke-RestMethod "$BaseUrl/api/v1/public/materials/en/qa36-$RunId-material"
$solution = Invoke-RestMethod "$BaseUrl/api/v1/public/solutions/en/qa36-$RunId-solution"
$knowledgeWithAuthor = @($homeResponse.data.knowledge | Where-Object { $_.author })[0]
$knowledgeEn = Invoke-RestMethod "$BaseUrl/api/v1/public/knowledge/en?page_size=48"
$knowledgeZh = Invoke-RestMethod "$BaseUrl/api/v1/public/knowledge/zh-cn?page_size=48"
$pageTwo = Invoke-RestMethod "$BaseUrl/api/v1/public/products/en?page=2&page_size=24"
$temporary = Invoke-RestMethod "$BaseUrl/api/v1/public/products/en?page=1&page_size=12"
$outOfRange = Invoke-WebRequest -UseBasicParsing -SkipHttpErrorCheck "$BaseUrl/api/v1/public/products/en?page=99&page_size=24"
$invalidFilter = Invoke-WebRequest -UseBasicParsing -SkipHttpErrorCheck "$BaseUrl/api/v1/public/products/en?material=missing-filter"
$zeroResult = Invoke-WebRequest -UseBasicParsing -SkipHttpErrorCheck "$BaseUrl/api/v1/public/products/en?material=qa36-$RunId-unmatched-material"
$draft = Invoke-WebRequest -UseBasicParsing -SkipHttpErrorCheck "$BaseUrl/api/v1/public/products/en/qa36-$RunId-screws/qa36-$RunId-draft-product"
$noindex = Invoke-WebRequest -UseBasicParsing -SkipHttpErrorCheck "$BaseUrl/api/v1/public/products/en/qa36-$RunId-screws/qa36-$RunId-noindex-product"
$ssr = Invoke-WebRequest -UseBasicParsing -SkipHttpErrorCheck "$BaseUrl/en/"
$html = $ssr.Content
$ids = [regex]::Matches($html, ' id="([^"]+)"') | ForEach-Object { $_.Groups[1].Value }
$duplicates = @($ids | Group-Object | Where-Object Count -gt 1 | Select-Object -ExpandProperty Name)
$ssrZh = Invoke-WebRequest -UseBasicParsing -SkipHttpErrorCheck "$BaseUrl/zh-cn/"
$htmlZh = $ssrZh.Content
$zhIds = [regex]::Matches($htmlZh, ' id="([^"]+)"') | ForEach-Object { $_.Groups[1].Value }
$zhDuplicates = @($zhIds | Group-Object | Where-Object Count -gt 1 | Select-Object -ExpandProperty Name)

$evidence = [ordered]@{
    run_id = $RunId
    generated_at = (Get-Date).ToUniversalTime().ToString('o')
    home_api = [ordered]@{
        success = $homeResponse.success
        canonical = $homeResponse.data.seo.canonical
        robots = $homeResponse.data.seo.robots
        description_present = [bool]$homeResponse.data.seo.description
        schema_count = @($homeResponse.data.schema).Count
        featured_product_media_present = [bool]$homeResponse.data.featured_products[0].media.src
        featured_product_spec_types = @($homeResponse.data.featured_products[0].specifications | ForEach-Object { $_.type })
        knowledge_author_present = [bool]$knowledgeWithAuthor.author
        knowledge_published_at_present = [bool]$knowledgeWithAuthor.published_at
    }
    home_api_zh = [ordered]@{
        success = $homeZhResponse.success
        canonical = $homeZhResponse.data.seo.canonical
        robots = $homeZhResponse.data.seo.robots
        description_present = [bool]$homeZhResponse.data.seo.description
        schema_count = @($homeZhResponse.data.schema).Count
        english_alternate = $homeZhResponse.data.seo.hreflang.en
        self_alternate = $homeZhResponse.data.seo.hreflang.'zh-CN'
    }
    product_detail_api = [ordered]@{
        specification_count = @($productDetail.data.specifications).Count
        specification_types = @($productDetail.data.specifications | ForEach-Object { $_.type })
    }
    qa_fixture = [ordered]@{
        company_public = [bool]$company.data.company_name
        material_public = $material.data.slug -eq "qa36-$RunId-material"
        solution_public = $solution.data.slug -eq "qa36-$RunId-solution"
        capability_equipment_count = @($capability.data.equipment).Count
        anonymous_case_private_name_absent = -not (($caseStudy.data | ConvertTo-Json -Depth 8) -match 'QA PRIVATE CLIENT')
        public_download_count = @($downloads.data | Where-Object { $_.slug -eq "qa36-$RunId-datasheet" }).Count
        knowledge_en_total = $knowledgeEn.data.total
        knowledge_zh_total = $knowledgeZh.data.total
        draft_status = $draft.StatusCode
        noindex_status = $noindex.StatusCode
    }
    listing_api = [ordered]@{
        page_two_canonical = $pageTwo.data.seo.canonical
        page_two_items = @($pageTwo.data.items).Count
        temporary_page_size_robots = $temporary.data.seo.robots
        temporary_page_size_hreflang_count = @($temporary.data.seo.hreflang.PSObject.Properties).Count
        out_of_range_status = $outOfRange.StatusCode
        invalid_filter_status = $invalidFilter.StatusCode
        zero_result_status = $zeroResult.StatusCode
    }
    home_ssr = [ordered]@{
        status = $ssr.StatusCode
        description_present = $html -match '<meta name="description"'
        self_canonical_present = $html -match '<link rel="canonical" href="https://junhuiscrewbarrel.com/en/"'
        alternate_present = $html -match 'hreflang="zh-CN"'
        json_ld_present = $html -match 'application/ld\+json'
        main_count = [regex]::Matches($html, '<main(?:\s|>)').Count
        main_content_count = [regex]::Matches($html, 'id="main-content"').Count
        h1_count = [regex]::Matches($html, '<h1(?:\s|>)').Count
        duplicate_ids = $duplicates
        skip_link_present = $html -match 'href="#main-content"'
    }
    home_ssr_zh = [ordered]@{
        status = $ssrZh.StatusCode
        description_present = $htmlZh -match '<meta name="description"'
        self_canonical_present = $htmlZh -match '<link rel="canonical" href="https://junhuiscrewbarrel.com/zh-cn/"'
        alternate_present = $htmlZh -match 'hreflang="en"'
        json_ld_present = $htmlZh -match 'application/ld\+json'
        main_count = [regex]::Matches($htmlZh, '<main(?:\s|>)').Count
        main_content_count = [regex]::Matches($htmlZh, 'id="main-content"').Count
        h1_count = [regex]::Matches($htmlZh, '<h1(?:\s|>)').Count
        duplicate_ids = $zhDuplicates
        skip_link_present = $htmlZh -match 'href="#main-content"'
    }
}

if (
    -not $evidence.home_api.success -or
    $evidence.home_api.canonical -ne 'https://junhuiscrewbarrel.com/en/' -or
    $evidence.home_api.schema_count -lt 1 -or
    -not $evidence.home_api.featured_product_media_present -or
    $evidence.product_detail_api.specification_count -ne 5 -or
    @($evidence.product_detail_api.specification_types | Sort-Object) -join ',' -ne 'boolean,enum,number,range,text' -or
    -not $evidence.home_api.knowledge_author_present -or
    -not $evidence.home_api.knowledge_published_at_present -or
    -not $evidence.home_api_zh.success -or
    $evidence.home_api_zh.canonical -ne 'https://junhuiscrewbarrel.com/zh-cn/' -or
    $evidence.home_api_zh.english_alternate -ne 'https://junhuiscrewbarrel.com/en/' -or
    $evidence.home_api_zh.self_alternate -ne 'https://junhuiscrewbarrel.com/zh-cn/' -or
    -not $evidence.qa_fixture.company_public -or
    -not $evidence.qa_fixture.material_public -or
    -not $evidence.qa_fixture.solution_public -or
    $evidence.qa_fixture.capability_equipment_count -lt 1 -or
    -not $evidence.qa_fixture.anonymous_case_private_name_absent -or
    $evidence.qa_fixture.public_download_count -ne 1 -or
    $evidence.qa_fixture.knowledge_en_total -le $evidence.qa_fixture.knowledge_zh_total -or
    $evidence.qa_fixture.draft_status -ne 404 -or
    $evidence.qa_fixture.noindex_status -ne 404 -or
    $evidence.listing_api.page_two_canonical -ne 'https://junhuiscrewbarrel.com/en/products/?page=2' -or
    $evidence.listing_api.temporary_page_size_robots -ne 'noindex, follow' -or
    $evidence.listing_api.temporary_page_size_hreflang_count -ne 0 -or
    $evidence.listing_api.out_of_range_status -ne 404 -or
    $evidence.listing_api.invalid_filter_status -ne 404 -or
    $evidence.listing_api.zero_result_status -ne 404 -or
    $evidence.home_ssr.status -ne 200 -or
    -not $evidence.home_ssr.description_present -or
    -not $evidence.home_ssr.self_canonical_present -or
    -not $evidence.home_ssr.alternate_present -or
    -not $evidence.home_ssr.json_ld_present -or
    -not $evidence.home_ssr.skip_link_present -or
    $evidence.home_ssr.main_count -ne 1 -or
    $evidence.home_ssr.main_content_count -ne 1 -or
    $evidence.home_ssr.h1_count -ne 1 -or
    $evidence.home_ssr.duplicate_ids.Count -ne 0 -or
    $evidence.home_ssr_zh.status -ne 200 -or
    -not $evidence.home_ssr_zh.description_present -or
    -not $evidence.home_ssr_zh.self_canonical_present -or
    -not $evidence.home_ssr_zh.alternate_present -or
    -not $evidence.home_ssr_zh.json_ld_present -or
    -not $evidence.home_ssr_zh.skip_link_present -or
    $evidence.home_ssr_zh.main_count -ne 1 -or
    $evidence.home_ssr_zh.main_content_count -ne 1 -or
    $evidence.home_ssr_zh.h1_count -ne 1 -or
    $evidence.home_ssr_zh.duplicate_ids.Count -ne 0
) {
    throw 'Phase 3.6 HTTP/SSR evidence assertions failed.'
}

New-Item -ItemType Directory -Force $OutputDir | Out-Null
$json = $evidence | ConvertTo-Json -Depth 8
Set-Content -LiteralPath (Join-Path $OutputDir 'http-ssr-evidence.json') -Value $json -Encoding utf8
$json
