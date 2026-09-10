<!-- 页面用途：公开媒体资源库，以可读文件名维护上传、预览和双语元数据。 -->
<script setup lang="ts">
import { labelFrom } from '~/utils/adminZhCn'

useHead({
  title: '媒体资源库',
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})
const api = useAuthorityApi()
interface MediaItem {
  id: string
  type: string
  filename: string
  url: string | null
  mime_type: string
  file_extension: string
  visibility: string
  width: number | null
  height: number | null
}
interface LocaleItem {
  id: string
  code: string
  native_name: string
}
interface MediaTranslation {
  locale_id: string
  alt_text: string
  title: string
  caption: string
}
interface MediaDetail extends MediaItem {
  translations: MediaTranslation[]
}

const items = ref<MediaItem[]>([])
const locales = ref<LocaleItem[]>([])
const selectedAsset = ref('')
const selectedLocale = ref('')
const file = ref<File | null>(null)
const loadingDetail = ref(false)
const message = ref('')
const errorMessage = ref('')
const loading = ref(true)
const operationMode = ref<'metadata' | 'replace' | 'upload'>('metadata')
const translations = reactive({ alt_text: '', title: '', caption: '' })

const selectedItem = computed(() => items.value.find((item) => item.id === selectedAsset.value))

/** 读取当前媒体和语言的已保存元数据，避免选择后显示空白表单。 */
async function loadTranslation(): Promise<void> {
  if (!selectedAsset.value || !selectedLocale.value) return
  loadingDetail.value = true
  message.value = ''
  try {
    const detail = await api.detail<MediaDetail>(`/media/${selectedAsset.value}`)
    const localized = detail.translations.find((item) => item.locale_id === selectedLocale.value)
    translations.alt_text = localized?.alt_text || ''
    translations.title = localized?.title || ''
    translations.caption = localized?.caption || ''
  } finally {
    loadingDetail.value = false
  }
}

