param(
    [string]$MediaRoot = "data/demo-r2/media",
    [string]$OutputPath = "data/demo-r2/media-manifest.json"
)

$ErrorActionPreference = "Stop"

<#
.SYNOPSIS
    为 Demo R2 私有媒体目录生成严格、可重复的导入清单。

.DESCRIPTION
    输入：MediaRoot 为实际媒体根目录，OutputPath 为清单输出路径。
    输出：符合 DemoMediaManifest 的 JSON，并核验每个文件真实存在。
#>

function New-DemoMediaItem {
    <#
    创建一条媒体清单记录。

    输入：别名、相对文件、类型、来源、槽位、双语alt及可选视频时长。
    输出：pscustomobject，可序列化的媒体清单项。
    #>
    param(
        [string]$Alias,
        [string]$File,
        [ValidateSet("image", "video", "document")]
        [string]$Kind,
        [ValidateSet("approved_public_copy", "generated_demo", "licensed_demo")]
        [string]$ContentOrigin,
        [string[]]$Slots,
        [string]$AltZh,
        [string]$AltEn,
        [Nullable[double]]$DurationSeconds = $null
    )

    $item = [ordered]@{
        alias = $Alias
        file = $File
        kind = $Kind
        content_origin = $ContentOrigin
        slots = $Slots
        alt_zh = $AltZh
        alt_en = $AltEn
    }
    if ($null -ne $DurationSeconds) {
        $item.duration_seconds = $DurationSeconds
    }
    return [pscustomobject]$item
}

$resolvedMediaRoot = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $MediaRoot))
$assets = [System.Collections.Generic.List[object]]::new()

# 三张既有产品图只读复制进隔离 Demo 媒体库，不改原文件与原实例关联。
$assets.Add((New-DemoMediaItem -Alias "APPROVED-PRODUCT-01" -File "images/approved-product-01.webp" -Kind image -ContentOrigin approved_public_copy -Slots @("IMAGE-PRODUCT-01") -AltZh "氮化螺杆产品图（已批准公开素材只读副本）" -AltEn "Nitrided screw product image (read-only copy of approved public media)"))
$assets.Add((New-DemoMediaItem -Alias "APPROVED-PRODUCT-02" -File "images/approved-product-02.webp" -Kind image -ContentOrigin approved_public_copy -Slots @("IMAGE-PRODUCT-02") -AltZh "氮化机筒产品图（已批准公开素材只读副本）" -AltEn "Nitrided barrel product image (read-only copy of approved public media)"))
$assets.Add((New-DemoMediaItem -Alias "APPROVED-PRODUCT-03" -File "images/approved-product-03.webp" -Kind image -ContentOrigin approved_public_copy -Slots @("IMAGE-PRODUCT-03") -AltZh "电镀螺杆产品图（已批准公开素材只读副本）" -AltEn "Electroplated screw product image (read-only copy of approved public media)"))

# 40 张生成式工业视觉分别承担产品、材料、工艺、应用与内容卡片槽位。
$slotGroups = @(
    @("IMAGE-HERO", "IMAGE-PRODUCT-04"),
    @("IMAGE-PRODUCT-05"),
    @("IMAGE-PRODUCT-06"),
    @("IMAGE-PRODUCT-07"),
    @("IMAGE-PRODUCT-08", "IMAGE-PRODUCT-09"),
    @("IMAGE-MATERIAL-PA66"),
    @("IMAGE-MATERIAL-PC"),
    @("IMAGE-MATERIAL-PP"),
    @("IMAGE-MATERIAL-PEEK"),
    @("IMAGE-MATERIAL-PET"),
    @("IMAGE-TECH-NITRIDING"),
    @("IMAGE-TECH-COATING"),
    @("IMAGE-TECH-PTA"),
    @("IMAGE-TECH-HEAT"),
    @("IMAGE-TECH-INSPECT", "IMAGE-TECH-POLISH"),
    @("IMAGE-APP-AUTO"),
    @("IMAGE-APP-MED"),
    @("IMAGE-APP-PACK"),
    @("IMAGE-APP-PIPE"),
    @("IMAGE-APP-OPTICS", "IMAGE-APP-FLEX"),
    @("IMAGE-FACTORY-WIDE", "IMAGE-EQP-01"),
    @("IMAGE-EQP-02", "IMAGE-CAP-01"),
    @("IMAGE-EQP-03", "IMAGE-CAP-02"),
    @("IMAGE-EQP-04", "IMAGE-CAP-03"),
    @("IMAGE-EQP-05", "IMAGE-EQP-06"),
    @("IMAGE-ARTICLE-01"),
    @("IMAGE-ARTICLE-02"),
    @("IMAGE-ARTICLE-03", "IMAGE-SOLUTION-STABILITY"),
    @("IMAGE-MATERIAL-PLA", "IMAGE-MATERIAL-PPSU", "IMAGE-MATERIAL-TPU"),
    @("IMAGE-ARTICLE-04"),
    @("IMAGE-CASE-01", "IMAGE-SOLUTION-WEAR"),
    @("IMAGE-CASE-02", "IMAGE-SOLUTION-SURFACE"),
    @("IMAGE-CASE-03", "IMAGE-SOLUTION-COLOR"),
    @("IMAGE-ARTICLE-05", "IMAGE-CAP-04"),
    @("IMAGE-CASE-04", "IMAGE-ARTICLE-06"),
    @("IMAGE-PROOF-01"),
    @("IMAGE-PROOF-02"),
    @("IMAGE-PROOF-03"),
    @("IMAGE-EVENT-01", "IMAGE-EVENT-02", "IMAGE-ARTICLE-07"),
    @("IMAGE-ARTICLE-08")
)

