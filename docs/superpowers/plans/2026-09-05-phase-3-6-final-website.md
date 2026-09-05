# Phase 3.6 Final Website Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the final bilingual, SSR-first Junhui public website by composing existing published content, trust, media, RFQ, SEO, and GEO capabilities into an accessible and performant global B2B experience.

**Architecture:** Add focused read-only Public API query modules for navigation, homepage, listings, search, media, and clean product specifications. Build a Nuxt default layout and reusable public components that render these DTOs server-side while preserving backend-owned publication, canonical, hreflang, robots, Schema, privacy, and RFQ security rules.

**Tech Stack:** FastAPI 0.116.1, SQLAlchemy 2.0.43, PostgreSQL 17, Nuxt 4.5.2, Vue 3.5.42, TypeScript 5.9.2, Vitest 3.2.4, native CSS, Docker Compose.

---

## File map

Backend files:

- Create `apps/api/app/modules/discovery/public_schemas.py`: typed public display DTOs with no internal identifiers.
- Create `apps/api/app/modules/discovery/public_specs.py`: converts five specification value types into clean display values.
- Create `apps/api/app/modules/discovery/public_collections.py`: published listing, navigation, homepage, and search queries.
- Modify `apps/api/app/modules/discovery/public_delivery.py`: reuse shared public gates and enrich detail DTOs with display media/specs/relations.
- Modify `apps/api/app/api/v1/public.py`: expose read-only home, navigation, listing, and search endpoints.
- Create `apps/api/alembic/versions/20260905_0010_phase36_search.py`: enable pg_trgm and add public-search expression indexes without changing content ownership.
- Create `apps/api/tests/test_phase36_public_dtos.py`: spec/media/privacy DTO tests.
- Create `apps/api/tests/test_phase36_public_collections.py`: navigation, homepage, listing, search, and indexability tests.

Website foundation files:

- Create `apps/website/app/types/public.ts`: shared DTO interfaces.
- Create `apps/website/app/i18n/ui.ts`: zh-CN/en UI labels only.
- Create `apps/website/app/composables/useLocalePath.ts`: locale normalization, alternate routing, and RFQ source URLs.
- Create `apps/website/app/composables/useTelemetry.ts`: no-op telemetry hooks until analytics is configured.
- Create `apps/website/app/layouts/default.vue`: global SSR shell.
- Modify `apps/website/app/app.vue`: use Nuxt layout and global accessibility behavior.
- Replace `apps/website/app/assets/css/main.css`: tokens, reset, typography, layout, accessibility, responsive rules.
- Create `apps/website/public/brand/junhui-mark.png`: user-provided static brand mark.
- Create `apps/website/public/brand/junhui-wordmark.png`: transparent horizontal brand reference after background cleanup.

Website component files:

- Create `SiteHeader.vue`, `MegaMenu.vue`, `MobileNav.vue`, `LanguageSwitcher.vue`, `SearchButton.vue`, `SiteFooter.vue`.
- Create `PageHero.vue`, `SectionHeader.vue`, `ProductCard.vue`, `ArticleCard.vue`, `CaseCard.vue`, `TrustMetric.vue`.
- Create `SpecTable.vue`, `RelationLinks.vue`, `FAQAccordion.vue`, `GeoAnswer.vue`.
- Create `PublicImage.vue`, `PublicVideo.vue`, `MediaGallery.vue`.
- Create `RfqCta.vue`, `EmptyState.vue`, `PaginationNav.vue`, `FilterBar.vue`.
- Refactor existing `PublicBreadcrumb.vue`, `PublicFaqList.vue`, `PublicGeoContent.vue`, and `PublicRelationLinks.vue` into compatibility wrappers where existing tests require their names.

Website page files:

- Replace `apps/website/app/pages/en/index.vue` and `apps/website/app/pages/zh-cn/index.vue` with a shared homepage component.
- Create `apps/website/app/pages/[lang]/products/index.vue` and finish product category/detail pages.
- Finish Material, Technology, Application, Solution, Knowledge, Case, Expert, About, Capability, Trust, Exhibition, Downloads, and RFQ pages.
- Create `apps/website/app/pages/[lang]/knowledge/index.vue`, `case-studies/index.vue`, `materials/index.vue`, `technologies/index.vue`, `applications/index.vue`, `solutions/index.vue`, `experts/index.vue`, and `search/index.vue`.
- Create `apps/website/app/error.vue` for public 404/500 recovery.

Website test files:

- Create `apps/website/tests/phase36-foundation.test.ts`.
- Create `apps/website/tests/phase36-navigation.test.ts`.
- Create `apps/website/tests/phase36-homepage.test.ts`.
- Create `apps/website/tests/phase36-products.test.ts`.
- Create `apps/website/tests/phase36-content.test.ts`.
- Create `apps/website/tests/phase36-interactions.test.ts`.

