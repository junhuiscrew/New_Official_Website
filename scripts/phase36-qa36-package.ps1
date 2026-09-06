param(
  [string]$RunId = $env:PHASE36_QA_RUN_ID,
  [string]$Worktree = (Get-Location).Path
)

if (-not $RunId) { throw 'RunId is required' }
$evidenceDir = Join-Path $Worktree "artifacts/phase3-6-qa-closeout/$RunId"
$packageRoot = Join-Path $Worktree "artifacts/phase3-6-qa36-closeout/QA36-Evidence-$RunId"
$zipPath = Join-Path $Worktree "artifacts/phase3-6-qa36-closeout/Junhui-Phase3.6-QA36-Evidence-$RunId.zip"
$report = Join-Path $Worktree 'docs/architecture/phase3-6-qa36-closeout-report.md'

if (-not (Test-Path $evidenceDir)) { throw "Missing evidence directory: $evidenceDir" }
if (-not (Test-Path (Join-Path $evidenceDir 'manifest.json'))) { throw 'manifest.json is required' }
if (Test-Path $packageRoot) { Remove-Item -LiteralPath $packageRoot -Recurse -Force }
New-Item -ItemType Directory -Path $packageRoot -Force | Out-Null

# 证据包只复制已列出的脱敏文件，不包含运行目录、日志、环境变量或数据库文件。
$files = @(
  'manifest.json', 'browser-qa.json', 'http-ssr-evidence.json', 'upstream-5xx-evidence.json',
  'home-desktop.png', 'product-mobile.png', 'gallery-open-desktop.png', 'gallery-open-mobile.png',
  'language-product-zh.png', 'language-fallback-home.png', 'rfq-submitted.png'
)
foreach ($file in $files) { Copy-Item -LiteralPath (Join-Path $evidenceDir $file) -Destination (Join-Path $packageRoot $file) -Force }
Copy-Item -LiteralPath $report -Destination (Join-Path $packageRoot 'phase3-6-qa36-closeout-report.md') -Force

$readme = @"
# Junhui Phase 3.6 QA36 Evidence

- Run ID: `$RunId
- Branch: phase-3.6-fix
- Tested commit: d1a979fc66b7c350332f92bf6a44961ba158eb87 plus the documented QA working-tree diff
- Environment: local Docker Compose only; official-origin requests were forwarded to http://localhost:8080 inside Playwright
- Browser: Chromium 152.0.7977.82

The JSON files contain sanitized assertions and SHA-256 manifest entries. UUIDs, cookies, credentials, RFQ tokens, private signed URLs, customer data, database dumps and node/browser profiles are intentionally excluded. The PNG files are the actual desktop/mobile, Gallery-open, language-switch and RFQ screenshots from this run.

Ruff is explicitly marked BLOCKED in the manifest because it was unavailable in the host and test image. Lighthouse is NOT RUN and Safari/WebKit is BLOCKED on this host.
"@
Set-Content -LiteralPath (Join-Path $packageRoot 'README.md') -Value $readme -Encoding utf8

if (Test-Path $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
Compress-Archive -LiteralPath $packageRoot -DestinationPath $zipPath -CompressionLevel Optimal
Get-FileHash -LiteralPath $zipPath -Algorithm SHA256
Get-Item -LiteralPath $zipPath | Select-Object FullName,Length
