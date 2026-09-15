<!-- 页面用途：可视化维护顶部、移动菜单和页脚分组的双语标签、顺序及启停。 -->
<script setup lang="ts">
interface MenuItem {
  id: string
  label: string
  target_key: string
  enabled: boolean
}
interface FooterGroup {
  id: string
  title: string
  enabled: boolean
  items: MenuItem[]
}
interface NavigationConfig {
  header_items: MenuItem[]
  footer_groups: FooterGroup[]
}
interface TargetOption {
  key: string
  label: string
  path: string
  available: boolean
  reason: string | null
}
interface NavigationDetail {
  locale: { code: string; slug: string; native_name: string }
  draft: NavigationConfig
  applied: NavigationConfig
  draft_revision: number
  applied_revision: number
  applied_at: string | null
  target_options: TargetOption[]
}

const api = useAuthorityApi()
const { currentUser } = useAuth()
const activeLocale = ref<'zh-CN' | 'en'>('zh-CN')
const detail = ref<NavigationDetail | null>(null)
const draft = ref<NavigationConfig>({ header_items: [], footer_groups: [] })
const preview = ref<NavigationConfig | null>(null)
const loading = ref(true)
const busy = ref(false)
const message = ref('')
const errorMessage = ref('')
const canEdit = computed(() => currentUser.value?.permissions.includes('content.update') ?? false)
const canApply = computed(() => currentUser.value?.permissions.includes('content.publish') ?? false)
const targetOptions = computed(() => detail.value?.target_options ?? [])
const availableTargets = computed(() => targetOptions.value.filter((item) => item.available))

useHead({
  title: '导航与页脚 · 骏辉内容运营后台',
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})

/** 输入服务端配置；输出独立深拷贝，避免未保存编辑污染回读对象。 */
function cloneConfig(value: NavigationConfig): NavigationConfig {
  return {
    header_items: value.header_items.map((item) => ({ ...item })),
    footer_groups: value.footer_groups.map((group) => ({
      ...group,
      items: group.items.map((item) => ({ ...item })),
    })),
  }
}

/** 读取当前语言真实草稿、应用版和服务端认可目标。 */
async function loadNavigation(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    detail.value = await api.detail<NavigationDetail>(
      `/site-operations/navigation/${activeLocale.value}`,
    )
    draft.value = cloneConfig(detail.value.draft)
  } catch {
    detail.value = null
    errorMessage.value = '导航设置尚未建立，或当前账号没有读取权限。'
  } finally {
    loading.value = false
  }
}

/** 幂等初始化当前导航等值配置，不覆盖数据库中已有草稿。 */
async function initializeSettings(): Promise<void> {
  await api.create('/site-operations/initialize', {})
  await loadNavigation()
  message.value = '已建立等值初始配置并重新读取。'
}

/** 输入数组、当前下标与方向；输出无，只调整本地草稿排序。 */
function moveItem<T>(items: T[], index: number, direction: -1 | 1): void {
  const destination = index + direction
  if (destination < 0 || destination >= items.length) return
  const [item] = items.splice(index, 1)
  if (item) items.splice(destination, 0, item)
}

