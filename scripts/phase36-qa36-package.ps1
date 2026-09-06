param(
  [string]$RunId = $env:PHASE36_QA_RUN_ID,
  [string]$Worktree = (Get-Location).Path
)

if (-not $RunId) { throw 'RunId is required' }
if ($RunId -notmatch '^[a-z0-9][a-z0-9-]{2,39}$') { throw 'RunId contains unsafe characters' }
$evidenceDir = Join-Path $Worktree "artifacts/phase3-6-qa-closeout/$RunId"
$packageBase = Join-Path $Worktree 'artifacts/phase3-6-qa36-closeout'
$packageRoot = Join-Path $packageBase "QA36-Evidence-$RunId"
$zipPath = Join-Path $packageBase "Junhui-Phase3.6-QA36-Evidence-$RunId.zip"
$report = Join-Path $Worktree 'docs/architecture/phase3-6-qa36-closeout-report.md'
$packageTest = Join-Path $Worktree 'scripts/test-phase36-qa36-package.ps1'

if (-not (Test-Path $evidenceDir)) { throw "Missing evidence directory: $evidenceDir" }
if (-not (Test-Path (Join-Path $evidenceDir 'manifest.json'))) { throw 'manifest.json is required' }
if (-not (Test-Path $report -PathType Leaf)) { throw "Missing closeout report: $report" }
New-Item -ItemType Directory -Path $packageBase -Force | Out-Null
if (Test-Path $packageRoot) { Remove-Item -LiteralPath $packageRoot -Recurse -Force }
New-Item -ItemType Directory -Path $packageRoot -Force | Out-Null

# 证据包只复制已列出的脱敏文件，不包含运行目录、日志、环境变量或数据库文件。
$evidenceFiles = @(
  'browser-qa.json', 'http-ssr-evidence.json', 'upstream-5xx-evidence.json',
  'home-desktop.png', 'product-mobile.png', 'gallery-open-desktop.png', 'gallery-open-mobile.png',
  'language-product-zh.png', 'language-fallback-home.png', 'rfq-submitted.png'
)
foreach ($file in @('manifest.json') + $evidenceFiles) {
  $source = Join-Path $evidenceDir $file
  if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing evidence: $file" }
  if ((Get-Item -LiteralPath $source).Length -eq 0) { throw "Empty evidence: $file" }
  Copy-Item -LiteralPath $source -Destination (Join-Path $packageRoot $file) -Force
}
Copy-Item -LiteralPath $report -Destination (Join-Path $packageRoot 'phase3-6-qa36-closeout-report.md') -Force

$readme = @"
# Junhui Phase 3.6 QA36 Evidence

- Run ID: $RunId
- Branch: phase-3.6-fix
- Tested commit: d1a979fc66b7c350332f92bf6a44961ba158eb87 plus the documented QA working-tree diff
- Environment: local Docker Compose only; official-origin requests were forwarded to http://localhost:8080 inside Playwright
- Browser: Chromium 152.0.7977.82

The JSON files contain sanitized assertions and SHA-256 manifest entries. UUIDs, cookies, credentials, RFQ tokens, private signed URLs, customer data, database dumps and node/browser profiles are intentionally excluded. The PNG files are the actual desktop/mobile, Gallery-open, language-switch and RFQ screenshots from this run.

Ruff was executed from the project API dev environment with `python -m ruff check --no-cache apps/api` and passed. Lighthouse is NOT RUN and Safari/WebKit is BLOCKED on this host.
"@
Set-Content -LiteralPath (Join-Path $packageRoot 'README.md') -Value $readme -Encoding utf8

# 校验 README、报告、三份 JSON 和七张截图，并为全部有效载荷生成校验和。
$requiredFiles = @(
  'README.md', 'phase3-6-qa36-closeout-report.md',
  'browser-qa.json', 'http-ssr-evidence.json', 'upstream-5xx-evidence.json',
  'home-desktop.png', 'product-mobile.png', 'gallery-open-desktop.png', 'gallery-open-mobile.png',
  'language-product-zh.png', 'language-fallback-home.png', 'rfq-submitted.png'
)
foreach ($file in $requiredFiles) {
  $path = Join-Path $packageRoot $file
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing packaged file: $file" }
  if ((Get-Item -LiteralPath $path).Length -eq 0) { throw "Empty packaged file: $file" }
}
foreach ($jsonFile in @('browser-qa.json', 'http-ssr-evidence.json', 'upstream-5xx-evidence.json')) {
  Get-Content -LiteralPath (Join-Path $packageRoot $jsonFile) -Raw | ConvertFrom-Json | Out-Null
}
$packagedReadme = Get-Content -LiteralPath (Join-Path $packageRoot 'README.md') -Raw
if ($packagedReadme -notmatch "(?m)^- Run ID: $([regex]::Escape($RunId))$") { throw 'README Run ID was not expanded' }
if ($packagedReadme.Contains('$RunId')) { throw 'README contains a literal RunId placeholder' }

$checksumFiles = @('manifest.json') + $requiredFiles
$checksumLines = foreach ($file in ($checksumFiles | Sort-Object)) {
  $hash = (Get-FileHash -LiteralPath (Join-Path $packageRoot $file) -Algorithm SHA256).Hash
  "$hash  $file"
}
Set-Content -LiteralPath (Join-Path $packageRoot 'SHA256SUMS.txt') -Value $checksumLines -Encoding ascii

if (Test-Path $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
Compress-Archive -LiteralPath $packageRoot -DestinationPath $zipPath -CompressionLevel Optimal
$integrity = & $packageTest -RunId $RunId -Worktree $Worktree | ConvertFrom-Json
$zipHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash
$zip = Get-Item -LiteralPath $zipPath
[pscustomobject]@{
  run_id = $RunId
  path = $zip.FullName
  bytes = $zip.Length
  sha256 = $zipHash
  integrity = $integrity.status
  checksum_entries = $integrity.checksum_entries
} | ConvertTo-Json
