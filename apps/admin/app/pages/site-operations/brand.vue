<!-- 页面用途：维护站点双语展示名称、Logo 与浏览器小图标的草稿和应用版。 -->
<script setup lang="ts">
interface BrandTranslation {
  display_name: string
  short_name: string
}

interface BrandMedia {
  id: string
  filename: string
  mime_type: string
  url: string
}

interface BrandVersion {
  translations: Record<'zh-CN' | 'en', BrandTranslation>
  media: Record<'header_logo' | 'mobile_logo' | 'favicon', BrandMedia | null>
}

interface BrandDetail {
  draft: BrandVersion
  applied: BrandVersion
  draft_revision: number
  applied_revision: number
  applied_at: string | null
}

interface MediaOption {
  id: string
  type: string
  filename: string
  url: string | null
  mime_type: string
  visibility: string
  upload_status: string
}

const api = useAuthorityApi()
const { currentUser } = useAuth()
const detail = ref<BrandDetail | null>(null)
const mediaOptions = ref<MediaOption[]>([])
const translations = reactive<Record<'zh-CN' | 'en', BrandTranslation>>({
  'zh-CN': { display_name: '', short_name: '' },
  en: { display_name: '', short_name: '' },
})
const selectedMedia = reactive<Record<'header_logo' | 'mobile_logo' | 'favicon', string>>({
  header_logo: '',
  mobile_logo: '',
  favicon: '',
})
const loading = ref(true)
const saving = ref(false)
const message = ref('')
const errorMessage = ref('')
const preview = ref<BrandVersion | null>(null)

const canEdit = computed(() => currentUser.value?.permissions.includes('content.update') ?? false)
const canApply = computed(() => currentUser.value?.permissions.includes('content.publish') ?? false)
const eligibleMedia = computed(() =>
  mediaOptions.value.filter(
    (item) =>
      item.type === 'image' &&
      item.visibility === 'public' &&
      item.upload_status === 'ready' &&
      Boolean(item.url),
  ),
)

useHead({
  title: '站点与品牌 · 骏辉内容运营后台',
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})

/** 输入服务端详情；输出无，把完整双语草稿复制到表单，避免局部语言覆盖。 */
function fillForm(value: BrandDetail): void {
  for (const locale of ['zh-CN', 'en'] as const) {
    translations[locale] = { ...value.draft.translations[locale] }
  }
  selectedMedia.header_logo = value.draft.media.header_logo?.id ?? ''
  selectedMedia.mobile_logo = value.draft.media.mobile_logo?.id ?? ''
  selectedMedia.favicon = value.draft.media.favicon?.id ?? ''
}

/** 读取真实品牌草稿、应用版与可选择的公开就绪图片。 */
async function loadBrand(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const [brand, media] = await Promise.all([
      api.detail<BrandDetail>('/site-operations/brand'),
      api.detail<MediaOption[]>('/media'),
    ])
    detail.value = brand
    mediaOptions.value = media
    fillForm(brand)
  } catch {
    detail.value = null
    errorMessage.value = '品牌设置尚未建立，或当前账号没有读取权限。'
  } finally {
    loading.value = false
  }
}

/** 幂等建立等值品牌和导航初始配置，不覆盖已有草稿。 */
async function initializeSettings(): Promise<void> {
  if (!canEdit.value) return
  await api.create('/site-operations/initialize', {})
  await loadBrand()
  message.value = '已建立等值初始配置并重新读取。'
}

/** 保存完整中英文品牌草稿，空媒体值明确保存为 null。 */
async function saveDraft(): Promise<void> {
  if (!detail.value || !canEdit.value) return
  saving.value = true
  message.value = ''
  errorMessage.value = ''
  try {
    const saved = await api.update<BrandDetail>('/site-operations/brand/draft', {
      expected_revision: detail.value.draft_revision,
      translations: {
        'zh-CN': { ...translations['zh-CN'] },
        en: { ...translations.en },
      },
      header_logo_media_id: selectedMedia.header_logo || null,
      mobile_logo_media_id: selectedMedia.mobile_logo || null,
      favicon_media_id: selectedMedia.favicon || null,
    })
    detail.value = saved
    fillForm(saved)
    message.value = `草稿已保存并 fresh GET 回读，revision ${saved.draft_revision}。`
  } catch {
    errorMessage.value = '保存失败：请检查双语名称、媒体状态或版本冲突。'
  } finally {
    saving.value = false
  }
}

