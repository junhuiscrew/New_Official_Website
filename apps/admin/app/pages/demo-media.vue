<!-- 页面用途：以可读文件名维护Demo首页Hero、两段视频及海报，不要求编辑人员填写UUID。 -->
<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

interface DemoMediaAsset {
  id: string
  media_type: 'image' | 'video'
  filename: string
  mime_type: string
  width: number | null
  height: number | null
  duration_seconds: number | null
  preview_url: string
  alt: Record<string, string>
}

interface DemoMediaState {
  token: string
  assignments: Record<string, string | null>
  slots: Record<string, { media_type: 'image' | 'video'; required: boolean }>
  assets: DemoMediaAsset[]
}

const api = useAuthorityApi()
const state = ref<DemoMediaState | null>(null)
const form = reactive<Record<string, string>>({})
const loading = ref(true)
const saving = ref(false)
const message = ref('')
const errorMessage = ref('')

const slotLabels: Record<string, { title: string; note: string }> = {
  hero: { title: '首页 Hero 主视觉', note: '首屏右侧主图，必须选择图片' },
  video_1: { title: '产品演示视频', note: '首页工厂与设备模块第一段视频' },
  poster_1: { title: '产品视频封面', note: '视频载入前显示，可留空' },
  video_2: { title: '制造流程视频', note: '首页工厂与设备模块第二段视频' },
  poster_2: { title: '流程视频封面', note: '视频载入前显示，可留空' },
}

const orderedSlots = ['hero', 'video_1', 'poster_1', 'video_2', 'poster_2']

/** 输入固定槽位；输出存在性有保证的可读标签和校验规则。 */
function slotMeta(slot: string): { title: string; note: string; required: boolean } {
  return {
    title: slotLabels[slot]?.title || slot,
    note: slotLabels[slot]?.note || '',
    required: state.value?.slots[slot]?.required ?? false,
  }
}

/** 输入槽位键；输出媒体类型符合且可公开读取的下拉选项。 */
function optionsFor(slot: string): DemoMediaAsset[] {
  const expected = state.value?.slots[slot]?.media_type
  return (state.value?.assets ?? []).filter((asset) => asset.media_type === expected)
}

/** 输入媒体ID；输出当前选择的完整可读媒体记录。 */
function selectedAsset(slot: string): DemoMediaAsset | undefined {
  return state.value?.assets.find((asset) => asset.id === form[slot])
}

const hasChanges = computed(() =>
  orderedSlots.some((slot) => (form[slot] || null) !== (state.value?.assignments[slot] || null)),
)

/** 从真实管理API读取当前选择，并将服务端并发令牌保存到表单会话。 */
async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await api.detail<DemoMediaState>('/demo-r2/presentation-media')
    state.value = result
    for (const slot of orderedSlots) form[slot] = result.assignments[slot] || ''
  } catch {
    errorMessage.value = '无法读取演示媒体槽位。请确认当前为Demo R2实例且账号具有媒体权限。'
  } finally {
    loading.value = false
  }
}

/** 保存变化槽位；后端再次校验媒体类型、CSRF和并发令牌。 */
async function save(): Promise<void> {
  if (!state.value || !hasChanges.value) return
  saving.value = true
  message.value = ''
  errorMessage.value = ''
  const assignments = Object.fromEntries(
    orderedSlots
      .filter((slot) => (form[slot] || null) !== (state.value?.assignments[slot] || null))
      .map((slot) => [slot, form[slot] || null]),
  )
  try {
    state.value = await api.replace<DemoMediaState>('/demo-r2/presentation-media', {
      expected_token: state.value.token,
      assignments,
    })
    for (const slot of orderedSlots) form[slot] = state.value.assignments[slot] || ''
    message.value = '媒体槽位已保存并从数据库重新回读。刷新首页即可看到变化。'
  } catch {
    errorMessage.value = '保存失败：媒体可能已被其他编辑修改，请刷新后重试。'
  } finally {
    saving.value = false
  }
}

useHead({
  title: '演示媒体 · Junhui Admin',
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})
onMounted(load)
</script>

<template>
  <main class="admin-shell demo-media-page">
    <header class="demo-media-heading">
      <div>
        <p>DEMO R2 · PRESENTATION MEDIA</p>
        <h1>首页媒体与视频槽位</h1>
        <span>选择项来自真实媒体库；文件ID只在请求内部使用，不需要人工复制。</span>
      </div>
      <div>
        <NuxtLink to="/media">打开媒体资源库</NuxtLink>
        <button type="button" :disabled="saving || !hasChanges" @click="save">
          {{ saving ? '正在保存…' : '保存并应用' }}
        </button>
      </div>
    </header>

    <p v-if="message" class="demo-media-message" role="status">{{ message }}</p>
    <p v-if="errorMessage" class="error-message" role="alert">{{ errorMessage }}</p>
    <p v-if="loading" class="demo-media-loading">正在读取媒体库与当前配置…</p>

    <section v-else-if="state" class="demo-media-grid">
      <article v-for="slot in orderedSlots" :key="slot" class="demo-media-card">
        <header>
          <span>{{ slot.toUpperCase() }}</span>
          <div>
            <h2>{{ slotMeta(slot).title }}</h2>
            <p>{{ slotMeta(slot).note }}</p>
          </div>
        </header>
        <div class="demo-media-preview">
          <img
            v-if="selectedAsset(slot)?.media_type === 'image'"
            :src="selectedAsset(slot)?.preview_url"
            :alt="selectedAsset(slot)?.alt['zh-CN'] || selectedAsset(slot)?.filename"
          />
          <video
            v-else-if="selectedAsset(slot)?.media_type === 'video'"
            controls
            preload="metadata"
          >
            <source
              :src="selectedAsset(slot)?.preview_url"
              :type="selectedAsset(slot)?.mime_type"
            />
          </video>
          <p v-else>尚未选择可预览媒体</p>
        </div>
        <label>
          媒体文件
          <select v-model="form[slot]" :required="slotMeta(slot).required">
            <option v-if="!slotMeta(slot).required" value="">不使用封面</option>
            <option v-for="asset in optionsFor(slot)" :key="asset.id" :value="asset.id">
              {{ asset.filename }}
            </option>
          </select>
        </label>
        <dl v-if="selectedAsset(slot)">
          <div>
            <dt>类型</dt>
            <dd>{{ selectedAsset(slot)?.mime_type }}</dd>
          </div>
          <div v-if="selectedAsset(slot)?.duration_seconds">
            <dt>时长</dt>
            <dd>{{ selectedAsset(slot)?.duration_seconds }} 秒</dd>
          </div>
          <div v-else>
            <dt>尺寸</dt>
            <dd>{{ selectedAsset(slot)?.width }} × {{ selectedAsset(slot)?.height }}</dd>
          </div>
        </dl>
      </article>
    </section>
  </main>
