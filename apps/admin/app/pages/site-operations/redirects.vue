<!-- 页面用途：读取、搜索并按“草稿—检查—确认”流程管理精确路径重定向。 -->
<script setup lang="ts">
interface RedirectItem {
  id: string
  source_host: string
  source_path: string
  target_url: string
  target_path: string
  status_code: 301 | 302 | 307 | 308
  notes: string | null
  workflow_status: 'draft' | 'checked' | 'confirmed'
  revision: number
  checked_revision: number | null
  enabled: boolean
  hit_count: number
  last_hit_at: string | null
  confirmed_at: string | null
  updated_at: string
}
interface RedirectList {
  items: RedirectItem[]
  source_hosts: string[]
  official_target_origin: string
}
interface HistoryItem {
  action: string
  metadata: Record<string, unknown>
  created_at: string
}

const api = useAuthorityApi()
const { currentUser } = useAuth()
const list = ref<RedirectList>({
  items: [],
  source_hosts: [],
  official_target_origin: 'https://junhuiscrewbarrel.com',
})
const query = ref('')
const selectedId = ref<string | null>(null)
const form = reactive({
  source_host: 'junhuiscrew.com',
  source_path: '',
  target_path: '',
  status_code: 301 as 301 | 302 | 307 | 308,
  notes: '',
})
const history = ref<HistoryItem[]>([])
const loading = ref(true)
const busy = ref(false)
const message = ref('')
const errorMessage = ref('')
const canManage = computed(
  () => currentUser.value?.permissions.includes('redirect.manage') ?? false,
)
const selected = computed(
  () => list.value.items.find((item) => item.id === selectedId.value) ?? null,
)
const redirectActionLabels: Record<string, string> = {
  'redirect.draft.create': '新建草稿',
  'redirect.draft.update': '更新草稿',
  'redirect.check': '完成检查',
  'redirect.confirm': '确认启用',
  'redirect.disable': '停用规则',
}

useHead({
  title: '重定向管理 · 骏辉内容运营后台',
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})

/** 输入重定向审计动作代码；输出员工可读的中文主文案，未知代码保持可识别。 */
function redirectActionLabel(action: string): string {
  return redirectActionLabels[action] ?? '其他操作'
}

/** 输入可选选中规则；输出无，把可读字段装入表单，不要求员工输入内部标识或 JSON。 */
function fillForm(item: RedirectItem | null): void {
  form.source_host = item?.source_host ?? list.value.source_hosts[0] ?? 'junhuiscrew.com'
  form.source_path = item?.source_path ?? ''
  form.target_path = item?.target_path ?? ''
  form.status_code = item?.status_code ?? 301
  form.notes = item?.notes ?? ''
}

/** 读取实际规则和主机白名单；搜索仅在数据库字段内执行。 */
async function loadRedirects(preserveSelection = true): Promise<void> {
  loading.value = true
  try {
    list.value = await api.request<RedirectList>('/site-operations/redirects', {
      query: { query: query.value || null },
    })
    if (!preserveSelection || !list.value.items.some((item) => item.id === selectedId.value)) {
      selectedId.value = null
      fillForm(null)
      history.value = []
    } else fillForm(selected.value)
  } catch {
    errorMessage.value = '读取重定向规则失败，请检查登录与读取权限。'
  } finally {
    loading.value = false
  }
}

/** 输入列表记录；输出无，选择规则并读取其脱敏变更历史。 */
async function selectRule(item: RedirectItem): Promise<void> {
  selectedId.value = item.id
  fillForm(item)
  history.value = await api.detail<HistoryItem[]>(`/site-operations/redirects/${item.id}/history`)
}

/** 重置为新增表单，来源主机仍只能从服务端允许名单选择。 */
function startCreate(): void {
  selectedId.value = null
  history.value = []
  fillForm(null)
  message.value = '正在新建停用草稿。'
}

/** 保存新草稿或更新现有草稿，默认不启用。 */
async function saveDraft(): Promise<void> {
  if (!canManage.value) return
  busy.value = true
  errorMessage.value = ''
  const body = { ...form, notes: form.notes.trim() || null }
  try {
    const item = selected.value
      ? await api.update<RedirectItem>(`/site-operations/redirects/${selected.value.id}`, {
          ...body,
          expected_revision: selected.value.revision,
        })
      : await api.create<RedirectItem>('/site-operations/redirects', body)
    selectedId.value = item.id
    await loadRedirects(true)
    if (selected.value) await selectRule(selected.value)
    message.value = `草稿已保存并重新读取，revision ${item.revision}；当前未启用。`
  } catch {
    errorMessage.value = '保存被拒绝：请检查保护路径、重复、循环、跳转链、协议或版本冲突。'
  } finally {
    busy.value = false
  }
}