async function load() {
  loading.value = true
  errorMessage.value = ''
  try {
    items.value = await api.detail<MediaItem[]>('/media')
    locales.value = await api.detail<LocaleItem[]>('/locales')
    selectedAsset.value ||= items.value[0]?.id || ''
    selectedLocale.value ||= locales.value[0]?.id || ''
    await loadTranslation()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '无法读取媒体资源。'
  } finally {
    loading.value = false
  }
}
async function upload() {
  if (!file.value) return
  const body = new FormData()
  body.append('file', file.value)
  body.append('visibility', 'public')
  try {
    await api.upload('/media/assets', body)
    file.value = null
    await load()
    message.value = '新文件已上传并重新读取。'
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '上传失败。'
  }
}
async function saveTranslation() {
  if (!selectedAsset.value || !selectedLocale.value) return
  const body = new FormData()
  body.append('alt_text', translations.alt_text)
  body.append('title', translations.title)
  body.append('caption', translations.caption)
  await api.request(`/media/${selectedAsset.value}/translations/${selectedLocale.value}`, {
    method: 'PATCH',
    body,
  })
  await loadTranslation()
  message.value = '已保存，并从媒体详情接口重新读取。'
}
watch([selectedAsset, selectedLocale], loadTranslation)
onMounted(load)
</script>
<template>
  <main class="admin-shell media-page">
    <header class="media-page__heading">
      <div>
        <p>媒体运营</p>
        <h1>媒体资源库</h1>
        <span>选择已有记录即可回填双语 Alt、标题与图注；文件本身不会被替换。</span>
      </div>
    </header>
    <nav class="operation-tabs" aria-label="媒体操作类型">
      <button
        type="button"
        :class="{ active: operationMode === 'metadata' }"
        @click="operationMode = 'metadata'"
      >
        元数据修改
      </button>
      <button
        type="button"
        :class="{ active: operationMode === 'replace' }"
        @click="operationMode = 'replace'"
      >
        指定位置换图
      </button>
      <button
        type="button"
        :class="{ active: operationMode === 'upload' }"
        @click="operationMode = 'upload'"
      >
        新上传
      </button>
    </nav>
    <p v-if="loading" role="status">正在读取媒体资源…</p>
    <p v-if="errorMessage" class="error-message" role="alert">
      {{ errorMessage }}
    </p>
    <section v-if="operationMode === 'replace'" class="operation-guide">
      <h2>指定位置换图</h2>
      <p>
        这里不会覆盖原文件。请先在下方确认媒体，再到产品、企业资料或首页模块编辑器中更换对应引用；这样可以保留引用保护和审计记录。
      </p>
      <nav>
        <NuxtLink to="/catalog">前往产品目录</NuxtLink><NuxtLink to="/trust">前往企业资料</NuxtLink
        ><NuxtLink to="/homepage">前往首页模块</NuxtLink>
      </nav>
    </section>
    <form v-if="operationMode === 'upload'" class="operation-guide" @submit.prevent="upload">
      <h2>新上传</h2>
      <p>新文件会创建独立媒体记录，不替换已有媒体，也不会自动改动任何页面引用。</p>
      <label
        >选择文件<input
          type="file"
          accept="image/jpeg,image/png,image/webp,application/pdf,video/mp4,video/webm"
          @change="file = ($event.target as HTMLInputElement).files?.[0] || null"
      /></label>
      <button type="submit" :disabled="!file">上传新文件</button>
    </form>
    <section class="media-workspace">
      <form
        v-show="operationMode === 'metadata'"
        class="media-editor"
        :aria-busy="loadingDetail"
        @submit.prevent="saveTranslation"
      >
        <p class="media-editor__eyebrow">双语元数据</p>
        <h2>{{ selectedItem?.filename || '选择媒体' }}</h2>
        <img
          v-if="selectedItem?.type === 'image' && selectedItem.url"
          :src="selectedItem.url"
          :alt="translations.alt_text || selectedItem.filename"
        />
        <label
          >媒体
          <select v-model="selectedAsset">
            <option v-for="item in items" :key="item.id" :value="item.id">
              {{ labelFrom({ image: '图片', video: '视频', document: '文档' }, item.type) }}
              ·
              {{ item.filename }}
            </option>
          </select></label
        ><label
          >语言
          <select v-model="selectedLocale">
            <option v-for="locale in locales" :key="locale.id" :value="locale.id">
              {{ locale.native_name }}
            </option>
          </select></label
        >
        <p v-if="loadingDetail" class="media-editor__loading" role="status">
          正在读取已保存元数据…
        </p>
        <label
          >替代文本（Alt） <input v-model="translations.alt_text" :disabled="loadingDetail"
        /></label>
        <label>标题 <input v-model="translations.title" :disabled="loadingDetail" /></label>
        <label
          >图注
          <textarea v-model="translations.caption" :disabled="loadingDetail" />
        </label>
        <button type="submit" :disabled="loadingDetail">保存元数据</button>
        <p v-if="message" role="status">{{ message }}</p>
      </form>
      <div class="media-library-grid">
        <button
          v-for="item in items"
          :key="item.id"
          type="button"
          :class="{ 'media-library-card--selected': item.id === selectedAsset }"
          @click="selectedAsset = item.id"
        >
          <img
            v-if="item.type === 'image'"
            :src="String(item.url)"
            :alt="item.filename"
            loading="lazy"
          />
          <video v-else-if="item.type === 'video'" controls preload="none">
            <source :src="String(item.url)" :type="String(item.mime_type)" />
          </video>
          <div v-else class="media-library-file">{{ item.file_extension }}</div>
          <div>
            <strong>{{ item.filename }}</strong>
            <span
              >{{ labelFrom({ image: '图片', video: '视频', document: '文档' }, item.type) }}
              ·
              {{ labelFrom({ public: '公开', private: '私有' }, item.visibility) }}</span
            >
            <small v-if="item.width && item.height">{{ item.width }} × {{ item.height }}</small>
          </div>
        </button>
      </div>
    </section>
  </main>