</template>

<style scoped>
.demo-media-page {
  display: grid;
  align-content: start;
  gap: 1.1rem;
}
.demo-media-heading {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 1.5rem;
}
.demo-media-heading p {
  margin: 0;
  color: #0f70c9;
  font-size: 0.65rem;
  font-weight: 850;
  letter-spacing: 0.13em;
}
.demo-media-heading h1 {
  margin: 0.35rem 0;
  font-size: clamp(1.5rem, 3vw, 2.25rem);
  letter-spacing: -0.04em;
}
.demo-media-heading span {
  color: #687a8e;
}
.demo-media-heading > div:last-child {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}
.demo-media-heading a {
  padding: 0.62rem 0.85rem;
  color: #0d65ae;
  background: #fff;
  border: 1px solid #bed0df;
  border-radius: 0.5rem;
  font-size: 0.76rem;
  font-weight: 750;
  text-decoration: none;
}
.demo-media-message {
  margin: 0;
  padding: 0.75rem 1rem;
  color: #0e694c;
  background: #e9f8f2;
  border: 1px solid #b9e6d5;
  border-radius: 0.6rem;
}
.demo-media-loading {
  color: #66788c;
}
.demo-media-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}
.demo-media-card {
  min-width: 0;
  padding: 1rem;
  display: grid;
  align-content: start;
  gap: 0.9rem;
  background: #fff;
  border: 1px solid #dce4ec;
  border-radius: 0.85rem;
  box-shadow: 0 0.6rem 1.6rem rgb(20 46 73 / 5%);
}
.demo-media-card:first-child {
  grid-column: 1 / -1;
  grid-template-columns: minmax(16rem, 0.9fr) minmax(18rem, 1.1fr);
}
.demo-media-card:first-child > header,
.demo-media-card:first-child > label,
.demo-media-card:first-child > dl {
  grid-column: 2;
}
.demo-media-card:first-child > .demo-media-preview {
  grid-column: 1;
  grid-row: 1 / 5;
}
.demo-media-card > header {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.7rem;
}
.demo-media-card > header > span {
  width: 2.4rem;
  height: 1.65rem;
  display: grid;
  place-items: center;
  color: #0b67b3;
  background: #e9f5fd;
  border-radius: 0.35rem;
  font-size: 0.55rem;
  font-weight: 850;
}
.demo-media-card h2 {
  margin: 0;
  font-size: 1rem;
}
.demo-media-card header p {
  margin: 0.22rem 0 0;
  color: #748598;
  font-size: 0.72rem;
}
.demo-media-preview {
  min-height: 13rem;
  display: grid;
  place-items: center;
  overflow: hidden;
  color: #8a9aab;
  background: #07192c;
  border-radius: 0.6rem;
}
.demo-media-preview img,
.demo-media-preview video {
  width: 100%;
  aspect-ratio: 16 / 9;
  display: block;
  object-fit: cover;
}
.demo-media-card label {
  display: grid;
  gap: 0.4rem;
  color: #43566a;
  font-size: 0.72rem;
  font-weight: 750;
}
.demo-media-card dl {
  margin: 0;
  padding-top: 0.7rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.8rem;
  border-top: 1px solid #e2e9ef;
}
.demo-media-card dl > div {
  display: flex;
  gap: 0.35rem;
  color: #718296;
  font-size: 0.68rem;
}
.demo-media-card dt,
.demo-media-card dd {
  margin: 0;
}
.demo-media-card dd {
  color: #344a60;
  font-weight: 750;
}
@media (max-width: 60rem) {
  .demo-media-card:first-child {
    grid-template-columns: 1fr;
  }
  .demo-media-card:first-child > header,
  .demo-media-card:first-child > label,
  .demo-media-card:first-child > dl,
  .demo-media-card:first-child > .demo-media-preview {
    grid-column: 1;
    grid-row: auto;
  }
}
@media (max-width: 44rem) {
  .demo-media-heading {
    align-items: stretch;
    flex-direction: column;
  }
  .demo-media-heading > div:last-child {
    align-items: stretch;
    flex-direction: column;
  }
  .demo-media-grid {
    grid-template-columns: 1fr;
  }
  .demo-media-card:first-child {
    grid-column: 1;
  }
}
</style>