/** 从认证预览接口读取草稿，不使用公开查询参数解锁。 */
async function loadPreview(): Promise<void> {
  try {
    const result = await api.detail<{ brand: BrandVersion }>('/site-operations/brand/preview')
    preview.value = result.brand
    message.value = '认证草稿预览已从服务端重新读取。'
  } catch {
    errorMessage.value = '预览读取失败，请先保存草稿并确认登录状态。'
  }
}

/** 经员工明确确认后应用当前已保存草稿。 */
async function applyDraft(): Promise<void> {
  if (!detail.value || !canApply.value || !window.confirm('确认把当前品牌草稿应用到 Demo 前台吗？'))
    return
  try {
    detail.value = await api.create<BrandDetail>('/site-operations/brand/apply', {
      expected_revision: detail.value.draft_revision,
    })
    fillForm(detail.value)
    message.value = '品牌草稿已确认应用并重新读取。'
  } catch {
    errorMessage.value = '应用失败：请刷新并确认发布权限和草稿版本。'
  }
}

/** 从当前应用版生成一个新草稿，保留全部修订与审计历史。 */
async function restoreDraft(): Promise<void> {
  if (!detail.value || !canEdit.value || !window.confirm('确认从当前应用版恢复出一个新草稿吗？'))
    return
  detail.value = await api.create<BrandDetail>('/site-operations/brand/restore', {
    expected_revision: detail.value.draft_revision,
  })
  fillForm(detail.value)
  message.value = '已从应用版生成新草稿；普通前台未改变。'
}

onMounted(loadBrand)
</script>

<template>
  <main class="operations-page" data-testid="site-brand-editor">
    <header class="operations-hero">
      <div>
        <p>站点运营设置 R1</p>
        <h1>站点与品牌</h1>
        <span>名称仅用于站点展示，不修改法定公司资料。保存草稿不会影响普通前台。</span>
      </div>
      <NuxtLink to="/media">打开媒体资源库</NuxtLink>
    </header>
    <p v-if="loading" class="operations-card" role="status">正在读取品牌设置…</p>
    <section v-else-if="!detail" class="operations-card">
      <p role="alert">{{ errorMessage }}</p>
      <button v-if="canEdit" type="button" @click="initializeSettings">建立等值初始配置</button>
    </section>
    <template v-else>
      <section class="status-strip">
        <span>草稿 revision {{ detail.draft_revision }}</span
        ><span>应用版 revision {{ detail.applied_revision }}</span
        ><span>{{
          detail.draft_revision === detail.applied_revision ? '草稿与应用版一致' : '有未应用修改'
        }}</span>
      </section>
      <div class="operations-grid">
        <section class="operations-card">
          <h2>双语展示名称</h2>
          <fieldset v-for="locale in ['zh-CN', 'en'] as const" :key="locale">
            <legend>{{ locale === 'zh-CN' ? '简体中文' : '英语' }}</legend>
            <label
              >展示名称<input
                v-model="translations[locale].display_name"
                maxlength="120"
                :disabled="!canEdit"
            /></label>
            <label
              >简称<input
                v-model="translations[locale].short_name"
                maxlength="40"
                :disabled="!canEdit"
            /></label>
          </fieldset>
          <h2>品牌图片</h2>
          <label v-for="field in ['header_logo', 'mobile_logo', 'favicon'] as const" :key="field">
            {{
              field === 'header_logo'
                ? '桌面 Logo'
                : field === 'mobile_logo'
                  ? '移动端 Logo'
                  : '浏览器小图标'
            }}
            <select v-model="selectedMedia[field]" :disabled="!canEdit">
              <option value="">使用现有批准静态素材</option>
              <option v-for="media in eligibleMedia" :key="media.id" :value="media.id">
                {{ media.filename }}
              </option>
            </select>
          </label>
        </section>
        <aside class="operations-card preview-card">
          <h2>认证草稿预览</h2>
          <template v-if="preview">
            <img
              v-if="preview.media.header_logo"
              :src="preview.media.header_logo.url"
              :alt="preview.translations['zh-CN'].display_name"
            />
            <p v-else>桌面 Logo：继续使用前台内置的批准素材。</p>
            <strong>{{ preview.translations['zh-CN'].display_name }}</strong>
            <span>{{ preview.translations.en.display_name }}</span>
            <span>浏览器小图标：{{ preview.media.favicon?.filename || '继续使用现有设置' }}</span>
          </template>
          <p v-else>点击“认证预览”读取已保存的服务端草稿。</p>
          <button type="button" @click="loadPreview">认证预览</button>
        </aside>
      </div>
      <footer class="operations-actions">
        <button type="button" :disabled="saving || !canEdit" @click="saveDraft">
          保存完整双语草稿
        </button>
        <button type="button" :disabled="saving || !canApply" @click="applyDraft">确认应用</button>
        <button type="button" :disabled="saving || !canEdit" @click="restoreDraft">
          从应用版恢复草稿
        </button>
        <button type="button" @click="loadBrand">重新读取</button>
      </footer>
      <p v-if="message" class="notice" role="status">{{ message }}</p>
      <p v-if="errorMessage" class="error" role="alert">{{ errorMessage }}</p>
    </template>
  </main>
