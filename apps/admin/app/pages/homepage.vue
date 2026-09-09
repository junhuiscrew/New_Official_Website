<!-- 页面用途：用可视化表单维护双语首页十四模块的顺序、显隐、样式和已发布产品引用。 -->
<script setup lang="ts">
import { adminMeta } from '../admin-config'

type ModuleKey =
  | 'hero'
  | 'core_product_families'
  | 'materials'
  | 'special_applications'
  | 'technologies'
  | 'manufacturing_capability'
  | 'why_junhui'
  | 'factory_equipment'
  | 'solutions'
  | 'case_studies'
  | 'technical_knowledge'
  | 'certificates_patents'
  | 'global_markets'
  | 'rfq_cta'

interface ModuleConfig {
  key: ModuleKey
  visible: boolean
  variant: string
  product_slugs: string[]
}

interface LayoutConfig {
  schema_version: number
  modules: ModuleConfig[]
}

interface ProductOption {
  slug: string
  name: string
  summary: string
  media?: { src: string; alt: string } | null
}

interface LanguageDetail {
  locale: { code: string; slug: string; name: string; native_name: string }
  translation: { display_name: string }
  layout: {
    draft: LayoutConfig
    applied: LayoutConfig
    draft_revision: number
    applied_revision: number
    applied_at: string | null
  }
  products: ProductOption[]
}

interface HomepageDetail {
  page: { system_key: string; status: string }
  languages: LanguageDetail[]
}

const moduleLabels: Record<ModuleKey, string> = {
  hero: 'Hero 首页主视觉',
  core_product_families: 'Core Product Families 核心产品系列',
  materials: 'Materials 材料',
  special_applications: 'Special Applications 特殊应用',
  technologies: 'Technologies 技术',
  manufacturing_capability: 'Manufacturing Capability 制造能力',
  why_junhui: 'Why Junhui 为什么选择骏辉',
  factory_equipment: 'Factory & Equipment 工厂与设备',
  solutions: 'Solutions 解决方案',
  case_studies: 'Case Studies 案例研究',
  technical_knowledge: 'Technical Knowledge 技术知识',
  certificates_patents: 'Certificates / Patents 证书与专利',
  global_markets: 'Global Markets 全球市场',
  rfq_cta: 'RFQ CTA 询价入口',
}

const variantOptions: Record<ModuleKey, string[]> = {
  hero: ['product-focus', 'navy'],
  core_product_families: ['product-rail', 'light', 'soft'],
  materials: ['light', 'soft', 'rail'],
  special_applications: ['light', 'soft', 'split'],
  technologies: ['navy', 'light', 'soft'],
  manufacturing_capability: ['split', 'light', 'soft'],
  why_junhui: ['soft', 'light', 'navy'],
  factory_equipment: ['split', 'light', 'soft'],
  solutions: ['light', 'soft', 'rail'],
  case_studies: ['soft', 'light', 'rail'],
  technical_knowledge: ['light', 'soft', 'rail'],
  certificates_patents: ['light', 'soft', 'navy'],
  global_markets: ['soft', 'light', 'navy'],
  rfq_cta: ['navy', 'light', 'soft'],
}

const productReferenceModules = new Set<ModuleKey>(['hero', 'core_product_families'])
const { currentUser } = useAuth()
const api = useAuthorityApi()
const detail = ref<HomepageDetail | null>(null)
const activeLocaleCode = ref('zh-CN')
const editableModules = ref<ModuleConfig[]>([])
const activeModuleKey = ref<ModuleKey>('hero')
const loading = ref(true)
const saving = ref(false)
const message = ref('')
const errorMessage = ref('')