/** 生成后台内部稳定标识，不参与前台路径解析。 */
function newItemId(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}`
}

/** 在顶部菜单末尾增加一个服务端白名单目标。 */
function addHeaderItem(): void {
  const option = availableTargets.value.find(
    (item) => !draft.value.header_items.some((current) => current.target_key === item.key),
  )
  if (!option) return
  draft.value.header_items.push({
    id: newItemId('header'),
    label: option.label,
    target_key: option.key,
    enabled: true,
  })
}

/** 新增空页脚分组，后续只能从白名单目标下拉框添加项目。 */
function addFooterGroup(): void {
  draft.value.footer_groups.push({
    id: newItemId('group'),
    title: activeLocale.value === 'zh-CN' ? '新分组' : 'New group',
    enabled: true,
    items: [],
  })
}

/** 输入页脚分组；输出无，在该分组增加第一个尚未使用的目标。 */
function addFooterItem(group: FooterGroup): void {
  const option = availableTargets.value.find(
    (item) => !group.items.some((current) => current.target_key === item.key),
  )
  if (!option) return
  group.items.push({
    id: newItemId('footer'),
    label: option.label,
    target_key: option.key,
    enabled: true,
  })
}

/** 输入菜单项；输出无，在选择目标变化时填入当前语言默认标签，仍可人工修改。 */
function syncDefaultLabel(item: MenuItem): void {
  const option = detail.value?.target_options.find((candidate) => candidate.key === item.target_key)
  if (option) item.label = option.label
}

/** 输入目标选项；输出带当前公开资格提示的员工可读标签。 */
function targetOptionLabel(option: TargetOption): string {
  return `${option.label} · ${option.path}${option.available ? '' : ' · 当前不可公开'}`
}

/** 保存当前语言完整草稿；接口不会写入另一语言记录。 */
async function saveDraft(): Promise<void> {
  if (!detail.value || !canEdit.value) return
  busy.value = true
  errorMessage.value = ''
  try {
    detail.value = await api.update<NavigationDetail>(
      `/site-operations/navigation/${activeLocale.value}/draft`,
      {
        expected_revision: detail.value.draft_revision,
        ...cloneConfig(draft.value),
      },
    )
    draft.value = cloneConfig(detail.value.draft)
    message.value = `当前语言草稿已保存并 fresh GET 回读，revision ${detail.value.draft_revision}；另一语言未改。`
  } catch {
    errorMessage.value = '保存失败：请检查重复标识、目标可用性或版本冲突。'
  } finally {
    busy.value = false
  }
}

/** 从认证服务端预览接口读取已保存草稿。 */
async function loadPreview(): Promise<void> {
  try {
    const result = await api.detail<{ navigation: NavigationConfig }>(
      `/site-operations/navigation/${activeLocale.value}/preview`,
    )
    preview.value = cloneConfig(result.navigation)
    message.value = '认证导航预览已重新读取。'
  } catch {
    errorMessage.value = '认证预览失败，请先保存草稿。'
  }
}

/** 确认把当前语言已保存草稿应用到桌面、移动菜单和页脚。 */
async function applyDraft(): Promise<void> {
  if (
    !detail.value ||
    !canApply.value ||
    !window.confirm(`确认应用${activeLocale.value === 'zh-CN' ? '中文' : '英文'}导航草稿吗？`)
  )
    return
  detail.value = await api.create<NavigationDetail>(
    `/site-operations/navigation/${activeLocale.value}/apply`,
    { expected_revision: detail.value.draft_revision },
  )
  draft.value = cloneConfig(detail.value.draft)
  message.value = '当前语言导航已确认应用并重新读取。'
}

/** 从当前语言应用版生成新草稿，审计历史不删除。 */
async function restoreDraft(): Promise<void> {
  if (!detail.value || !canEdit.value || !window.confirm('确认从应用版恢复出一个新草稿吗？')) return
  detail.value = await api.create<NavigationDetail>(
    `/site-operations/navigation/${activeLocale.value}/restore`,
    { expected_revision: detail.value.draft_revision },
  )
  draft.value = cloneConfig(detail.value.draft)
  message.value = '已从应用版恢复草稿；普通前台未改变。'
}

watch(activeLocale, () => {
  preview.value = null
  message.value = ''
  loadNavigation()
})
onMounted(loadNavigation)
</script>

<template>
  <main class="operations-page" data-testid="site-navigation-editor">
    <header class="operations-hero">
      <div>
        <p>站点运营设置 R1</p>
        <h1>导航与页脚</h1>
        <span>新增或移除只改变菜单项，不删除任何内容；目标只能从安全站内页面中选择。</span>
      </div>
    </header>
    <div class="locale-tabs">
      <button
        v-for="locale in ['zh-CN', 'en'] as const"
        :key="locale"
        :class="{ active: activeLocale === locale }"
        :aria-pressed="activeLocale === locale"
        :data-testid="`site-navigation-locale-${locale}`"
        @click="activeLocale = locale"
      >
        {{ locale === 'zh-CN' ? '简体中文' : '英语' }}
      </button>
    </div>
    <p v-if="loading" class="operations-card">正在读取导航设置…</p>
    <section v-else-if="!detail" class="operations-card">
      <p role="alert">{{ errorMessage }}</p>
      <button v-if="canEdit" @click="initializeSettings">建立等值初始配置</button>
    </section>
    <template v-else>
      <section class="status-strip">
        <span>草稿 {{ detail.draft_revision }}</span
        ><span>应用版 {{ detail.applied_revision }}</span
        ><span>当前编辑：{{ detail.locale.native_name }}</span>
      </section>
      <div class="operations-grid">
        <section class="operations-card">
          <header class="section-heading">
            <div>
              <h2>顶部与移动菜单</h2>
              <p>两端共用同一应用版顺序。</p>
            </div>
            <button :disabled="!canEdit" @click="addHeaderItem">新增菜单项</button>
          </header>
          <article v-for="(item, index) in draft.header_items" :key="item.id" class="menu-row">
            <label>标签<input v-model="item.label" maxlength="80" :disabled="!canEdit" /></label>
            <label
              >站内目标<select
                v-model="item.target_key"
                :disabled="!canEdit"
                @change="syncDefaultLabel(item)"
              >
                <option
                  v-for="option in targetOptions"
                  :key="option.key"
                  :value="option.key"
                  :disabled="!option.available && option.key !== item.target_key"
                >
                  {{ targetOptionLabel(option) }}
                </option>
              </select></label
            >
            <label class="check"
              ><input v-model="item.enabled" type="checkbox" :disabled="!canEdit" />启用</label
            >
            <span class="row-actions"
              ><button
                :disabled="index === 0 || !canEdit"
                @click="moveItem(draft.header_items, index, -1)"
              >
                ↑</button
              ><button
                :disabled="index === draft.header_items.length - 1 || !canEdit"
                @click="moveItem(draft.header_items, index, 1)"
              >
                ↓</button
              ><button :disabled="!canEdit" @click="draft.header_items.splice(index, 1)">
                移除
              </button></span
            >
          </article>

          <header class="section-heading">
            <div>
              <h2>页脚分组</h2>
              <p>语言切换由系统维护，不在此处删除。</p>
            </div>
            <button :disabled="!canEdit" @click="addFooterGroup">新增分组</button>
          </header>
          <article
            v-for="(group, groupIndex) in draft.footer_groups"
            :key="group.id"
            class="footer-group"
          >
            <header>
              <input v-model="group.title" maxlength="80" :disabled="!canEdit" /><label
                class="check"
                ><input
                  v-model="group.enabled"
                  type="checkbox"
                  :disabled="!canEdit"
                />启用分组</label
              ><button :disabled="!canEdit" @click="draft.footer_groups.splice(groupIndex, 1)">
                移除分组
              </button>
            </header>
            <div v-for="(item, index) in group.items" :key="item.id" class="menu-row compact">
              <input v-model="item.label" maxlength="80" :disabled="!canEdit" /><select
                v-model="item.target_key"
                :disabled="!canEdit"
                @change="syncDefaultLabel(item)"
              >
                <option
                  v-for="option in targetOptions"
                  :key="option.key"
                  :value="option.key"
                  :disabled="!option.available && option.key !== item.target_key"
                >
                  {{ targetOptionLabel(option) }}
                </option></select
              ><label class="check"
                ><input v-model="item.enabled" type="checkbox" :disabled="!canEdit" />启用</label
              ><span class="row-actions"
                ><button :disabled="index === 0" @click="moveItem(group.items, index, -1)">↑</button
                ><button
                  :disabled="index === group.items.length - 1"
                  @click="moveItem(group.items, index, 1)"
                >
                  ↓</button
                ><button @click="group.items.splice(index, 1)">移除</button></span
              >
            </div>
            <button :disabled="!canEdit" @click="addFooterItem(group)">添加站内目标</button>
          </article>
        </section>
        <aside class="operations-card preview-card">
          <h2>认证草稿预览</h2>
          <template v-if="preview"
            ><strong>顶部 / 移动菜单</strong>
            <ol>
              <li v-for="item in preview.header_items.filter((i) => i.enabled)" :key="item.id">
                {{ item.label }}
              </li>
            </ol>
            <strong>页脚</strong>
            <section
              v-for="group in preview.footer_groups.filter((g) => g.enabled)"
              :key="group.id"
            >
              <b>{{ group.title }}</b
              ><span v-for="item in group.items.filter((i) => i.enabled)" :key="item.id">{{
                item.label
              }}</span>
            </section></template
          >
          <p v-else>先保存草稿，再点击认证预览。</p>
          <button @click="loadPreview">认证预览</button>
        </aside>
      </div>
      <footer class="operations-actions">
        <button :disabled="busy || !canEdit" @click="saveDraft">保存当前语言草稿</button
        ><button :disabled="busy || !canApply" @click="applyDraft">确认应用</button
        ><button :disabled="busy || !canEdit" @click="restoreDraft">从应用版恢复</button
        ><button @click="loadNavigation">重新读取</button>
      </footer>
      <p v-if="message" class="notice" role="status">{{ message }}</p>
      <p v-if="errorMessage" class="error" role="alert">{{ errorMessage }}</p>
    </template>
  </main>
</template>

<style scoped>
.operations-page {
  width: min(calc(100% - 2rem), 92rem);
  margin: auto;
  padding: 2rem 0 5rem;
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
.locale-tabs,
.status-strip,
.operations-actions,
.section-heading,
.footer-group > header,
.row-actions {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}
.locale-tabs {
  margin: 1rem 0;
}
.locale-tabs button {
  padding: 0.6rem 1rem;
  color: #17324a;
  border: 1px solid #cbd8e3;
  background: #fff;
}
.locale-tabs button:hover:not(.active) {
  color: #0a5b9f;
  background: #eef6fc;
  border-color: #7db7df;
}
.locale-tabs button:focus-visible {
  outline: 3px solid rgb(15 112 201 / 28%);
  outline-offset: 2px;
}
.locale-tabs button.active {
  color: #fff;
  background: #0f70c9;
  border-color: #0f70c9;
}
.status-strip {
  padding: 0.8rem 1rem;
  background: #e9f3fb;
  border-radius: 0.7rem;
}
.operations-grid {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(18rem, 1fr);
  gap: 1rem;
  margin-top: 1rem;
}
.operations-card {
  padding: 1.2rem;
  background: #fff;
  border: 1px solid #dce4ec;
  border-radius: 0.85rem;
}
.section-heading {
  justify-content: space-between;
  margin: 1rem 0;
}
.menu-row {
  display: grid;
  grid-template-columns: minmax(10rem, 1fr) minmax(16rem, 1.5fr) auto auto;
  align-items: end;
  gap: 0.7rem;
  padding: 0.8rem;
  border-top: 1px solid #e2e8ef;
}
.menu-row label {
  display: grid;
  gap: 0.3rem;
  font-weight: 700;
}
.menu-row input,
.menu-row select,
.footer-group > header > input {
  width: 100%;
  padding: 0.62rem;
  border: 1px solid #b9c7d4;
  border-radius: 0.45rem;
}
.check {
  display: flex !important;
  align-items: center;
  gap: 0.3rem;
}
.check input {
  width: auto;
}
.footer-group {
  margin: 1rem 0;
  padding: 1rem;
  background: #f7f9fb;
  border: 1px solid #dce4ec;
  border-radius: 0.7rem;
}
.footer-group > header {
  display: grid;
  grid-template-columns: 1fr auto auto;
}
.compact {
  grid-template-columns: 1fr 1.4fr auto auto;
  padding-inline: 0;
}
.preview-card {
  align-self: start;
  display: grid;
  gap: 0.8rem;
}
.preview-card section {
  display: grid;
  gap: 0.3rem;
  padding: 0.6rem;
  background: #f1f5f8;
}
.preview-card section span {
  color: #607186;
}
.operations-actions {
  margin-top: 1rem;
  flex-wrap: wrap;
}
button {
  padding: 0.62rem 0.85rem;
  border: 0;
  border-radius: 0.45rem;
  cursor: pointer;
}
.section-heading button,
.footer-group > button,
.operations-actions button:first-child,
.preview-card > button {
  color: #fff;
  background: #0f70c9;
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
@media (max-width: 68rem) {
  .operations-grid {
    grid-template-columns: 1fr;
  }
  .menu-row,
  .menu-row.compact {
    grid-template-columns: 1fr;
  }
  .footer-group > header {
    grid-template-columns: 1fr;
  }
}
</style>