Documentation files:

- Create `docs/architecture/phase3-6-completion-report.md` after all verification commands have fresh results.

### Task 1: Clean Public DTO and specification contract

**Files:**
- Create: `apps/api/app/modules/discovery/public_schemas.py`
- Create: `apps/api/app/modules/discovery/public_specs.py`
- Modify: `apps/api/app/modules/discovery/public_delivery.py`
- Test: `apps/api/tests/test_phase36_public_dtos.py`

- [ ] **Step 1: Write failing DTO tests**

Add tests that construct text, number, range, boolean, and enum `ProductSpecValue` rows and assert this exact public shape:

```python
assert dto == {
    "name": "Outer Diameter",
    "value": "65",
    "unit": "mm",
    "group": "Dimensions",
    "type": "number",
}
assert not {"id", "definition_id", "product_id", "created_at"}.intersection(dto)
```

Add assertions that public media contains only `src`, `type`, `mime_type`, `width`, `height`, `alt`, `caption`, and `loading`, and that no private bucket/storage key can enter the DTO.

- [ ] **Step 2: Run tests and verify RED**

Run: `cd apps/api; .venv/Scripts/python.exe -m pytest tests/test_phase36_public_dtos.py -q`

Expected: FAIL because `public_schemas` and `public_specs` do not exist.

- [ ] **Step 3: Add typed public schemas**

Define focused Pydantic models:

```python
class PublicMediaDto(BaseModel):
    src: str
    type: Literal["image", "video", "document"]
    mime_type: str
    width: int | None = None
    height: int | None = None
    alt: str
    caption: str | None = None
    loading: Literal["eager", "lazy"] = "lazy"


class PublicSpecDto(BaseModel):
    name: str
    value: str
    unit: str | None = None
    group: str
    type: Literal["text", "number", "range", "boolean", "enum"]
```

Add Chinese docstrings describing inputs and outputs for every conversion function.

- [ ] **Step 4: Implement five specification serializers**

Use `Decimal`-safe string formatting, localized boolean labels, `min–max` range rendering, enum values, translated definition/group names, and public/default units. Reject impossible storage combinations rather than returning raw JSON.

- [ ] **Step 5: Enrich Product detail without weakening public gates**

Update `get_public_product()` to call the serializer and return `media`, `primary_media`, and `specifications: list[PublicSpecDto]`. Preserve `_public_route()`, `_published_alternates()`, canonical Link DTOs, FAQ, GEO, and backend Schema output.

- [ ] **Step 6: Run DTO and existing delivery tests**

Run: `cd apps/api; .venv/Scripts/python.exe -m pytest tests/test_phase36_public_dtos.py tests/test_phase34_remediation.py tests/test_phase35_remediation.py -q`

Expected: all selected tests PASS.

- [ ] **Step 7: Commit**

```powershell
git add apps/api/app/modules/discovery/public_schemas.py apps/api/app/modules/discovery/public_specs.py apps/api/app/modules/discovery/public_delivery.py apps/api/tests/test_phase36_public_dtos.py
git commit -m "feat: add clean public product DTOs"
```

### Task 2: Published navigation and homepage aggregation

**Files:**
- Create: `apps/api/app/modules/discovery/public_collections.py`
- Modify: `apps/api/app/api/v1/public.py`
- Test: `apps/api/tests/test_phase36_public_collections.py`

- [ ] **Step 1: Write failing navigation/home tests**

Create fixtures containing published, draft, disabled, non-self-canonical, and `robots_index=false` entities. Assert only the fully indexable rows enter navigation/home:

```python
assert [item["slug"] for item in payload["featured_products"]] == ["published-screw"]
assert "draft-screw" not in str(payload)
assert "private-client-name" not in str(payload)
```

Assert empty content families return empty arrays and do not invent product names, counts, certifications, or company facts.

- [ ] **Step 2: Run tests and verify RED**

Run: `cd apps/api; .venv/Scripts/python.exe -m pytest tests/test_phase36_public_collections.py -q`

Expected: FAIL with missing collection functions/routes.

- [ ] **Step 3: Implement shared published collection query**

Create `_published_rows(session, owner_type, locale, limit, featured_only)` that joins `ContentRoute`, `ContentPublication`, `TranslationStatus`, `Locale`, and optional `SeoDocument`. Apply the same enabled/published/canonical/active/indexable/robots/self-canonical rules as `_public_route()`.

- [ ] **Step 4: Implement navigation DTO**

Return:

```python
{
    "locale": locale.slug,
    "primary": [...],
    "products": {"categories": [...], "featured": [...]},
    "solutions": {"featured": [...], "problems": [...]},
    "materials": [...],
    "applications": [...],
    "company": {"name": ..., "phone": ..., "email": ..., "address": ...},
}
```

Static UI route labels may be localized server-side or by Nuxt, but every content link must come from canonical Link DTOs.

- [ ] **Step 5: Implement homepage DTO**

Return published `company`, `hero_media`, `product_categories`, `featured_products`, `materials`, `solutions`, `capabilities`, `applications`, `cases`, `knowledge`, and `trust_summary`. Each section is an empty list or `null` when data is absent.

- [ ] **Step 6: Add endpoints and cache headers**

Add `GET /public/navigation/{locale_slug}` and `/public/home/{locale_slug}`. Use a short public cache policy such as `public, max-age=60, stale-while-revalidate=300`; do not apply it to RFQ/auth/private routes.

- [ ] **Step 7: Run tests and commit**

Run: `cd apps/api; .venv/Scripts/python.exe -m pytest tests/test_phase36_public_collections.py tests/test_content_routes.py tests/test_phase34_remediation.py -q`

Expected: PASS.

```powershell
git add apps/api/app/modules/discovery/public_collections.py apps/api/app/api/v1/public.py apps/api/tests/test_phase36_public_collections.py
git commit -m "feat: add public navigation and homepage feeds"
```

### Task 3: Public listings and PostgreSQL search

**Files:**
- Modify: `apps/api/app/modules/discovery/public_collections.py`
- Modify: `apps/api/app/api/v1/public.py`
- Create: `apps/api/alembic/versions/20260905_0010_phase36_search.py`
- Test: `apps/api/tests/test_phase36_public_collections.py`
- Test: `apps/api/tests/test_postgresql_integration.py`

- [ ] **Step 1: Add failing listing/search tests**

Test category/material/application filters, page bounds, maximum page size, published-only results, locale isolation, search type allowlist, and zero private/unpublished results. Add a PostgreSQL-only assertion that relevant title/name matches rank ahead of summary/body matches.

- [ ] **Step 2: Run tests and verify RED**

Run: `cd apps/api; .venv/Scripts/python.exe -m pytest tests/test_phase36_public_collections.py -q`

Expected: FAIL because list and search routes do not exist.

- [ ] **Step 3: Implement list contracts**

Use a common envelope:

```python
{
    "items": list[PublicCardDto],
    "page": page,
    "page_size": page_size,
    "total": total,
    "pages": max(1, ceil(total / page_size)),
    "filters": {"category": category, "material": material, "application": application},
}
```

Whitelist filter fields and cap `page_size` at 48. Add list endpoints for products, product categories, materials, technologies, applications, solutions, knowledge, cases, and experts.

- [ ] **Step 4: Add the PostgreSQL search migration**

Create revision `20260905_0010` with `down_revision = "20260904_0009"`. In `upgrade()`, execute `CREATE EXTENSION IF NOT EXISTS pg_trgm` and add named GIN trigram indexes for the translated Product/Material/Application/Solution names and Knowledge/Case titles used by the search union. In `downgrade()`, drop only those named indexes; leave the shared extension installed so downgrade cannot break another database consumer.

- [ ] **Step 5: Implement search**

Use PostgreSQL `to_tsvector`/`websearch_to_tsquery` with pg_trgm fallback where available. For SQLite unit tests use deterministic `ilike` behavior. Search only the six approved content families and return canonical card DTOs grouped by type.

- [ ] **Step 6: Run unit and PostgreSQL tests**

Run local unit suite, then: `docker compose --profile test run --rm --build api-test`

Expected: all backend tests PASS, including the new real PostgreSQL search test.

- [ ] **Step 7: Commit**

```powershell
git add apps/api/app/modules/discovery/public_collections.py apps/api/app/api/v1/public.py apps/api/alembic/versions/20260905_0010_phase36_search.py apps/api/tests/test_phase36_public_collections.py apps/api/tests/test_postgresql_integration.py
git commit -m "feat: add public listings and search"
```

### Task 4: Website types, locale labels, tokens, and brand assets

**Files:**
- Create: `apps/website/app/types/public.ts`
- Create: `apps/website/app/i18n/ui.ts`
- Create: `apps/website/app/composables/useLocalePath.ts`
- Create: `apps/website/app/composables/useTelemetry.ts`
- Replace: `apps/website/app/assets/css/main.css`
- Create: `apps/website/public/brand/junhui-mark.png`
- Create: `apps/website/public/brand/junhui-wordmark.png`
- Test: `apps/website/tests/phase36-foundation.test.ts`

- [ ] **Step 1: Write failing foundation tests**