const canRead = computed(() => currentUser.value?.permissions.includes('content.read') ?? false)
const canEdit = computed(() => currentUser.value?.permissions.includes('content.update') ?? false)
const canApply = computed(() => currentUser.value?.permissions.includes('content.publish') ?? false)
const activeLanguage = computed(
  () => detail.value?.languages.find((item) => item.locale.code === activeLocaleCode.value) ?? null,
)
const previewUrl = computed(
  // 使用当前后台同源路径，确保主实例与 Demo 各自留在自己的认证边界内。
  () => `/preview/${activeLanguage.value?.locale.slug ?? 'zh-cn'}/`,
)
const activeModule = computed(
  () => editableModules.value.find((module) => module.key === activeModuleKey.value) ?? null,
)
const activeModuleIndex = computed(() =>
  editableModules.value.findIndex((module) => module.key === activeModuleKey.value),
)
const hasUnappliedChanges = computed(() => {
  const applied = activeLanguage.value?.layout.applied.modules ?? []
  return editableModules.value.some((module, index) => {
    const saved = applied[index]
    return (
      !saved ||
      module.key !== saved.key ||
      module.visible !== saved.visible ||
      module.variant !== saved.variant ||
      module.product_slugs.join('|') !== saved.product_slugs.join('|')
    )
  })
})

useHead({
  title: `Homepage Presentation · ${adminMeta.title}`,
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})

/** 输入服务端草稿；输出完全独立的表单数组，避免未保存操作污染回读对象。 */
function cloneModules(modules: ModuleConfig[]): ModuleConfig[] {
  return modules.map((module) => ({ ...module, product_slugs: [...module.product_slugs] }))
}

/** 读取双语首页详情，并把当前语言的最新草稿装入编辑器。 */
async function loadHomepage(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    detail.value = await api.detail<HomepageDetail>('/presentation/homepage')
    if (!detail.value.languages.some((item) => item.locale.code === activeLocaleCode.value)) {
      activeLocaleCode.value = detail.value.languages[0]?.locale.code ?? 'zh-CN'
    }
    editableModules.value = cloneModules(activeLanguage.value?.layout.draft.modules ?? [])
    if (!editableModules.value.some((module) => module.key === activeModuleKey.value)) {
      activeModuleKey.value = editableModules.value[0]?.key ?? 'hero'
    }
  } catch {
    detail.value = null
    errorMessage.value = '首页配置尚未建立，或当前账号无读取权限。'
  } finally {
    loading.value = false
  }
}

/** 幂等建立固定首页身份和双语十四模块配置。 */
async function initializeHomepage(): Promise<void> {
  if (!canEdit.value) return
  errorMessage.value = ''
  try {
    await api.create<HomepageDetail>('/presentation/homepage/initialize', {})
    await loadHomepage()
    message.value = '首页配置已建立并重新读取。'
  } catch {
    errorMessage.value = '建立失败；请检查运行目标、权限或已有页面冲突。'
  }
}

/** 按当前位置移动模块；输入起点和偏移，输出只修改本地草稿顺序。 */
function moveModule(index: number, direction: -1 | 1): void {
  const destination = index + direction
  if (destination < 0 || destination >= editableModules.value.length) return
  const next = [...editableModules.value]
  const [module] = next.splice(index, 1)
  if (!module) return
  next.splice(destination, 0, module)
  editableModules.value = next
}

/** 切换一个已发布产品引用，最多保留三个且不修改产品本身。 */
function toggleProduct(module: ModuleConfig, slug: string): void {
  if (module.product_slugs.includes(slug)) {
    module.product_slugs = module.product_slugs.filter((item) => item !== slug)
    return
  }
  if (module.product_slugs.length < 3) module.product_slugs = [...module.product_slugs, slug]
}

/** 保存完整白名单草稿，并以服务端新 revision 回填表单。 */
async function saveDraft(): Promise<void> {
  if (!activeLanguage.value || !canEdit.value) return
  saving.value = true
  message.value = ''
  errorMessage.value = ''
  try {
    const saved = await api.update<LanguageDetail>(
      `/presentation/homepage/${activeLocaleCode.value}/draft`,
      {
        expected_revision: activeLanguage.value.layout.draft_revision,
        modules: editableModules.value,
      },
    )
    const languageIndex = detail.value!.languages.findIndex(
      (item) => item.locale.code === activeLocaleCode.value,
    )
    detail.value!.languages[languageIndex] = saved
    editableModules.value = cloneModules(saved.layout.draft.modules)
    message.value = `草稿已保存并回读，revision ${saved.layout.draft_revision}。`
  } catch {
    errorMessage.value = '保存失败或 revision 已冲突；未覆盖服务端修改，请重新读取。'
  } finally {
    saving.value = false
  }
}