</template>

<style scoped>
.operations-page {
  width: min(calc(100% - 2rem), 88rem);
  margin: auto;
  padding: 2rem 0 5rem;
}
.operations-hero,
.status-strip,
.operations-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}
.operations-hero {
  padding: 1.4rem;
  color: #fff;
  background: linear-gradient(120deg, #07182b, #0f5791);
  border-radius: 1rem;
}
.operations-hero p,
.operations-hero h1 {
  margin: 0.2rem 0;
}
.operations-hero span {
  color: #c8def0;
}
.operations-hero a {
  color: #fff;
}
.status-strip {
  margin: 1rem 0;
  padding: 0.8rem 1rem;
  background: #e9f3fb;
  border: 1px solid #c8dfef;
  border-radius: 0.7rem;
}
.operations-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(18rem, 1fr);
  gap: 1rem;
}
.operations-card {
  padding: 1.2rem;
  background: #fff;
  border: 1px solid #dce4ec;
  border-radius: 0.85rem;
  box-shadow: 0 0.8rem 2.4rem rgb(20 46 73 / 8%);
}
fieldset {
  margin: 0 0 1rem;
  padding: 1rem;
  border: 1px solid #dce4ec;
  border-radius: 0.7rem;
}
label {
  display: grid;
  gap: 0.35rem;
  margin: 0.75rem 0;
  font-weight: 700;
}
input,
select {
  width: 100%;
  padding: 0.7rem;
  border: 1px solid #b9c7d4;
  border-radius: 0.5rem;
}
.preview-card {
  align-content: start;
  display: grid;
  gap: 0.75rem;
}
.preview-card img {
  width: min(100%, 18rem);
  height: 5rem;
  object-fit: contain;
  object-position: left;
  background: #07182b;
  padding: 0.7rem;
}
.operations-actions {
  justify-content: flex-start;
  margin-top: 1rem;
  flex-wrap: wrap;
}
.operations-actions button,
.preview-card button,
.operations-card button {
  padding: 0.7rem 1rem;
  border: 0;
  border-radius: 0.5rem;
  color: #fff;
  background: #0f70c9;
  cursor: pointer;
}
.operations-actions button:nth-child(n + 2) {
  color: #17324a;
  background: #e6edf3;
}
.notice,
.error {
  padding: 0.8rem 1rem;
  border-radius: 0.5rem;
}
.notice {
  color: #075b42;
  background: #e4f6ef;
}
.error {
  color: #8d2118;
  background: #feecea;
}
@media (max-width: 52rem) {
  .operations-grid {
    grid-template-columns: 1fr;
  }
  .operations-hero,
  .status-strip {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