Assert both locales define every navigation, CTA, form, empty-state, and error label. Assert tokens include primary/navy/green/neutral/status colors, typography, 4/8 spacing, restrained radius, content width, focus ring, reduced motion, and breakpoints. Assert brand images exist and have no checkerboard background reference in CSS.

- [ ] **Step 2: Run test and verify RED**

Run: `pnpm --filter @junhui/website test -- phase36-foundation.test.ts`

Expected: FAIL because files and tokens are missing.

- [ ] **Step 3: Create shared DTO types and locale helpers**

Define `LocaleSlug = 'zh-cn' | 'en'`, `PublicLinkDto`, `PublicMediaDto`, `PublicSpecDto`, `PublicCardDto`, `NavigationDto`, `HomeDto`, `SeoDto`, and `GeoDto`. Implement `normalizeLocale()`, `localeHome()`, `alternateTarget()`, and `rfqUrl(source)` without internal IDs.

- [ ] **Step 4: Add UI dictionaries**

Export a complete `ui` record for `zh-cn` and `en`. Add a test that recursively compares dictionary keys so one language cannot silently miss labels.

- [ ] **Step 5: Install brand assets**

Copy the supplied circular logo into `junhui-mark.png`. Produce the transparent horizontal wordmark from the supplied reference without changing the logo geometry or brand colors. Verify alpha/background visually and with image metadata.

- [ ] **Step 6: Replace placeholder CSS with final tokens**

Define CSS custom properties for colors, type, spacing, container, focus, borders, shadows, transitions, and responsive breakpoints. Add semantic base styles and `prefers-reduced-motion`; avoid global selectors that break Admin.

- [ ] **Step 7: Run tests, typecheck, and commit**

Run: `pnpm --filter @junhui/website test -- phase36-foundation.test.ts`

Run: `pnpm --filter @junhui/website typecheck`

Expected: PASS.

```powershell
git add apps/website/app/types apps/website/app/i18n apps/website/app/composables/useLocalePath.ts apps/website/app/composables/useTelemetry.ts apps/website/app/assets/css/main.css apps/website/public/brand apps/website/tests/phase36-foundation.test.ts
git commit -m "feat: establish final public design system"
```

### Task 5: Global SSR layout, header, mega menus, mobile nav, and footer

**Files:**
- Create: `apps/website/app/layouts/default.vue`
- Modify: `apps/website/app/app.vue`
- Create: `apps/website/app/components/SiteHeader.vue`
- Create: `apps/website/app/components/MegaMenu.vue`
- Create: `apps/website/app/components/MobileNav.vue`
- Create: `apps/website/app/components/LanguageSwitcher.vue`
- Create: `apps/website/app/components/SearchButton.vue`
- Create: `apps/website/app/components/SiteFooter.vue`
- Test: `apps/website/tests/phase36-navigation.test.ts`

- [ ] **Step 1: Write failing navigation tests**

Mount components with published DTO fixtures and assert Desktop links, Product/Solution menus, language fallback, RFQ CTA, `aria-expanded`, Escape handling, body scroll locking, focus restoration, and omission of empty/unpublished groups.

- [ ] **Step 2: Run test and verify RED**

Run: `pnpm --filter @junhui/website test -- phase36-navigation.test.ts`

Expected: FAIL because layout and components are missing.

- [ ] **Step 3: Implement SSR layout fetch**

Fetch `/public/navigation/${lang}` with a stable key. Do not fail the whole page when optional navigation groups are empty; show the static route labels and suppress only missing dynamic children.

- [ ] **Step 4: Implement accessible Desktop and Mobile navigation**

Use buttons for menu toggles, anchors/NuxtLink for navigation, roving focus only where useful, outside-click close, Escape close, and focus return. Lock body scroll only while Mobile Nav is open and remove the lock on unmount.

- [ ] **Step 5: Implement conditional Footer**

Render company contact fields only when returned by the API. Add Privacy, optional Terms, Sitemap, locale links, and current-year copyright without inventing company claims.

- [ ] **Step 6: Run tests and commit**

Run: `pnpm --filter @junhui/website test -- phase36-navigation.test.ts`

Expected: PASS.

```powershell
git add apps/website/app/app.vue apps/website/app/layouts/default.vue apps/website/app/components/SiteHeader.vue apps/website/app/components/MegaMenu.vue apps/website/app/components/MobileNav.vue apps/website/app/components/LanguageSwitcher.vue apps/website/app/components/SearchButton.vue apps/website/app/components/SiteFooter.vue apps/website/tests/phase36-navigation.test.ts
git commit -m "feat: build global website navigation"
```

### Task 6: Final SSR homepage