/** 把当前已保存草稿应用到普通首页；发布权限仍由服务端强制执行。 */
async function applyLayout(): Promise<void> {
  if (!activeLanguage.value || !canApply.value) return
  saving.value = true
  message.value = ''
  errorMessage.value = ''
  try {
    await api.create<LanguageDetail>(`/presentation/homepage/${activeLocaleCode.value}/apply`, {
      expected_revision: activeLanguage.value.layout.draft_revision,
    })
    await loadHomepage()
    message.value = '当前语言布局已应用，并重新读取实际应用版。'
  } catch {
    errorMessage.value = '应用失败；请确认草稿 revision、产品公开状态和发布权限。'
  } finally {
    saving.value = false
  }
}

/** 从当前应用版恢复出新草稿，不直接改变普通首页。 */
async function restoreDraft(): Promise<void> {
  if (!activeLanguage.value || !canEdit.value) return
  saving.value = true
  message.value = ''
  errorMessage.value = ''
  try {
    await api.create<LanguageDetail>(`/presentation/homepage/${activeLocaleCode.value}/restore`, {
      expected_revision: activeLanguage.value.layout.draft_revision,
    })
    await loadHomepage()
    message.value = '草稿已从当前应用版恢复。'
  } catch {
    errorMessage.value = '恢复失败或 revision 已冲突；请重新读取。'
  } finally {
    saving.value = false
  }
}

/** 在新的 Admin 同源标签页打开由服务端校验的完整布局预览。 */
function openPreview(): void {
  window.open(previewUrl.value, '_blank', 'noopener,noreferrer')
}

watch(activeLocaleCode, () => {
  editableModules.value = cloneModules(activeLanguage.value?.layout.draft.modules ?? [])
  message.value = ''
  errorMessage.value = ''
})
onMounted(loadHomepage)
</script>

