# Phase 3.6 QA36 Closeout Report

## 1. Scope and baseline

- Project: `junhuiscrew/New_Official_Website`
- Branch: `phase-3.6-fix`
- Base / tested commit: `d1a979fc66b7c350332f92bf6a44961ba158eb87`
- Working tree: dirty during the run by the QA-only fixture/evidence changes listed below; no force reset, push, merge or deployment.
- Run ID: `closeout-20260906-a`
- Browser: Chromium `152.0.7977.82` on the local Windows host
- Local gateway: `http://localhost:8080`

R36-01–R36-05 were not reopened. This closeout only addresses QA36-G, QA36-L and QA36-E and does not enter Phase 3.7.

## 2. QA-only isolation and data

The fixture was created and removed with the existing explicit opt-in CLI using `PHASE36_QA_CONFIRM=LOCAL_QA_ONLY`, `PHASE36_QA_ISOLATION=LOCAL_COMPOSE_ONLY`, database `junhui`, run ID `closeout-20260906-a`, and a dedicated Redis namespace. It created real local MinIO public objects only:

- `qa/phase36/closeout-20260906-a/product.png` — QA-only 1200×800 PNG, visible alt/caption and normal dimensions.
- `qa/phase36/closeout-20260906-a/qa-datasheet.pdf`.

No production request was made. Playwright forwarded only requests whose origin was exactly `https://junhuiscrewbarrel.com` to the local gateway; other external origins were aborted. Relative language links remained local. RFQ/media UUIDs are redacted in evidence.

## 3. QA36-G — Gallery forced interaction

`scripts/phase36-browser-qa.js` now uses `data-testid="gallery-open"`. It asserts count, visibility and enabled state before clicking and never uses `if(count)`, `force`, or component-state manipulation.

| Viewport | Result | Evidence |
|---|---|---|
| Desktop 1440px | PASS — dialog opened; source and dialog image decoded at 1200×800; focus entered dialog; Tab and reverse Tab stayed inside; Escape closed and returned focus; visible close button closed and returned focus | `gallery-open-desktop.png` |
| Mobile 320px | PASS — same assertions and real click path | `gallery-open-mobile.png` |

The screenshots show the opened dialog and QA image rather than a 1×1 placeholder. The raw assertion object is in `browser-qa.json` under `gallery.desktop` and `gallery.mobile`.

## 4. QA36-L — Real language-menu clicks

The test opens the visible language menu and clicks the single visible option, then waits for navigation; it does not replace the click with `page.goto()`.

- English product → Chinese product: PASS; final `html lang=zh-CN`, Chinese heading, self-canonical and English alternate verified.
- Chinese product → English product: PASS; final `html lang=en`, English heading and self-canonical verified.
- English-only knowledge article → Simplified Chinese home fallback: PASS; final URL was local gateway `/zh-cn/`, canonical remained the official Chinese home URL, and hreflang was present.
- Mobile navigation language switch: PASS; actual mobile menu language click reached Chinese home and verified language/canonical/hreflang.

Evidence: `language-product-zh.png`, `language-fallback-home.png`, and the `chineseProduct`, `englishProduct`, `missingTranslationFallback`, and `mobileLanguage` objects in `browser-qa.json`.

## 5. QA36-E — Journeys and structural checks

| Journey/check | Result |
|---|---|
| Home → Product → RFQ multi-item → real local attachment upload → submitted response | PASS; HTTP 201, second item visible, attachment uploaded, token/reference redacted |
| Search → Knowledge → related Product | PASS; visible source and relation link verified |
| Non-Product Case → RFQ source persistence | PASS; server-validated source visible and RFQ created |
| Mobile menu and mobile RFQ source | PASS |
| Pagination/filter errors and recovery | PASS; valid page 200/self-canonical, invalid filter/zero-result/out-of-range 404, recovery list 24 items |
| Home/Product 320–1920 matrix and full document structure | PASS; one `main`, one `#main-content`, one H1, no duplicate IDs, no horizontal overflow at all tested widths |
| Home/Product HTTP SSR | PASS; description, self-canonical, hreflang, JSON-LD and visible structured content |
| Isolated upstream 5xx | PASS; local 500, friendly recovery, no internal detail, API restored 200 |