**Files:**
- Create: `apps/website/app/components/HomePage.vue`
- Create: `apps/website/app/components/PageHero.vue`
- Create: `apps/website/app/components/SectionHeader.vue`
- Create: `apps/website/app/components/ProductCard.vue`
- Create: `apps/website/app/components/ArticleCard.vue`
- Create: `apps/website/app/components/CaseCard.vue`
- Create: `apps/website/app/components/TrustMetric.vue`
- Create: `apps/website/app/components/RfqCta.vue`
- Modify: `apps/website/app/pages/en/index.vue`
- Modify: `apps/website/app/pages/zh-cn/index.vue`
- Test: `apps/website/tests/phase36-homepage.test.ts`

- [ ] **Step 1: Write failing homepage tests**

Assert one H1, two hero CTAs, Published API content, conditional omission of empty sections, no carousel, no hardcoded years/diameters/ISO/equipment counts, eager hero media, lazy below-fold media, and localized zh-CN/en labels.

- [ ] **Step 2: Run test and verify RED**

Run: `pnpm --filter @junhui/website test -- phase36-homepage.test.ts`

Expected: FAIL because the homepage is still a placeholder.

- [ ] **Step 3: Implement homepage SSR composition**

Fetch `/public/home/${locale}` once and render Hero, Product Categories, Trust Strip, Material/Problem discovery, Capabilities, Featured Products, Applications, Cases, Knowledge, Trust summary, and RFQ CTA in the approved order. Each optional section uses `v-if="items.length"` or an equivalent typed condition.

- [ ] **Step 4: Add metadata without a second Schema system**

Use the homepage API SEO/Schema payload if present; serialize through the existing safe `serializeJsonLd()` utility. Keep one H1 and logical H2/H3 structure.

- [ ] **Step 5: Run tests, SSR build smoke, and commit**

Run: `pnpm --filter @junhui/website test -- phase36-homepage.test.ts`

Run: `pnpm --filter @junhui/website build`

Expected: PASS with no blocking hydration/build errors.

```powershell
git add apps/website/app/components/HomePage.vue apps/website/app/components/PageHero.vue apps/website/app/components/SectionHeader.vue apps/website/app/components/ProductCard.vue apps/website/app/components/ArticleCard.vue apps/website/app/components/CaseCard.vue apps/website/app/components/TrustMetric.vue apps/website/app/components/RfqCta.vue apps/website/app/pages/en/index.vue apps/website/app/pages/zh-cn/index.vue apps/website/tests/phase36-homepage.test.ts
git commit -m "feat: deliver final SSR homepage"
```

### Task 7: Product listing, clean specs, gallery, and detail page

**Files:**
- Create: `apps/website/app/pages/[lang]/products/index.vue`
- Modify: `apps/website/app/pages/[lang]/products/[category]/index.vue`
- Modify: `apps/website/app/pages/[lang]/products/[category]/[slug].vue`
- Create: `apps/website/app/components/SpecTable.vue`
- Create: `apps/website/app/components/PublicImage.vue`
- Create: `apps/website/app/components/PublicVideo.vue`
- Create: `apps/website/app/components/MediaGallery.vue`
- Create: `apps/website/app/components/FilterBar.vue`
- Create: `apps/website/app/components/PaginationNav.vue`
- Create: `apps/website/app/components/EmptyState.vue`
- Test: `apps/website/tests/phase36-products.test.ts`

- [ ] **Step 1: Write failing Product tests**

Assert meaningful filters, canonical pagination links, 2–4 card specs, no price/cart/rating/stock, Product Detail relations as anchors, five spec types rendered without `<pre>`, Gallery keyboard close, alt text, image dimensions, lazy/eager behavior, and RFQ source context.

- [ ] **Step 2: Run tests and verify RED**

Run: `pnpm --filter @junhui/website test -- phase36-products.test.ts`

Expected: FAIL against the current raw specification page.

- [ ] **Step 3: Implement Product listings**

Load the Public Product list with query-derived filters. Keep filter state in the URL, reset the page when a filter changes, and render an EmptyState instead of an empty grid.

- [ ] **Step 4: Implement SpecTable and Gallery**

Group specs by `group`, render `<dl>`/table semantics appropriate to viewport, format all values from DTO strings, and never parse raw ORM fields. Implement an accessible dialog-based lightbox with Escape and focus restoration.

- [ ] **Step 5: Rebuild Product Detail**

Use PageHero, MediaGallery, SpecTable, Models, structured description, RelationLinks, FAQAccordion, GeoAnswer, Trust/Case/Knowledge sections, and RfqCta. Do not duplicate backend Schema/index rules.

- [ ] **Step 6: Run tests/typecheck and commit**

Run: `pnpm --filter @junhui/website test -- phase36-products.test.ts`

Run: `pnpm --filter @junhui/website typecheck`

Expected: PASS.

