param(
    [Parameter(Mandatory = $true)]
    [string]$SheetOne,

    [Parameter(Mandatory = $true)]
    [string]$SheetTwo,

    [string]$OutputDirectory = "data/demo-r2/media/images"
)

$ErrorActionPreference = "Stop"

<#
.SYNOPSIS
    将两张经过批准的 DEMO 概念联系表拆分为可独立入库的演示图片。

.DESCRIPTION
    输入：SheetOne、SheetTwo 为 5×4 联系表路径，OutputDirectory 为输出目录。
    输出：40 张 1200×900 JPEG 图片。仅做机械裁切，不改写生成素材含义。
#>

Add-Type -AssemblyName System.Drawing

function Export-DemoContactSheetCells {
    <#
    将一张 5×4 联系表按网格裁切并统一成 4:3 媒体卡片。

    输入：
        SourcePath: string，联系表完整路径。
        StartIndex: int，输出文件起始序号。
        TargetDirectory: string，输出目录。
    输出：
        string[]，生成文件的完整路径。
    #>
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourcePath,

        [Parameter(Mandatory = $true)]
        [int]$StartIndex,

        [Parameter(Mandatory = $true)]
        [string]$TargetDirectory
    )

    $source = [System.Drawing.Bitmap]::FromFile((Resolve-Path -LiteralPath $SourcePath))
    $generated = [System.Collections.Generic.List[string]]::new()
    try {
        for ($row = 0; $row -lt 4; $row++) {
            for ($column = 0; $column -lt 5; $column++) {
                # 使用浮点网格边界避免 975px 高度的余数累积，并裁掉白色分隔线。
                $left = [Math]::Floor($column * $source.Width / 5) + 6
                $right = [Math]::Floor(($column + 1) * $source.Width / 5) - 6
                $top = [Math]::Floor($row * $source.Height / 4) + 6
                $bottom = [Math]::Floor(($row + 1) * $source.Height / 4) - 6
                $sourceRectangle = [System.Drawing.Rectangle]::new(
                    $left,
                    $top,
                    $right - $left,
                    $bottom - $top
                )
                $target = [System.Drawing.Bitmap]::new(1200, 900)
                try {
                    $graphics = [System.Drawing.Graphics]::FromImage($target)
                    try {
                        $graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
                        $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
                        $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
                        $graphics.DrawImage(
                            $source,
                            [System.Drawing.Rectangle]::new(0, 0, 1200, 900),
                            $sourceRectangle,
                            [System.Drawing.GraphicsUnit]::Pixel
                        )
                    }
                    finally {
                        $graphics.Dispose()
                    }

                    $index = $StartIndex + ($row * 5) + $column
                    $targetPath = Join-Path $TargetDirectory ("generated-{0:D2}.jpg" -f $index)
                    $jpegCodec = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() |
                        Where-Object MimeType -eq "image/jpeg" |
                        Select-Object -First 1
                    $encoderParameters = [System.Drawing.Imaging.EncoderParameters]::new(1)
                    try {
                        $encoderParameters.Param[0] = [System.Drawing.Imaging.EncoderParameter]::new(
                            [System.Drawing.Imaging.Encoder]::Quality,
                            [long]88
                        )
                        $target.Save($targetPath, $jpegCodec, $encoderParameters)
                    }
                    finally {
                        $encoderParameters.Dispose()
                    }
                    $generated.Add((Resolve-Path -LiteralPath $targetPath).Path)
                }
                finally {
                    $target.Dispose()
                }
            }
        }
    }
    finally {
        $source.Dispose()
    }
    return $generated.ToArray()
}

$resolvedOutput = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputDirectory))
New-Item -ItemType Directory -Force -Path $resolvedOutput | Out-Null

$files = @()
$files += Export-DemoContactSheetCells -SourcePath $SheetOne -StartIndex 1 -TargetDirectory $resolvedOutput
$files += Export-DemoContactSheetCells -SourcePath $SheetTwo -StartIndex 21 -TargetDirectory $resolvedOutput

[pscustomobject]@{
    output_directory = $resolvedOutput
    generated_count = $files.Count
    files = $files
} | ConvertTo-Json -Depth 3
