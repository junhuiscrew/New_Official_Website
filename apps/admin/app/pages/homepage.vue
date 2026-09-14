<!-- 页面用途：用可视化表单维护双语首页十四模块、Hero 轮播及已发布产品引用。 -->
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
  slides: HeroSlideConfig[]
}

interface HeroSlideConfig {
  id: string
  media_id: string
  title: string
  subtitle: string
  cta_label: string | null
  cta_href: string | null
  enabled: boolean
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

interface MediaOption {
  id: string
  type: string
  filename: string
  url: string | null
  mime_type: string
  visibility: string
  upload_status: string
  width: number | null
  height: number | null
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
const mediaOptions = ref<MediaOption[]>([])
const activeLocaleCode = ref('zh-CN')
const editableModules = ref<ModuleConfig[]>([])
const activeModuleKey = ref<ModuleKey>('hero')
const loading = ref(true)
const saving = ref(false)
const message = ref('')
const errorMessage = ref('')
const previewNonce = ref(0)

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
const previewFrameKey = computed(
  () =>
    `${previewUrl.value}:${activeLanguage.value?.layout.draft_revision ?? 0}:${previewNonce.value}`,
)
const eligibleMedia = computed(() =>
  mediaOptions.value.filter(
    (item) =>
      item.type === 'image' &&
      item.visibility === 'public' &&
      item.upload_status === 'ready' &&
      Boolean(item.url),
  ),
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
      module.product_slugs.join('|') !== saved.product_slugs.join('|') ||
      !sameSlides(module.slides, saved.slides)
    )
  })
})

useHead({
  title: `首页模块编辑器 · ${adminMeta.title}`,
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})

/** 输入服务端草稿；输出完全独立的表单数组，避免未保存操作污染回读对象。 */
function cloneModules(modules: ModuleConfig[]): ModuleConfig[] {
  return modules.map((module) => ({
    ...module,
    product_slugs: [...module.product_slugs],
    slides: (module.slides ?? []).map((slide) => ({ ...slide })),
  }))
}

/** 输入两组轮播配置；输出 boolean，用字段级比较识别尚未应用的改动。 */
function sameSlides(current: HeroSlideConfig[], saved: HeroSlideConfig[] | undefined): boolean {
  const baseline = saved ?? []
  return (
    current.length === baseline.length &&
    current.every((slide, index) => {
      const target = baseline[index]
      if (!target) return false
      return (
        slide.id === target.id &&
        slide.media_id === target.media_id &&
        slide.title === target.title &&
        slide.subtitle === target.subtitle &&
        slide.cta_label === target.cta_label &&
        slide.cta_href === target.cta_href &&
        slide.enabled === target.enabled
      )
    })
  )
}