```powershell
git add apps/website/app/pages/[lang]/products apps/website/app/components/SpecTable.vue apps/website/app/components/PublicImage.vue apps/website/app/components/PublicVideo.vue apps/website/app/components/MediaGallery.vue apps/website/app/components/FilterBar.vue apps/website/app/components/PaginationNav.vue apps/website/app/components/EmptyState.vue apps/website/tests/phase36-products.test.ts
git commit -m "feat: finish public product experience"
```

### Task 8: Material, Technology, Application, and Solution page system

**Files:**
- Create: `apps/website/app/pages/[lang]/materials/index.vue`
- Create: `apps/website/app/pages/[lang]/technologies/index.vue`
- Create: `apps/website/app/pages/[lang]/applications/index.vue`
- Create: `apps/website/app/pages/[lang]/solutions/index.vue`
- Modify: corresponding `[slug].vue` files
- Modify: `apps/website/app/components/PublicCatalogEntityPage.vue`
- Create: `apps/website/app/components/RelationLinks.vue`
- Create: `apps/website/app/components/GeoAnswer.vue`
- Test: `apps/website/tests/phase36-content.test.ts`

- [ ] **Step 1: Write failing catalog content tests**

Assert all four list/detail families have unique H1, Breadcrumb, early definition/direct answer, semantic field labels, published relation links, optional GEO, RFQ source, localized labels, and no raw translation object iteration.

- [ ] **Step 2: Run tests and verify RED**

Run: `pnpm --filter @junhui/website test -- phase36-content.test.ts`

Expected: FAIL because list routes and final templates are missing.

- [ ] **Step 3: Implement shared typed list and detail shells**

Use a page configuration map for labels and section ordering, while mapping explicit DTO fields for each entity type. Do not render arbitrary object keys from `translation`.

- [ ] **Step 4: Implement RelationLinks and GeoAnswer**

Render only backend-approved links, visible direct answer/key facts/evidence, clear section headings, and user-visible related questions when supplied.

- [ ] **Step 5: Run tests and commit**

Run: `pnpm --filter @junhui/website test -- phase36-content.test.ts`

Expected: PASS.

```powershell
git add apps/website/app/pages/[lang]/materials apps/website/app/pages/[lang]/technologies apps/website/app/pages/[lang]/applications apps/website/app/pages/[lang]/solutions apps/website/app/components/PublicCatalogEntityPage.vue apps/website/app/components/RelationLinks.vue apps/website/app/components/GeoAnswer.vue apps/website/tests/phase36-content.test.ts
git commit -m "feat: finish catalog authority pages"
```

### Task 9: Knowledge Center, Case Studies, and Expert pages

**Files:**
- Create: `apps/website/app/pages/[lang]/knowledge/index.vue`
- Modify: `apps/website/app/pages/[lang]/knowledge/[category]/[slug].vue`
- Create: `apps/website/app/pages/[lang]/case-studies/index.vue`
- Modify: `apps/website/app/pages/[lang]/case-studies/[slug].vue`
- Create: `apps/website/app/pages/[lang]/experts/index.vue`
- Modify: `apps/website/app/pages/[lang]/experts/[slug].vue`
- Create: `apps/website/app/components/FAQAccordion.vue`
- Test: `apps/website/tests/phase36-content.test.ts`

- [ ] **Step 1: Add failing Authority UI tests**

Assert Knowledge author/reviewer/source metadata, visible GEO direct answer, real source links, Case privacy omission, optional customer identity allowlist rendering, Expert real-person fields, FAQ visible/schema consistency contract, and RFQ context.

- [ ] **Step 2: Run tests and verify RED**

Run: `pnpm --filter @junhui/website test -- phase36-content.test.ts`

Expected: new assertions FAIL against minimal pages.

- [ ] **Step 3: Implement index pages**

Use published list DTOs with category/type filters and PaginationNav. Show neutral EmptyState without fabricated article, case, or expert content.

- [ ] **Step 4: Implement final detail pages**

Knowledge: Summary/Direct Answer, authorship, dates, body, facts, FAQ, sources, relations, RFQ. Case: public engineering facts and allowlisted identity only. Expert: verified person profile and authored published knowledge.

- [ ] **Step 5: Run privacy regressions and commit**

Run: `pnpm --filter @junhui/website test -- phase36-content.test.ts phase34-public-pages.test.ts`

Run: `cd apps/api; .venv/Scripts/python.exe -m pytest tests/test_phase34_authority_services.py tests/test_phase34_remediation.py -q`

Expected: PASS with no private identity leakage.

```powershell
git add apps/website/app/pages/[lang]/knowledge apps/website/app/pages/[lang]/case-studies apps/website/app/pages/[lang]/experts apps/website/app/components/FAQAccordion.vue apps/website/tests/phase36-content.test.ts
git commit -m "feat: finish authority content pages"
```