/** 对当前修订做数据库与路由冲突检查，不请求目标网站。 */
async function checkRule(): Promise<void> {
  if (!selected.value || !canManage.value) return
  try {
    await api.create(`/site-operations/redirects/${selected.value.id}/check`, {
      expected_revision: selected.value.revision,
    })
    await loadRedirects(true)
    if (selected.value) await selectRule(selected.value)
    message.value = '当前修订已通过本地冲突检查；检查过程未访问外网。'
  } catch {
    errorMessage.value = '检查未通过，请处理冲突后重新保存。'
  }
}

/** 经明确确认后启用已检查的同一修订。 */
async function confirmRule(): Promise<void> {
  if (!selected.value || !canManage.value || !window.confirm('确认启用当前已检查的重定向规则吗？'))
    return
  try {
    await api.create(`/site-operations/redirects/${selected.value.id}/confirm`, {
      expected_revision: selected.value.revision,
    })
    await loadRedirects(true)
    if (selected.value) await selectRule(selected.value)
    message.value = '规则已确认启用，可通过真实 HTTP 3xx 接口验证。'
  } catch {
    errorMessage.value = '确认失败：必须先检查当前修订，且不能存在新的冲突。'
  }
}

/** 停用实际规则但保留记录和全部审计历史。 */
async function disableRule(): Promise<void> {
  if (!selected.value || !canManage.value || !window.confirm('确认停用这条重定向吗？')) return
  await api.create(`/site-operations/redirects/${selected.value.id}/disable`, {
    expected_revision: selected.value.revision,
  })
  await loadRedirects(true)
  if (selected.value) await selectRule(selected.value)
  message.value = '规则已停用，历史仍保留。'
}

onMounted(() => loadRedirects(false))
</script>

<template>
  <main class="redirect-page" data-testid="site-redirect-manager">
    <header class="redirect-hero">
      <div>
        <p>站点运营设置 R1</p>
        <h1>受控重定向管理</h1>
        <span>规则必须保存草稿、完成本地冲突检查，再由有权限人员确认启用。</span>
      </div>
      <button :disabled="!canManage" @click="startCreate">新增规则</button>
    </header>
    <section class="search-bar">
      <label
        >搜索现有规则<input
          v-model="query"
          maxlength="120"
          placeholder="来源路径、目标或备注"
          @keyup.enter="loadRedirects(false)" /></label
      ><button @click="loadRedirects(false)">搜索</button>
    </section>
    <div class="redirect-grid">
      <section class="rule-list">
        <p v-if="loading">正在读取…</p>
        <button
          v-for="item in list.items"
          :key="item.id"
          :class="{ active: selectedId === item.id }"
          @click="selectRule(item)"
        >
          <strong class="rule-source">{{ item.source_host }}{{ item.source_path }}</strong
          ><span>→ {{ item.target_url }}</span
          ><small
            >{{
              item.enabled
                ? '已启用'
                : item.workflow_status === 'checked'
                  ? '已检查待确认'
                  : '停用 / 草稿'
            }}
            · {{ item.status_code }} · 命中 {{ item.hit_count }}</small
          >
        </button>
        <p v-if="!loading && !list.items.length">没有匹配规则。</p>
      </section>
      <section class="editor-card">
        <header>
          <div>
            <h2>{{ selected ? '修改规则' : '新增规则' }}</h2>
            <p>员工只需选择主机并填写路径。</p>
          </div>
          <span v-if="selected">revision {{ selected.revision }}</span>
        </header>
        <label
          >来源主机<select v-model="form.source_host" :disabled="!canManage">
            <option v-for="host in list.source_hosts" :key="host">{{ host }}</option>
          </select></label
        >
        <label
          >来源精确路径<input
            v-model="form.source_path"
            placeholder="/legacy-product/"
            :disabled="!canManage"
        /></label>
        <label
          >目标路径
          <div class="target-input">
            <span>{{ list.official_target_origin }}</span
            ><input
              v-model="form.target_path"
              placeholder="/en/products/"
              :disabled="!canManage"
            /></div
        ></label>
        <label
          >HTTP 状态<select v-model="form.status_code" :disabled="!canManage">
            <option :value="301">301 永久</option>
            <option :value="308">308 永久</option>
            <option :value="302">302 临时</option>
            <option :value="307">307 临时</option>
          </select></label
        >
        <label
          >内部备注<textarea
            v-model="form.notes"
            rows="3"
            maxlength="2000"
            :disabled="!canManage"
          />
        </label>
        <div class="workflow-actions">
          <button :disabled="busy || !canManage" @click="saveDraft">保存草稿</button
          ><button :disabled="!selected || !canManage" @click="checkRule">检查跳转</button
          ><button
            :disabled="!selected || selected.workflow_status !== 'checked' || !canManage"
            @click="confirmRule"
          >
            确认启用</button
          ><button :disabled="!selected?.enabled || !canManage" @click="disableRule">停用</button>
        </div>
        <p class="guard-note">
          检查不会抓取外网；首页、后台、API、媒体、Privacy、RFQ 和现有有效内容路径均受保护。
        </p>
      </section>
      <aside class="history-card">
        <h2>变更历史</h2>
        <ol>
          <li v-for="event in history" :key="`${event.action}:${event.created_at}`">
            <strong>{{ redirectActionLabel(event.action) }}</strong
            ><span>{{ new Date(event.created_at).toLocaleString('zh-CN') }}</span
            ><small
              >技术代码：{{ event.action }} · revision {{ event.metadata.revision ?? '—' }}</small
            >
          </li>
        </ol>
        <p v-if="selected && !history.length">暂无历史。</p>
        <p v-if="!selected">选择规则后查看。</p>
      </aside>
    </div>
    <p v-if="message" class="notice" role="status">{{ message }}</p>
    <p v-if="errorMessage" class="error" role="alert">{{ errorMessage }}</p>
  </main>