<template>
  <main class="homepage-admin" data-testid="homepage-module-editor">
    <header class="homepage-admin__hero">
      <div>
        <p class="admin-eyebrow">Website Presentation V1.0 · R1</p>
        <h1>首页模块编辑器</h1>
        <p>调整双语首页的顺序、显隐、有限样式与现有产品引用；正文仍由原业务模块维护。</p>
      </div>
      <div class="homepage-admin__hero-actions">
        <NuxtLink to="/site-overview">查看全站模块总览</NuxtLink>
        <button
          v-if="canRead && detail"
          type="button"
          class="button-secondary"
          @click="openPreview"
        >
          完整布局预览
        </button>
      </div>
    </header>

    <p v-if="loading" class="admin-panel" role="status">正在读取实际首页配置…</p>
    <section v-else-if="!detail" class="admin-panel admin-panel--center">
      <h2>首页配置不可用</h2>
      <p role="alert">{{ errorMessage }}</p>
      <button v-if="canEdit" type="button" @click="initializeHomepage">建立首页配置</button>
    </section>

    <template v-else>
      <section class="homepage-toolbar" aria-label="Homepage editing controls">
        <div class="locale-tabs" role="tablist" aria-label="语言">
          <button
            v-for="language in detail.languages"
            :key="language.locale.code"
            type="button"
            role="tab"
            :aria-selected="activeLocaleCode === language.locale.code"
            :class="{ active: activeLocaleCode === language.locale.code }"
            @click="activeLocaleCode = language.locale.code"
          >
            {{ language.locale.native_name }}
          </button>
        </div>
        <dl v-if="activeLanguage" class="revision-summary">
          <div>
            <dt>草稿</dt>
            <dd>{{ activeLanguage.layout.draft_revision }}</dd>
          </div>
          <div>
            <dt>应用版</dt>
            <dd>{{ activeLanguage.layout.applied_revision }}</dd>
          </div>
          <div>
            <dt>状态</dt>
            <dd>{{ hasUnappliedChanges ? '有未应用修改' : '与应用版一致' }}</dd>
          </div>
        </dl>
      </section>

      <section class="homepage-workspace">
        <!-- 模块清单：只负责选择、排序和状态识别，不再把十四组表单纵向全部展开。 -->
        <nav class="module-navigator" aria-label="首页模块清单">
          <header>
            <div>
              <p class="admin-eyebrow">MODULES</p>
              <h2>模块清单</h2>
            </div>
            <span>{{ editableModules.filter((module) => module.visible).length }} / 14 显示</span>
          </header>
          <div
            v-for="(module, index) in editableModules"
            :key="module.key"
            :class="{
              'module-navigator__item--active': activeModuleKey === module.key,
              'module-navigator__item--hidden': !module.visible,
            }"
          >
            <button
              type="button"
              class="module-navigator__identity"
              @click="activeModuleKey = module.key"
            >
              <span class="module-order">{{ String(index + 1).padStart(2, '0') }}</span>
              <span>
                <strong>{{ moduleLabels[module.key] }}</strong>
                <small>{{ module.visible ? module.variant : '已隐藏' }}</small>
              </span>
            </button>
            <span class="module-navigator__move">
              <button
                type="button"
                aria-label="上移"
                :disabled="index === 0 || !canEdit"
                @click.stop="moveModule(index, -1)"
              >
                ↑
              </button>
              <button
                type="button"
                aria-label="下移"
                :disabled="index === editableModules.length - 1 || !canEdit"
                @click.stop="moveModule(index, 1)"
              >
                ↓
              </button>
            </span>
          </div>
        </nav>

        <!-- 属性与预览：只编辑当前模块，并复用真实的服务端认证预览。 -->
        <section v-if="activeModule" class="module-properties">
          <header>
            <div>
              <p class="admin-eyebrow">PROPERTIES</p>
              <h2>{{ moduleLabels[activeModule.key] }}</h2>
            </div>
            <span>位置 {{ String(activeModuleIndex + 1).padStart(2, '0') }}</span>
          </header>

          <div class="module-controls">
            <label class="visibility-control">
              <input v-model="activeModule.visible" type="checkbox" :disabled="!canEdit" />
              在普通首页显示
            </label>
            <label>
              视觉样式
              <select v-model="activeModule.variant" :disabled="!canEdit">
                <option
                  v-for="variant in variantOptions[activeModule.key]"
                  :key="variant"
                  :value="variant"
                >
                  {{ variant }}
                </option>
              </select>
            </label>
          </div>

          <fieldset
            v-if="productReferenceModules.has(activeModule.key)"
            class="product-reference"
            data-testid="homepage-product-reference"
          >
            <legend>引用已发布产品（最多 3 款，不改变产品精选状态）</legend>
            <label v-for="product in activeLanguage?.products ?? []" :key="product.slug">
              <input
                type="checkbox"
                :checked="activeModule.product_slugs.includes(product.slug)"
                :disabled="
                  !canEdit ||
                  (!activeModule.product_slugs.includes(product.slug) &&
                    activeModule.product_slugs.length >= 3)
                "
                @change="toggleProduct(activeModule, product.slug)"
              />
              <span>{{ product.name }}</span>
              <small>{{ product.slug }}</small>
            </label>
          </fieldset>

          <div class="homepage-preview-frame">
            <header>
              <span>认证完整布局预览</span>
              <button type="button" @click="openPreview">新窗口打开</button>
            </header>
            <iframe :src="previewUrl" title="首页完整布局预览" loading="lazy" />
          </div>
        </section>

        <aside class="homepage-actions">
          <p class="admin-eyebrow">当前语言操作</p>
          <h2>{{ activeLanguage?.locale.native_name }}</h2>
          <p>保存只更新草稿；“应用布局”需要单独发布权限。</p>
          <button type="button" :disabled="saving || !canEdit" @click="saveDraft">
            {{ saving ? '处理中…' : '保存草稿' }}
          </button>
          <button
            type="button"
            class="button-secondary"
            :disabled="saving || !canRead"
            @click="openPreview"
          >
            打开完整预览
          </button>
          <button
            type="button"
            class="button-secondary"
            :disabled="saving || !canApply"
            @click="applyLayout"
          >
            应用布局
          </button>
          <button
            type="button"
            class="button-quiet"
            :disabled="saving || !canEdit"
            @click="restoreDraft"
          >
            从应用版恢复草稿
          </button>
          <p v-if="message" class="admin-message" role="status">{{ message }}</p>
          <p v-if="errorMessage" class="admin-error" role="alert">{{ errorMessage }}</p>
        </aside>
      </section>
    </template>
  </main>