### Task 10: About, Capabilities, Trust, Exhibitions, and Downloads

**Files:**
- Modify: `apps/website/app/pages/[lang]/about.vue`
- Modify: `apps/website/app/pages/[lang]/capabilities/index.vue`
- Modify: `apps/website/app/pages/[lang]/capabilities/[slug].vue`
- Modify: certificates, patents, honors, exhibitions, downloads page files
- Test: `apps/website/tests/phase36-content.test.ts`

- [ ] **Step 1: Add failing Trust UI tests**

Assert About conditional sections, Capability published Equipment, non-route Trust without detail links, Exhibition detail links, broken downloads absent, no “verified” claims without data, and company facts sourced from DTO values.

- [ ] **Step 2: Run tests and verify RED**

Run: `pnpm --filter @junhui/website test -- phase36-content.test.ts`

Expected: new Trust presentation assertions FAIL.

- [ ] **Step 3: Implement About and Capability templates**

Render only populated Company sections. Capability detail uses the server-approved Equipment list, Technology/Media/Product/Case relations, visible GEO, Breadcrumb, and RFQ.

- [ ] **Step 4: Implement Trust aggregate and Downloads templates**

Certificate/Patent/Honor remain aggregate-only. Exhibition stays index/detail. Downloads show public metadata and safe download links; no private or missing object URL can appear.

- [ ] **Step 5: Run Final Patch regressions and commit**

Run: `pnpm --filter @junhui/website test -- phase36-content.test.ts phase35-remediation-contract.test.ts`

Run: `cd apps/api; .venv/Scripts/python.exe -m pytest tests/test_phase35_remediation.py tests/test_phase35_final_patch_v2.py tests/test_phase35_final_patch_v3.py -q`

Expected: PASS.

```powershell
git add apps/website/app/pages/[lang]/about.vue apps/website/app/pages/[lang]/capabilities apps/website/app/pages/[lang]/certificates apps/website/app/pages/[lang]/patents apps/website/app/pages/[lang]/honors apps/website/app/pages/[lang]/exhibitions apps/website/app/pages/[lang]/downloads apps/website/tests/phase36-content.test.ts
git commit -m "feat: finish company trust presentation"
```

### Task 11: Search UI, RFQ final UX, language switching, telemetry, and errors

**Files:**
- Create: `apps/website/app/pages/[lang]/search/index.vue`
- Modify: `apps/website/app/pages/[lang]/request-a-quote/index.vue`
- Create: `apps/website/app/error.vue`
- Modify: `apps/website/app/components/LanguageSwitcher.vue`
- Modify: `apps/website/app/composables/useTelemetry.ts`
- Test: `apps/website/tests/phase36-interactions.test.ts`

- [ ] **Step 1: Write failing interaction tests**

Test search query persistence/type groups/no-result recovery/noindex, Product-to-RFQ source, multi-item add/remove, file upload states, accepted types/size text, localized validation, success reference, alternate language routing, 404/500 recovery, and analytics-disabled no-op events.

- [ ] **Step 2: Run tests and verify RED**

Run: `pnpm --filter @junhui/website test -- phase36-interactions.test.ts`

Expected: FAIL because Search/error pages and final interactions are missing.

- [ ] **Step 3: Implement Search**

Use `useAsyncData` for server-visible results when `q` exists. Add `robots=noindex,follow`, accessible form labels, grouped results, query-preserving pagination, and Product/Knowledge/RFQ recovery links.

- [ ] **Step 4: Finish RFQ UX without changing security**

Keep the existing anonymous POST and submission-token attachment flow. Add client state only for usability; server remains authoritative. Track each attachment as Pending/Uploading/Uploaded/Failed and never expose a private download URL.

- [ ] **Step 5: Implement language/error/telemetry behavior**

LanguageSwitcher uses backend alternates with home fallback. `error.vue` distinguishes friendly 404 and 500 messages without stack data. Telemetry exports four typed events and returns immediately when no provider is configured.

- [ ] **Step 6: Run interaction and RFQ security tests**

Run: `pnpm --filter @junhui/website test -- phase36-interactions.test.ts phase35-remediation-contract.test.ts`

Run: `cd apps/api; .venv/Scripts/python.exe -m pytest tests/test_phase35_foundation.py tests/test_phase35_remediation.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add apps/website/app/pages/[lang]/search apps/website/app/pages/[lang]/request-a-quote/index.vue apps/website/app/error.vue apps/website/app/components/LanguageSwitcher.vue apps/website/app/composables/useTelemetry.ts apps/website/tests/phase36-interactions.test.ts
git commit -m "feat: finish search and RFQ journeys"
```