The browser run preserved three expected out-of-range 404 console messages in `consoleErrors`; `unexpectedConsoleErrors` and `pageErrors` were empty. They were not blanket-filtered.

## 6. Files changed for this closeout

- `apps/api/app/phase36_qa.py` — QA-only 1200×800 PNG fixture metadata and deterministic image bytes.
- `scripts/phase36-browser-qa.js` — exact-origin forwarding, real Gallery/language clicks, focus assertions, redaction, screenshots and evidence output.
- `scripts/phase36-http-evidence.ps1` — run-scoped output and `run_id`.
- `scripts/phase36-upstream-5xx-evidence.ps1` — run-scoped output and `run_id`.
- `scripts/phase36-qa36-manifest.js` — SHA-256 manifest generator.
- `.gitignore` — ignored local closeout evidence directory.
- `docs/architecture/phase3-6-remediation-report.md` — historical evidence correction appended without deleting prior history.

## 7. Commands and actual results

| Command | Result |
|---|---|
| QA fixture cleanup/setup | PASS, local-only, exit 0 |
| `node scripts/phase36-browser-qa.js` | PASS, exit 0 |
| `pwsh -File scripts/phase36-http-evidence.ps1 ...` | PASS, exit 0 |
| `pwsh -File scripts/phase36-upstream-5xx-evidence.ps1 ...` | PASS, exit 0; API restored |
| `docker compose --profile test run --rm -v <worktree>/apps/api:/app api-test` | PASS, `241 passed`, 1 dependency warning, 84.04s |
| `pnpm --filter @junhui/website test` | PASS, 11 files / 118 tests |
| `pnpm --filter @junhui/admin test` | PASS, 6 files / 23 tests |
| `pnpm --filter @junhui/website typecheck` | PASS, exit 0 |
| `pnpm --filter @junhui/admin typecheck` | PASS, exit 0 |
| `pnpm format:check` | PASS |
| `pnpm --filter @junhui/website build` | PASS, Nuxt production build complete |
| `docker compose ps` + live/ready | PASS, services healthy; API ready 200 |
| Ruff | **BLOCKED** — neither host nor API test image contains `ruff`; not reported as PASS |
| Lighthouse | **NOT RUN** |
| Safari/WebKit | **BLOCKED** — unavailable on Windows host |

The full backend test command performs the test database migration and seed before pytest; its 241 tests cover migration/seed idempotency and the existing PostgreSQL/Redis/MinIO integration suite.

## 8. Evidence and delivery

Ignored local evidence directory:

`artifacts/phase3-6-qa-closeout/closeout-20260906-a/`

It contains `browser-qa.json`, `http-ssr-evidence.json`, `upstream-5xx-evidence.json`, `manifest.json`, the seven required screenshots (desktop/mobile/product language/fallback/RFQ), and no credentials or private URLs. `manifest.json` records command exit codes, assertion status, browser, run ID, SHA-256 and sanitization rules.

The ZIP is generated after this report is committed:

`artifacts/phase3-6-qa36-closeout/Junhui-Phase3.6-QA36-Evidence-closeout-20260906-a.zip`

The final local ZIP size and SHA-256 are printed by `scripts/phase36-qa36-package.ps1`; the package manifest contains the hashes of every included evidence file.

## 9. SEO/GEO and security consistency

No second canonical, hreflang, publication, route or schema system was introduced. Exact-origin forwarding was test-only and local. Existing RFQ Origin, rate-limit, attachment, scan and signed-download controls were not relaxed. The real image is public QA media; private RFQ data and signed URLs are excluded.

## 10. Conclusion / next step

QA36-G, QA36-L and QA36-E are evidenced for this local run. This is not a Phase 3.6 FINAL PASS announcement. The branch remains unpushed and undeployed; wait for the user’s final revalidation. Lighthouse and real Safari/WebKit remain outstanding limitations.