</template>

<style scoped>
.media-page {
  display: grid;
  align-content: start;
  gap: 1.25rem;
}
.media-page__heading {
  padding: 1.25rem 1.5rem;
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 1rem;
  color: #d9ecfb;
  background: linear-gradient(110deg, #07182b, #0b568f);
  border-radius: 0.9rem;
}
.media-page__heading h1,
.media-page__heading p {
  margin: 0;
  color: #fff;
}
.media-page__heading p {
  color: #77cdf5;
  font-size: 0.68rem;
  font-weight: 800;
  letter-spacing: 0.12em;
}
.media-page__heading span {
  display: block;
  margin-top: 0.45rem;
  font-size: 0.78rem;
}
.media-page__heading form {
  display: flex;
  align-items: end;
  gap: 0.5rem;
}
.media-workspace {
  display: grid;
  grid-template-columns: minmax(18rem, 0.32fr) minmax(0, 1fr);
  align-items: start;
  gap: 1rem;
}
.operation-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.operation-tabs button {
  color: #29465f;
  background: #edf3f7;
}
.operation-tabs button.active {
  color: #fff;
  background: #0f70c9;
}
.operation-guide {
  padding: 1rem;
  display: grid;
  gap: 0.65rem;
  background: #fff;
  border: 1px solid #dce4ec;
  border-radius: 0.8rem;
}
.operation-guide h2,
.operation-guide p {
  margin: 0;
}
.operation-guide nav {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
}
.media-editor {
  position: sticky;
  top: 1rem;
  padding: 1.1rem;
  display: grid;
  gap: 0.8rem;
  background: #fff;
  border: 1px solid #dce4ec;
  border-radius: 0.8rem;
}
.media-editor h2,
.media-editor__eyebrow {
  margin: 0;
}
.media-editor__eyebrow {
  color: #1474bd;
  font-size: 0.65rem;
  font-weight: 800;
  letter-spacing: 0.12em;
}
.media-editor > img {
  width: 100%;
  aspect-ratio: 16 / 10;
  object-fit: cover;
  background: #e9f1f7;
}
.media-editor label {
  display: grid;
  gap: 0.35rem;
  color: #40566c;
  font-size: 0.75rem;
}
.media-editor__loading {
  margin: 0;
  padding: 0.55rem 0.7rem;
  color: #0a5e9e;
  background: #eaf6ff;
}
.media-library-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(13rem, 1fr));
  gap: 1rem;
}
.media-library-grid > button {
  min-width: 0;
  padding: 0;
  text-align: left;
  overflow: hidden;
  background: #fff;
  border: 1px solid #dce4ec;
  border-radius: 0.75rem;
  cursor: pointer;
}
.media-library-grid > .media-library-card--selected {
  border-color: #1685d1;
  box-shadow: 0 0 0 3px rgb(22 133 209 / 14%);
}
.media-library-grid img,
.media-library-grid video,
.media-library-file {
  width: 100%;
  aspect-ratio: 4 / 3;
  display: grid;
  place-items: center;
  object-fit: cover;
  color: #75bce9;
  background: #07192c;
}
.media-library-grid > button > div:last-child {
  padding: 0.75rem;
  display: grid;
  gap: 0.3rem;
}
.media-library-grid strong {
  overflow: hidden;
  color: #23394e;
  font-size: 0.76rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.media-library-grid span {
  color: #78899a;
  font-size: 0.68rem;
}
.media-library-grid small {
  color: #8395a6;
  font-size: 0.65rem;
}
@media (max-width: 58rem) {
  .media-page__heading,
  .media-workspace {
    grid-template-columns: minmax(0, 1fr);
  }
  .media-page__heading {
    align-items: stretch;
    flex-direction: column;
  }
  .media-editor {
    position: static;
  }
}
</style>