for ($index = 1; $index -le $slotGroups.Count; $index++) {
    $assets.Add((New-DemoMediaItem `
        -Alias ("GENERATED-VISUAL-{0:D2}" -f $index) `
        -File ("images/generated-{0:D2}.jpg" -f $index) `
        -Kind image `
        -ContentOrigin generated_demo `
        -Slots $slotGroups[$index - 1] `
        -AltZh "生成式工业演示视觉，不代表真实工厂、客户、证书或设备型号" `
        -AltEn "Generated industrial demo visual; not real factory, customer, certificate or equipment evidence"
    ))
}

$assets.Add((New-DemoMediaItem -Alias "DEMO-VIDEO-01" -File "videos/product-presentation.webm" -Kind video -ContentOrigin generated_demo -Slots @("VIDEO-01") -AltZh "产品展示动效（DEMO演示素材）" -AltEn "Product presentation motion (DEMO material)" -DurationSeconds 10.0))
$assets.Add((New-DemoMediaItem -Alias "DEMO-VIDEO-02" -File "videos/manufacturing-review-flow.webm" -Kind video -ContentOrigin generated_demo -Slots @("VIDEO-02") -AltZh "制造检查流程动效（DEMO演示素材）" -AltEn "Manufacturing review flow motion (DEMO material)" -DurationSeconds 10.0))
$assets.Add((New-DemoMediaItem -Alias "DEMO-DOWNLOAD-01" -File "documents/sample-product-guide.pdf" -Kind document -ContentOrigin generated_demo -Slots @("FILE-DOWNLOAD-01") -AltZh "产品选型指南演示样张" -AltEn "Sample product selection guide"))
$assets.Add((New-DemoMediaItem -Alias "DEMO-DOWNLOAD-02" -File "documents/sample-process-checklist.pdf" -Kind document -ContentOrigin generated_demo -Slots @("FILE-DOWNLOAD-02") -AltZh "工艺检查清单演示样张" -AltEn "Sample process checklist"))
$assets.Add((New-DemoMediaItem -Alias "DEMO-DOWNLOAD-03" -File "documents/sample-rfq-template.pdf" -Kind document -ContentOrigin generated_demo -Slots @("FILE-DOWNLOAD-03") -AltZh "询价资料准备模板演示样张" -AltEn "Sample RFQ preparation template"))

$seenSlots = [System.Collections.Generic.HashSet[string]]::new()
foreach ($asset in $assets) {
    $fullPath = [System.IO.Path]::GetFullPath((Join-Path $resolvedMediaRoot $asset.file))
    if (-not $fullPath.StartsWith($resolvedMediaRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "媒体路径越界：$($asset.file)"
    }
    if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
        throw "媒体文件缺失：$fullPath"
    }
    foreach ($slot in $asset.slots) {
        if (-not $seenSlots.Add($slot)) {
            throw "媒体槽位重复：$slot"
        }
    }
}

$manifest = [ordered]@{
    demo_batch_id = "JH-DEMO-R2-V1"
    assets = $assets
}
$resolvedOutput = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputPath))
$outputParent = Split-Path -Parent $resolvedOutput
New-Item -ItemType Directory -Force -Path $outputParent | Out-Null
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $resolvedOutput -Encoding utf8NoBOM

[pscustomobject]@{
    output = $resolvedOutput
    assets = $assets.Count
    slots = $seenSlots.Count
    sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $resolvedOutput).Hash
} | ConvertTo-Json
