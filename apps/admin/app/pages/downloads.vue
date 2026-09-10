<!-- 页面用途：以文件名和双语字段表单维护公开下载资源，不要求编辑JSON或UUID。 -->
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ENTITY_STATUS_LABELS, labelFrom } from '~/utils/adminZhCn'

interface LocaleItem {
  id: string
  code: string
  native_name: string
}
interface MediaItem {
  id: string
  filename: string
  type: string
}
interface TranslationDraft {
  locale_id: string
  native_name: string
  title: string
  summary: string
}

useHead({
  title: '下载资料 · Junhui Admin',
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})
const api = useAuthorityApi()
const items = ref<Array<Record<string, unknown>>>([])
const media = ref<MediaItem[]>([])
const locales = ref<LocaleItem[]>([])
const brokenMedia = ref<Array<Record<string, unknown>>>([])
const editingId = ref<string | null>(null)
const translations = ref<TranslationDraft[]>([])
const errorMessage = ref('')
const loading = ref(true)
const successMessage = ref('')
const form = reactive({
  slug: '',
  resource_type: 'document',
  status: 'enabled',
  media_asset_id: '',
  version_label: '',
  published_date: '',
  requires_form: false,
  sort_order: 0,
})

function reset(): void {
  editingId.value = null
  Object.assign(form, {
    slug: '',
    resource_type: 'document',
    status: 'enabled',
    media_asset_id: '',
    version_label: '',
    published_date: '',
    requires_form: false,
    sort_order: 0,
  })
  translations.value = locales.value.map((locale) => ({
    locale_id: locale.id,
    native_name: locale.native_name,
    title: '',
    summary: '',
  }))
}

/** 读取下载、媒体完整文件名、语言和坏链检查结果。 */
async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const [result, mediaResult, localeResult, broken] = await Promise.all([
      api.detail<{ items: Array<Record<string, unknown>> }>('/downloads'),
      api.detail<MediaItem[]>('/media'),
      api.detail<LocaleItem[]>('/locales'),
      api.detail<{ items: Array<Record<string, unknown>> }>('/downloads/broken-media'),
    ])
    items.value = result.items
    media.value = mediaResult.filter((asset) => asset.type === 'document')
    locales.value = localeResult
    brokenMedia.value = broken.items
    reset()
  } catch {
    errorMessage.value = '无法读取下载资源。'
  } finally {
    loading.value = false
  }
}

async function save(): Promise<void> {
  const body = {
    ...form,
    version_label: form.version_label || null,
    published_date: form.published_date || null,
    translations: translations.value.map((item) => ({
      locale_id: item.locale_id,
      fields: { title: item.title, summary: item.summary || null },
    })),
  }
  try {
    if (editingId.value) await api.update(`/downloads/${editingId.value}`, body)
    else await api.create('/downloads', body)
    await load()
    successMessage.value = '已保存，并从接口重新读取最新内容。'
  } catch {
    errorMessage.value = '保存失败，请检查文件和双语标题。'
  }
}

/** 输入下载记录；输出优先中文、其次英文的可读标题。 */
function displayTitle(item: Record<string, unknown>): string {
  const rows = (item.translations as Array<Record<string, unknown>> | undefined) || []
  const zh = rows.find(
    (row) => locales.value.find((locale) => locale.id === row.locale_id)?.code === 'zh-CN',
  )
  const en = rows.find(
    (row) => locales.value.find((locale) => locale.id === row.locale_id)?.code === 'en',
  )
  return String(zh?.title || en?.title || rows.find((row) => row.title)?.title || '未填写标题')
}

function edit(item: Record<string, unknown>): void {
  editingId.value = String(item.id)
  Object.assign(form, {
    slug: String(item.slug || ''),
    resource_type: String(item.resource_type || 'document'),
    status: String(item.status || 'enabled'),
    media_asset_id: String(item.media_asset_id || ''),
    version_label: String(item.version_label || ''),
    published_date: String(item.published_date || ''),
    requires_form: Boolean(item.requires_form),
    sort_order: Number(item.sort_order || 0),
  })
  const source = (item.translations as Array<Record<string, unknown>>) || []
  translations.value = locales.value.map((locale) => {
    const translation = source.find((row) => row.locale_id === locale.id) || {}
    return {
      locale_id: locale.id,
      native_name: locale.native_name,
      title: String(translation.title || ''),
      summary: String(translation.summary || ''),
    }
  })
}