</template>

<style scoped>
.homepage-admin {
  width: min(calc(100% - 2rem), 92rem);
  margin: 0 auto;
  padding-block: 2rem 5rem;
}

.homepage-admin__hero {
  padding: 1.25rem 1.4rem;
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 2rem;
  color: #dbeeff;
  background: linear-gradient(115deg, #07182b, #0a4a88);
  border-radius: 1rem;
  box-shadow: 0 1.5rem 3rem rgb(7 24 43 / 18%);
}

.homepage-admin__hero h1,
.homepage-admin__hero .admin-eyebrow {
  color: #fff;
}

.homepage-admin__hero h1 {
  margin-block: 0.25rem 0.35rem;
  font-size: clamp(1.55rem, 2.4vw, 2.15rem);
}

.homepage-admin__hero p {
  margin-block: 0;
  max-width: 52rem;
  font-size: 0.78rem;
}

.homepage-admin__hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.homepage-admin__hero-actions a,
.homepage-admin__hero-actions button {
  padding: 0.75rem 1rem;
  color: #fff;
  background: rgb(255 255 255 / 10%);
  border: 1px solid rgb(255 255 255 / 40%);
  border-radius: 0.5rem;
  text-decoration: none;
}

.admin-eyebrow {
  margin: 0 0 0.4rem;
  color: #1765a9;
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.homepage-toolbar {
  margin-top: 1.5rem;
  padding: 1rem 1.25rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  background: #fff;
  border: 1px solid #d8e1ea;
  border-radius: 0.75rem;
}

.locale-tabs {
  display: flex;
  gap: 0.5rem;
}

.locale-tabs button {
  color: #24415f;
  background: #edf3f8;
  border: 1px solid transparent;
  border-radius: 0.4rem;
}

.locale-tabs button.active {
  color: #fff;
  background: #0a5da8;
}

.revision-summary {
  margin: 0;
  display: flex;
  gap: 1.5rem;
}

.revision-summary div {
  display: grid;
  gap: 0.1rem;
}

.revision-summary dt {
  color: #65778a;
  font-size: 0.75rem;
}

.revision-summary dd {
  margin: 0;
  color: #0d2d4c;
  font-weight: 750;
}

.homepage-workspace {
  margin-top: 1.5rem;
  display: grid;
  grid-template-columns: minmax(16rem, 0.42fr) minmax(26rem, 1fr) 17rem;
  align-items: start;
  gap: 1rem;
}

.module-navigator,
.module-properties {
  display: grid;
  align-content: start;
  background: #fff;
  border: 1px solid #d8e1ea;
  border-radius: 0.75rem;
  overflow: hidden;
}
.module-navigator > header,
.module-properties > header {
  padding: 1rem;
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 0.75rem;
  background: #f6f9fb;
  border-bottom: 1px solid #e0e8ef;
}
.module-navigator h2,
.module-properties h2 {
  margin: 0;
  font-size: 1rem;
}
.module-navigator > header > span,
.module-properties > header > span {
  color: #65778a;
  font-size: 0.7rem;
}
.module-navigator > div {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  border-bottom: 1px solid #edf1f5;
}
.module-navigator > div:last-child {
  border-bottom: 0;
}
.module-navigator > div.module-navigator__item--active {
  background: #eaf5fd;
  box-shadow: inset 3px 0 #1484ce;
}
.module-navigator > div.module-navigator__item--hidden {
  background: #f7f8f9;
  opacity: 0.72;
}
.module-navigator__identity {
  min-width: 0;
  padding: 0.62rem 0.45rem 0.62rem 0.8rem;
  display: grid;
  grid-template-columns: 2rem minmax(0, 1fr);
  align-items: center;
  gap: 0.55rem;
  text-align: left;
  background: transparent;
  border: 0;
}
.module-navigator__identity > span:last-child {
  min-width: 0;
  display: grid;
  gap: 0.12rem;
}
.module-navigator__identity strong,
.module-navigator__identity small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.module-navigator__identity strong {
  color: #173651;
  font-size: 0.75rem;
}
.module-navigator__identity small {
  color: #718599;
  font-size: 0.64rem;
}
.module-order {
  color: #0a5da8;
  font-family: Consolas, monospace;
  font-size: 0.72rem;
  font-weight: 800;
}
.module-navigator__move {
  display: flex;
  padding-right: 0.45rem;
  gap: 0.2rem;
}
.module-navigator__move button {
  width: 1.65rem;
  min-height: 1.65rem;
  padding: 0;
  color: #24415f;
  background: #edf3f8;
  border: 0;
  border-radius: 0.3rem;
}
.module-properties {
  padding-bottom: 1rem;
  gap: 1rem;
}
.module-controls {
  padding-inline: 1rem;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}
.module-controls label {
  display: grid;
  gap: 0.35rem;
  color: #40576d;
  font-size: 0.72rem;
}

.visibility-control {
  grid-template-columns: auto 1fr !important;
  align-items: center;
}

.visibility-control input,
.product-reference input {
  width: auto;
  min-height: auto;
}

.product-reference {
  margin: 0 1rem;
  padding: 1rem;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.7rem;
  border: 1px solid #d8e1ea;
  border-radius: 0.55rem;
}

.product-reference legend {
  padding-inline: 0.4rem;
  color: #24415f;
  font-size: 0.82rem;
  font-weight: 700;
}

.product-reference label {
  padding: 0.7rem;
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  gap: 0.15rem 0.55rem;
  background: #f4f8fb;
  border-radius: 0.45rem;
}

.product-reference small {
  grid-column: 2;
  color: #65778a;
}

.homepage-preview-frame {
  margin-inline: 1rem;
  overflow: hidden;
  background: #07182b;
  border: 1px solid #b8c9d7;
  border-radius: 0.65rem;
}
.homepage-preview-frame > header {
  padding: 0.55rem 0.7rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #d8eafa;
  font-size: 0.68rem;
}
.homepage-preview-frame button {
  padding: 0.35rem 0.55rem;
  color: #0a4f86;
  background: #e9f6ff;
  border: 0;
  border-radius: 0.3rem;
}
.homepage-preview-frame iframe {
  width: 100%;
  height: 22rem;
  display: block;
  background: #fff;
  border: 0;
}

.homepage-actions {
  position: sticky;
  top: 1rem;
  padding: 1.25rem;
  display: grid;
  gap: 0.75rem;
  background: #fff;
  border: 1px solid #d8e1ea;
  border-radius: 0.75rem;
  box-shadow: 0 0.8rem 2rem rgb(7 24 43 / 8%);
}

.homepage-actions h2,
.homepage-actions p {
  margin: 0;
}

.homepage-actions button,
.admin-panel button {
  color: #fff;
  background: #0a5da8;
  border: 1px solid #0a5da8;
  border-radius: 0.45rem;
}

.homepage-actions .button-secondary,
.homepage-admin__hero-actions .button-secondary {
  color: #0a4a88;
  background: #fff;
  border-color: #9eb7cc;
}

.homepage-actions .button-quiet {
  color: #4b6175;
  background: transparent;
  border-color: transparent;
}

.admin-panel {
  margin-top: 1.5rem;
  padding: 2rem;
  background: #fff;
  border-radius: 0.75rem;
}

.admin-panel--center {
  text-align: center;
}

.admin-message,
.admin-error {
  padding: 0.7rem;
  border-radius: 0.4rem;
  font-size: 0.8rem;
}

.admin-message {
  color: #1d6836;
  background: #e8f6ec;
}

.admin-error {
  color: #8f2424;
  background: #fff0f0;
}

@media (max-width: 64rem) {
  .homepage-workspace {
    grid-template-columns: minmax(0, 1fr);
  }

  .homepage-actions {
    position: static;
  }
}

@media (max-width: 48rem) {
  .homepage-admin__hero,
  .homepage-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .revision-summary {
    flex-wrap: wrap;
  }

  .module-controls,
  .product-reference {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