### Task 12: Accessibility, responsive, security, and browser QA

**Files:**
- Modify: affected Website components/pages found during QA
- Modify: `apps/website/app/assets/css/main.css`
- Test: all `apps/website/tests/phase36-*.test.ts`

- [ ] **Step 1: Run complete Website test/type/style checks**

Run:

```powershell
pnpm --filter @junhui/website test
pnpm --filter @junhui/website typecheck
pnpm exec prettier --check .
```

Expected: PASS.

- [ ] **Step 2: Build and start production-like stack**

Run: `pnpm build`

Run: `docker compose up -d --build`

Expected: Nuxt Website/Admin builds succeed and all core containers reach healthy.

- [ ] **Step 3: Execute browser matrix**

Check Home, Product list/detail, Material, Technology, Application, Solution, Knowledge index/detail, Case, About, Capability index/detail, Trust aggregates, Exhibition, Downloads, RFQ, Search, and 404 at 320/375/430/768/1024/1280/1440/1920.

For each representative journey assert:

- no horizontal scroll;
- no console errors or hydration mismatch;
- keyboard navigation and visible focus;
- Escape/focus return for menus/gallery;
- no `undefined`, `null`, raw JSON, private fields, or broken images;
- Hero LCP image eager and below-fold images lazy;
- correct zh-CN/en UI labels.

- [ ] **Step 4: Run Lighthouse when locally available**

Run Mobile and Desktop Lighthouse against the production Website URL. Record Performance, Accessibility, Best Practices, SEO, LCP, and CLS. Treat deviations as measured limitations, not ranking guarantees.

- [ ] **Step 5: Fix observed blockers and rerun focused checks**

Apply only scoped fixes for accessibility, responsive overflow, hydration, console, image sizing, or security headers. Add a regression test for every corrected blocker.

- [ ] **Step 6: Commit**

```powershell
git add apps/website
git commit -m "fix: complete responsive and accessibility QA"
```

### Task 13: Full regression, Docker health, and completion report

**Files:**
- Create: `docs/architecture/phase3-6-completion-report.md`

- [ ] **Step 1: Run Ruff and full backend pytest**

Run:

```powershell
apps/api/.venv/Scripts/python.exe -m ruff check apps/api
cd apps/api
.venv/Scripts/python.exe -m pytest -q
```

Expected: Ruff PASS; local backend tests PASS with only documented external-service skips.

- [ ] **Step 2: Run real integration profile**

Run: `docker compose --profile test run --rm --build api-test`

Expected: empty PostgreSQL migrates to latest, Seed completes, real PostgreSQL/Redis/MinIO tests PASS, and existing migration/security/privacy suites remain green.

- [ ] **Step 3: Verify Seed idempotency explicitly**

Run twice:

```powershell
docker compose exec -T api python -m app.cli seed
docker compose exec -T api python -m app.cli seed
```

Expected: both commands print `Phase 3.2 system seed completed.` and exit 0.

- [ ] **Step 4: Run complete frontend verification**

Run:

```powershell
pnpm --filter @junhui/website test
pnpm --filter @junhui/admin test
pnpm --filter @junhui/website typecheck
pnpm --filter @junhui/admin typecheck
pnpm exec prettier --check .
pnpm build
```

Expected: all tests, typechecks, formatting checks, and both Nuxt production builds PASS.

- [ ] **Step 5: Rebuild and verify Docker health**

Run: `docker compose up -d --build`

Run: `docker compose ps --format "table {{.Service}}\t{{.State}}\t{{.Health}}\t{{.Status}}"`

Expected: api, worker, postgres, redis, minio, website, admin, and nginx are healthy. Verify API live/ready and Website/Admin/Nginx return HTTP 200 on their documented ports.

- [ ] **Step 6: Write the completion report**

Record exact Branch/Base/Final implementation SHA, every UI/page family, Public Spec DTO, SEO/GEO visible UI, privacy/security results, test counts, build output, Docker states, browser sizes, Lighthouse scores or limitation, known issues, Phase 3.7 recommendation, and `$seo-rank`/`$geo-rank` conflict review.

- [ ] **Step 7: Self-review and commit report**

Run: `rg -n "TBD|TODO|FIXME|placeholder" docs/architecture/phase3-6-completion-report.md`

Expected: no unresolved completion-report placeholders.

```powershell
git add docs/architecture/phase3-6-completion-report.md
git commit -m "docs: add phase 3.6 completion report"
```

- [ ] **Step 8: Final clean-state check**

Run: `git diff --check; git status --short --branch; git log -5 --oneline`

Expected: no diff errors, clean worktree, and Phase 3.6 commits on the dedicated branch. Do not merge, deploy, submit Search Console, enable analytics, or enter Phase 3.7.