/** 读取双语首页详情，并把当前语言的最新草稿装入编辑器。 */
async function loadHomepage(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const [homepage, media] = await Promise.all([
      api.detail<HomepageDetail>('/presentation/homepage'),
      api.detail<MediaOption[]>('/media'),
    ])
    detail.value = homepage
    mediaOptions.value = media
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

/** 输入媒体 ID；输出可用于后台预览的公开图片选项。 */
function mediaFor(mediaId: string): MediaOption | undefined {
  return eligibleMedia.value.find((item) => item.id === mediaId)
}

/** 输入无；输出无，在 Hero 末尾新增一项可编辑的 Demo 轮播草稿。 */
function addHeroSlide(): void {
  if (!activeModule.value || activeModule.value.key !== 'hero' || !canEdit.value) return
  if (activeModule.value.slides.length >= 5) {
    errorMessage.value = 'Hero 轮播最多 5 张；请先停用或删除不需要的项目。'
    return
  }
  const media = eligibleMedia.value[0]
  if (!media) {
    errorMessage.value = '媒体库暂无已就绪的公开图片，请先到“媒体资源库”上传。'
    return
  }
  activeModule.value.slides.push({
    id: `demo-hero-${Date.now()}`,
    media_id: media.id,
    title: '新的 Demo 轮播项',
    subtitle: '请替换为当前语言的演示说明。',
    cta_label: null,
    cta_href: null,
    enabled: true,
  })
  message.value = '已在当前语言草稿中新增轮播项；请填写后保存草稿。'
  errorMessage.value = ''
}

/** 输入轮播下标；输出无，经确认后从当前语言草稿删除对应项目。 */
function removeHeroSlide(index: number): void {
  if (!activeModule.value || activeModule.value.key !== 'hero' || !canEdit.value) return
  if (!window.confirm('确定从当前语言草稿中删除这张轮播图吗？')) return
  activeModule.value.slides.splice(index, 1)
}

/** 输入轮播下标和方向；输出无，仅调整当前语言草稿中的显示顺序。 */
function moveHeroSlide(index: number, direction: -1 | 1): void {
  if (!activeModule.value || activeModule.value.key !== 'hero' || !canEdit.value) return
  const destination = index + direction
  if (destination < 0 || destination >= activeModule.value.slides.length) return
  const [slide] = activeModule.value.slides.splice(index, 1)
  if (slide) activeModule.value.slides.splice(destination, 0, slide)
}

/** 输入可空表单值；输出去除首尾空格后的字符串或 null。 */
function optionalText(value: string | null): string | null {
  return value?.trim() || null
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
    const modules = cloneModules(editableModules.value).map((module) => ({
      ...module,
      slides: module.slides.map((slide) => ({
        ...slide,
        title: slide.title.trim(),
        subtitle: slide.subtitle.trim(),
        cta_label: optionalText(slide.cta_label),
        cta_href: optionalText(slide.cta_href),
      })),
    }))
    const saved = await api.update<LanguageDetail>(
      `/presentation/homepage/${activeLocaleCode.value}/draft`,
      {
        expected_revision: activeLanguage.value.layout.draft_revision,
        modules,
      },
    )
    const languageIndex = detail.value!.languages.findIndex(
      (item) => item.locale.code === activeLocaleCode.value,
    )
    detail.value!.languages[languageIndex] = saved
    editableModules.value = cloneModules(saved.layout.draft.modules)
    previewNonce.value += 1
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

/** 输入无；输出无，强制重新加载已保存草稿的认证预览。 */
function refreshPreview(): void {
  previewNonce.value += 1
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
        <p class="admin-eyebrow">官网呈现 V1.0 · R1</p>
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
              <p class="admin-eyebrow">首页模块</p>
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
              <p class="admin-eyebrow">模块属性</p>
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

          <!-- Hero 轮播编辑器：每个语言分别保存，图片只能从公开且已就绪的媒体库中选择。 -->
          <section
            v-if="activeModule.key === 'hero'"
            class="hero-slide-editor"
            data-testid="hero-slide-editor"
          >
            <header>
              <div>
                <h3>Banner Slider 轮播图</h3>
                <p>
                  当前为 {{ activeLanguage?.locale.native_name }} 文案；切换上方语言后分别维护。
                  新增内容和图片仅为 Demo 素材，不代表正式企业资料。
                </p>
              </div>
              <button
                type="button"
                :disabled="!canEdit || activeModule.slides.length >= 5"
                @click="addHeroSlide"
              >
                新增轮播项
              </button>
            </header>
            <p class="hero-slide-editor__limit">
              最多 5 张；列表顺序就是前台播放顺序。保存草稿后可在下方预览。
            </p>

            <div v-if="!activeModule.slides.length" class="hero-slide-editor__empty">
              当前语言尚无轮播项，普通首页会继续使用原 Hero，不影响其他 13 个模块。
            </div>

            <article
              v-for="(slide, slideIndex) in activeModule.slides"
              :key="slide.id"
              class="hero-slide-card"
            >
              <header>
                <div class="hero-slide-card__identity">
                  <span>{{ String(slideIndex + 1).padStart(2, '0') }}</span>
                  <div>
                    <strong>{{ slide.title || '未填写标题' }}</strong>
                    <small>{{ slide.enabled ? '已启用' : '已停用' }}</small>
                  </div>
                </div>
                <div class="hero-slide-card__actions">
                  <button
                    type="button"
                    aria-label="轮播项上移"
                    :disabled="!canEdit || slideIndex === 0"
                    @click="moveHeroSlide(slideIndex, -1)"
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    aria-label="轮播项下移"
                    :disabled="!canEdit || slideIndex === activeModule.slides.length - 1"
                    @click="moveHeroSlide(slideIndex, 1)"
                  >
                    ↓
                  </button>
                  <button
                    type="button"
                    class="hero-slide-card__delete"
                    :disabled="!canEdit"
                    @click="removeHeroSlide(slideIndex)"
                  >
                    删除
                  </button>
                </div>
              </header>

              <div class="hero-slide-card__body">
                <figure>
                  <!-- 缩略图使用独立比例框，不跟随右侧编辑字段的高度拉伸。 -->
                  <div class="hero-slide-card__thumbnail">
                    <img
                      v-if="mediaFor(slide.media_id)?.url"
                      :src="mediaFor(slide.media_id)!.url!"
                      :alt="mediaFor(slide.media_id)!.filename"
                      :width="mediaFor(slide.media_id)!.width ?? undefined"
                      :height="mediaFor(slide.media_id)!.height ?? undefined"
                    />
                  </div>
                  <figcaption>
                    {{ mediaFor(slide.media_id)?.filename || '图片当前不可公开使用' }}
                  </figcaption>
                </figure>

                <div class="hero-slide-card__fields">
                  <label class="hero-slide-card__enabled">
                    <input v-model="slide.enabled" type="checkbox" :disabled="!canEdit" />
                    在前台启用这一项
                  </label>
                  <label>
                    图片
                    <select v-model="slide.media_id" required :disabled="!canEdit">
                      <option v-for="media in eligibleMedia" :key="media.id" :value="media.id">
                        {{ media.filename }}（{{ media.width || '?' }} × {{ media.height || '?' }}）
                      </option>
                    </select>
                  </label>
                  <label>
                    主标题
                    <input v-model="slide.title" maxlength="120" required :disabled="!canEdit" />
                  </label>
                  <label>
                    副标题
                    <textarea
                      v-model="slide.subtitle"
                      maxlength="300"
                      rows="3"
                      required
                      :disabled="!canEdit"
                    />
                  </label>
                  <div class="hero-slide-card__cta-fields">
                    <label>
                      按钮文案（可留空）
                      <input v-model="slide.cta_label" maxlength="40" :disabled="!canEdit" />
                    </label>
                    <label>
                      跳转链接（可留空）
                      <input
                        v-model="slide.cta_href"
                        maxlength="240"
                        placeholder="/zh-cn/products/"
                        :disabled="!canEdit"
                      />
                    </label>
                  </div>
                  <p>按钮文案与跳转链接必须同时填写；链接只允许当前站点内的绝对路径。</p>
                </div>
              </div>
            </article>
          </section>

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
              <span>
                <button type="button" @click="refreshPreview">刷新预览</button>
                <button type="button" @click="openPreview">新窗口打开</button>
              </span>
            </header>
            <iframe
              :key="previewFrameKey"
              :src="previewUrl"
              title="首页完整布局预览"
              loading="lazy"
            />
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
          <p v-if="message" class="admin-message" role="status">
            {{ message }}
          </p>
          <p v-if="errorMessage" class="admin-error" role="alert">
            {{ errorMessage }}
          </p>
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

.hero-slide-editor {
  margin-inline: 1rem;
  display: grid;
  gap: 0.85rem;
}

.hero-slide-editor > header {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 1rem;
}

.hero-slide-editor h3,
.hero-slide-editor p {
  margin: 0;
}

.hero-slide-editor h3 {
  color: #173651;
  font-size: 0.98rem;
}

.hero-slide-editor > header p,
.hero-slide-editor__limit,
.hero-slide-card__fields > p {
  margin-top: 0.25rem;
  color: #65778a;
  font-size: 0.7rem;
  line-height: 1.6;
}

.hero-slide-editor > header button {
  flex: none;
  color: #fff;
  background: #0a5da8;
  border: 1px solid #0a5da8;
  border-radius: 0.4rem;
}

.hero-slide-editor__empty {
  padding: 1.2rem;
  color: #536b80;
  background: #f6f9fb;
  border: 1px dashed #b8c9d7;
  border-radius: 0.5rem;
  text-align: center;
}

.hero-slide-card {
  overflow: hidden;
  border: 1px solid #cbd9e5;
  border-radius: 0.65rem;
}

.hero-slide-card > header {
  padding: 0.65rem 0.75rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  background: linear-gradient(90deg, #eef6fc, #f9fbfd);
  border-bottom: 1px solid #dbe5ed;
}

.hero-slide-card__identity {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.65rem;
}

.hero-slide-card__identity > span {
  color: #0a5da8;
  font-family: Consolas, monospace;
  font-weight: 800;
}

.hero-slide-card__identity div {
  min-width: 0;
  display: grid;
  gap: 0.08rem;
}

.hero-slide-card__identity strong {
  overflow: hidden;
  color: #173651;
  font-size: 0.78rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hero-slide-card__identity small {
  color: #65778a;
  font-size: 0.64rem;
}

.hero-slide-card__actions {
  display: flex;
  gap: 0.3rem;
}

.hero-slide-card__actions button {
  min-height: 1.9rem;
  padding: 0.25rem 0.55rem;
  color: #24415f;
  background: #fff;
  border: 1px solid #b8c9d7;
  border-radius: 0.3rem;
}

.hero-slide-card__actions .hero-slide-card__delete {
  color: #942f2f;
  border-color: #e0b5b5;
}

.hero-slide-card__body {
  padding: 0.8rem;
  display: grid;
  grid-template-columns: minmax(10rem, 16rem) minmax(0, 1fr);
  align-items: start;
  gap: 0.9rem;
}

.hero-slide-card figure {
  width: 100%;
  max-width: 16rem;
  margin: 0;
  align-self: start;
  overflow: hidden;
  background: #07182b;
  border-radius: 0.45rem;
}

.hero-slide-card__thumbnail {
  width: 100%;
  aspect-ratio: 16 / 9;
  overflow: hidden;
  background: #dce9f4;
}

.hero-slide-card__thumbnail img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}

.hero-slide-card figcaption {
  padding: 0.45rem 0.55rem;
  overflow: hidden;
  color: #cfe5f7;
  font-size: 0.62rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hero-slide-card__fields {
  display: grid;
  gap: 0.65rem;
}

.hero-slide-card__fields label {
  display: grid;
  gap: 0.3rem;
  color: #40576d;
  font-size: 0.7rem;
}

.hero-slide-card__fields input,
.hero-slide-card__fields select,
.hero-slide-card__fields textarea {
  width: 100%;
}

.hero-slide-card__enabled {
  grid-template-columns: auto 1fr !important;
  align-items: center;
}

.hero-slide-card__enabled input {
  width: auto;
  min-height: auto;
}

.hero-slide-card__cta-fields {
  display: grid;
  grid-template-columns: minmax(0, 0.8fr) minmax(0, 1.2fr);
  gap: 0.65rem;
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
.homepage-preview-frame > header > span:last-child {
  display: flex;
  gap: 0.4rem;
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
  .product-reference,
  .hero-slide-card__body,
  .hero-slide-card__cta-fields {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
