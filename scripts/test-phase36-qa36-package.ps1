param(
  [Parameter(Mandatory = $true)]
  [string]$RunId,
  [string]$Worktree = (Get-Location).Path
)

$zipPath = Join-Path $Worktree "artifacts/phase3-6-qa36-closeout/Junhui-Phase3.6-QA36-Evidence-$RunId.zip"
if (-not (Test-Path -LiteralPath $zipPath -PathType Leaf)) { throw "Missing ZIP: $zipPath" }

$verificationRoot = Join-Path ([System.IO.Path]::GetTempPath()) "junhui-qa36-package-$([guid]::NewGuid().ToString('N'))"
$expectedRoot = "QA36-Evidence-$RunId"
$requiredFiles = @(
  'README.md',
  'phase3-6-qa36-closeout-report.md',
  'browser-qa.json',
  'http-ssr-evidence.json',
  'upstream-5xx-evidence.json',
  'home-desktop.png',
  'product-mobile.png',
  'gallery-open-desktop.png',
  'gallery-open-mobile.png',
  'language-product-zh.png',
  'language-fallback-home.png',
  'rfq-submitted.png'
)
$checksumFiles = @('manifest.json') + $requiredFiles

try {
  Expand-Archive -LiteralPath $zipPath -DestinationPath $verificationRoot
  $contentRoot = Join-Path $verificationRoot $expectedRoot
  if (-not (Test-Path -LiteralPath $contentRoot -PathType Container)) { throw "Missing package root: $expectedRoot" }

  foreach ($file in $requiredFiles) {
    $path = Join-Path $contentRoot $file
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing required evidence: $file" }
    if ((Get-Item -LiteralPath $path).Length -eq 0) { throw "Empty required evidence: $file" }
  }

  $readme = Get-Content -LiteralPath (Join-Path $contentRoot 'README.md') -Raw
  if ($readme -notmatch "(?m)^- Run ID: $([regex]::Escape($RunId))$") { throw 'README does not contain the expanded Run ID' }
  if ($readme.Contains('$RunId')) { throw 'README still contains the literal $RunId placeholder' }

  foreach ($jsonFile in @('browser-qa.json', 'http-ssr-evidence.json', 'upstream-5xx-evidence.json')) {
    Get-Content -LiteralPath (Join-Path $contentRoot $jsonFile) -Raw | ConvertFrom-Json | Out-Null
  }

  $sumsPath = Join-Path $contentRoot 'SHA256SUMS.txt'
  if (-not (Test-Path -LiteralPath $sumsPath -PathType Leaf)) { throw 'Missing SHA256SUMS.txt' }
  $sumLines = @(Get-Content -LiteralPath $sumsPath | Where-Object { $_.Trim() })
  if ($sumLines.Count -ne $checksumFiles.Count) { throw "SHA256SUMS.txt expected $($checksumFiles.Count) entries, found $($sumLines.Count)" }
  foreach ($file in $checksumFiles) {
    $line = $sumLines | Where-Object { $_ -match "  $([regex]::Escape($file))$" }
    if (@($line).Count -ne 1) { throw "Missing or duplicate checksum entry: $file" }
    $expectedHash = ($line -split '\s{2}', 2)[0]
    $actualHash = (Get-FileHash -LiteralPath (Join-Path $contentRoot $file) -Algorithm SHA256).Hash
    if ($expectedHash -ne $actualHash) { throw "Checksum mismatch: $file" }
  }

  $text = ($requiredFiles | Where-Object { $_ -match '\.(md|json|txt)$' } | ForEach-Object {
    Get-Content -LiteralPath (Join-Path $contentRoot $_) -Raw
  }) -join "`n"
  foreach ($pattern in @('Authorization:\s*Bearer\s+\S+', 'X-Amz-Signature=', '"(?:access|refresh)_token"\s*:', 'https?://minio:9000')) {
    if ($text -match $pattern) { throw "Sensitive pattern found: $pattern" }
  }

  [pscustomobject]@{
    run_id = $RunId
    zip = $zipPath
    required_files = $requiredFiles.Count
    checksum_entries = $sumLines.Count
    status = 'PASS'
  } | ConvertTo-Json
}
finally {
  # 仅清理本次随机生成、位于系统临时目录中的验证目录。
  if (Test-Path -LiteralPath $verificationRoot) { Remove-Item -LiteralPath $verificationRoot -Recurse -Force }
}