</template>

<style scoped>
.redirect-page {
  width: min(calc(100% - 2rem), 96rem);
  margin: auto;
  padding: 2rem 0 5rem;
}
.redirect-hero,
.search-bar,
.editor-card > header,
.workflow-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}
.redirect-hero {
  padding: 1.4rem;
  color: #fff;
  background: linear-gradient(120deg, #07182b, #0f5791);
  border-radius: 1rem;
}
.redirect-hero p,
.redirect-hero h1 {
  margin: 0.2rem 0;
}
.redirect-hero span {
  color: #c8def0;
}
.redirect-hero button {
  color: #12304a;
  background: #fff;
}
.search-bar {
  margin: 1rem 0;
  padding: 1rem;
  background: #fff;
  border: 1px solid #dce4ec;
  border-radius: 0.75rem;
}
.search-bar label {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  flex: 1;
}
.search-bar input {
  flex: 1;
}
.redirect-grid {
  display: grid;
  grid-template-columns: minmax(17rem, 0.85fr) minmax(26rem, 1.5fr) minmax(15rem, 0.7fr);
  gap: 1rem;
}
.rule-list,
.editor-card,
.history-card {
  padding: 1rem;
  background: #fff;
  border: 1px solid #dce4ec;
  border-radius: 0.85rem;
}
.rule-list {
  display: grid;
  align-content: start;
  gap: 0.5rem;
}
.rule-list > button {
  display: grid;
  gap: 0.28rem;
  color: #17324a;
  text-align: left;
  background: #f5f8fa;
}
.rule-source {
  overflow-wrap: anywhere;
  color: #17324a;
}
.rule-list > button.active {
  outline: 2px solid #0f70c9;
}
.rule-list span,
.rule-list small {
  overflow-wrap: anywhere;
  color: #607186;
}
.editor-card label {
  display: grid;
  gap: 0.35rem;
  margin: 0.8rem 0;
  font-weight: 700;
}
input,
select,
textarea {
  width: 100%;
  padding: 0.68rem;
  border: 1px solid #b9c7d4;
  border-radius: 0.45rem;
}
.target-input {
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  border: 1px solid #b9c7d4;
  border-radius: 0.45rem;
  overflow: hidden;
}
.target-input span {
  padding: 0.68rem;
  background: #edf3f7;
}
.target-input input {
  border: 0;
}
.workflow-actions {
  justify-content: flex-start;
  flex-wrap: wrap;
}
.workflow-actions button:first-child,
.workflow-actions button:nth-child(3) {
  color: #fff;
  background: #0f70c9;
}
.guard-note {
  padding: 0.7rem;
  color: #5c4a18;
  background: #fff8dd;
}
.history-card ol {
  padding-left: 1.2rem;
}
.history-card li {
  display: grid;
  gap: 0.2rem;
  margin: 0.8rem 0;
}
.history-card span,
.history-card small {
  color: #607186;
}
button {
  padding: 0.65rem 0.85rem;
  border: 0;
  border-radius: 0.45rem;
  cursor: pointer;
}
.notice,
.error {
  padding: 0.8rem 1rem;
}
.notice {
  color: #075b42;
  background: #e4f6ef;
}
.error {
  color: #8d2118;
  background: #feecea;
}
@media (max-width: 75rem) {
  .redirect-grid {
    grid-template-columns: 1fr 1.5fr;
  }
  .history-card {
    grid-column: 1/-1;
  }
}
@media (max-width: 50rem) {
  .redirect-grid {
    grid-template-columns: 1fr;
  }
  .redirect-hero,
  .search-bar {
    align-items: flex-start;
    flex-direction: column;
  }
  .search-bar label {
    width: 100%;
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