async function archive(id: unknown): Promise<void> {
  await api.archive(`/downloads/${id}/archive`)
  await load()
}
onMounted(load)
</script>

<template>
  <main class="admin-shell downloads-page">
    <header class="page-heading">
      <div>
        <p>公开资源</p>
        <h1>下载资料</h1>
        <span>文件、双语标题和版本信息保存在真实下载资源表。</span>
      </div>
      <button type="button" @click="reset">新建资料</button>
    </header>
    <p v-if="errorMessage" class="error-message" role="alert">
      {{ errorMessage }}
    </p>
    <p v-if="successMessage" role="status">{{ successMessage }}</p>
    <p v-if="loading" role="status">正在读取下载资料…</p>
    <aside v-if="brokenMedia.length" class="error-message" role="alert">
      <strong>发现缺失媒体对象</strong>
      <ul>
        <li v-for="item in brokenMedia" :key="String(item.asset_id)">
          {{ item.download_slug }} · {{ item.reason || 'object_missing' }}
        </li>
      </ul>
    </aside>
    <div class="downloads-layout">
      <section class="record-list">
        <button
          v-for="item in items"
          :key="String(item.id)"
          type="button"
          :class="{ active: editingId === String(item.id) }"
          @click="edit(item)"
        >
          <strong>{{ displayTitle(item) }}</strong>
          <small>{{ item.slug }}</small>
          <span>{{ labelFrom(ENTITY_STATUS_LABELS, item.status) }}</span>
        </button>
      </section>
      <form class="editor-form" @submit.prevent="save">
        <fieldset>
          <legend>基本信息</legend>
          <div class="downloads-grid">
            <label>Slug（路径标识）<input v-model="form.slug" required /></label>
            <label>资料类型<input v-model="form.resource_type" /></label>
            <label
              >公开文件<select v-model="form.media_asset_id" required>
                <option value="" disabled>选择PDF或文档</option>
                <option v-for="asset in media" :key="asset.id" :value="asset.id">
                  {{ asset.filename }}
                </option>
              </select></label
            >
            <label
              >状态<select v-model="form.status">
                <option value="enabled">启用</option>
                <option value="disabled">停用</option>
                <option value="retired">退役</option>
              </select></label
            >
            <label>版本标签<input v-model="form.version_label" /></label>
            <label>发布日期<input v-model="form.published_date" type="date" /></label>
          </div>
        </fieldset>
        <fieldset>
          <legend>中英文内容</legend>
          <fieldset
            v-for="translation in translations"
            :key="translation.locale_id"
            class="translation-fields"
          >
            <legend>{{ translation.native_name }}</legend>
            <label>标题<input v-model="translation.title" required /></label
            ><label>摘要<textarea v-model="translation.summary" /></label>
          </fieldset>
        </fieldset>
        <div class="form-actions">
          <button type="submit">
            {{ editingId ? '保存更改' : '创建资料' }}</button
          ><button v-if="editingId" type="button" class="danger" @click="archive(editingId)">
            归档
          </button>
        </div>
      </form>
    </div>
  </main>
</template>

<style scoped>
.downloads-page {
  display: grid;
  align-content: start;
  gap: 1rem;
}
.page-heading > div {
  display: grid;
  gap: 0.2rem;
}
.page-heading p,
.page-heading h1 {
  margin: 0;
}
.page-heading p {
  color: #0f70c9;
  font-size: 0.64rem;
  font-weight: 850;
  letter-spacing: 0.13em;
}
.page-heading span {
  color: #6f8092;
}
.downloads-layout {
  display: grid;
  grid-template-columns: minmax(14rem, 0.65fr) minmax(0, 2fr);
  gap: 1rem;
  align-items: start;
}
.downloads-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.8rem;
}
@media (max-width: 54rem) {
  .downloads-layout,
  .downloads-grid {
    grid-template-columns: 1fr;
  }
}
</style>
