<!-- 页面用途：询盘中心，以服务端搜索、筛选和分页管理真实询盘。 -->
<script setup lang="ts">
import { RFQ_STATUS_LABELS, formatBeijingTime, labelFrom } from '~/utils/adminZhCn'

interface RfqItem {
  id: string
  public_reference: string
  company_name: string
  contact_name: string
  email: string
  status: string
  assigned_to: string | null
  created_at: string
}
interface UserItem {
  id: string
  email: string
  display_name: string | null
  is_active: boolean
}

useHead({
  title: '询盘中心',
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})
const api = useAuthorityApi()
const items = ref<RfqItem[]>([])
const users = ref<UserItem[]>([])
const loading = ref(true)
const errorMessage = ref('')
const query = ref('')
const status = ref('')
const assignedTo = ref('')
const createdFrom = ref('')
const createdTo = ref('')
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
let requestVersion = 0

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const hasFilters = computed(() =>
  Boolean(query.value || status.value || assignedTo.value || createdFrom.value || createdTo.value),
)

/** 输入用户ID；输出可读姓名，邮箱仅作为没有姓名时的辅助标识。 */
function userLabel(userId: string | null): string {
  if (!userId) return '未分配'
  const user = users.value.find((item) => item.id === userId)
  return user?.display_name || user?.email || '账号已不可用'
}

/** 按当前筛选条件读取真实询盘；输入无，输出 Promise<void>。 */
async function load(): Promise<void> {
  const currentRequest = ++requestVersion
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await api.list<RfqItem>('/rfqs', {
      page: page.value,
      page_size: pageSize.value,
      q: query.value.trim() || undefined,
      status: status.value || undefined,
      assigned_to: assignedTo.value || undefined,
      created_from: createdFrom.value ? `${createdFrom.value}T00:00:00+08:00` : undefined,
      created_to: createdTo.value ? `${createdTo.value}T23:59:59+08:00` : undefined,
    })
    if (currentRequest !== requestVersion) return
    items.value = result.items
    total.value = result.total
  } catch (error) {
    if (currentRequest !== requestVersion) return
    errorMessage.value = error instanceof Error ? error.message : '无法读取询盘。'
  } finally {
    if (currentRequest === requestVersion) loading.value = false
  }
}

/** 应用筛选并返回第一页。 */
async function applyFilters(): Promise<void> {
  page.value = 1
  await load()
}

/** 清空所有筛选并重新读取。 */
async function clearFilters(): Promise<void> {
  query.value = ''
  status.value = ''
  assignedTo.value = ''
  createdFrom.value = ''
  createdTo.value = ''
  page.value = 1
  await load()
}

/** 切换分页并读取目标页。 */
async function goToPage(nextPage: number): Promise<void> {
  page.value = Math.min(Math.max(1, nextPage), totalPages.value)
  await load()
}

onMounted(async () => {
  try {
    users.value = await api.detail<UserItem[]>('/users')
  } catch {
    users.value = []
  }
  await load()
})
</script>

<template>
  <main class="admin-shell rfq-page">
    <header class="page-heading">
      <div>
        <p>销售工作台</p>
        <h1>询盘中心</h1>
        <span>按客户、编号、联系人或邮箱搜索，时间统一显示为北京时间。</span>
      </div>
      <strong>{{ total }} 条询盘</strong>
    </header>

    <form class="filter-panel" @submit.prevent="applyFilters">
      <label
        >搜索<input v-model="query" type="search" placeholder="公司、编号、联系人或邮箱"
      /></label>
      <label
        >询盘状态<select v-model="status">
          <option value="">全部状态</option>
          <option v-for="(label, code) in RFQ_STATUS_LABELS" :key="code" :value="code">
            {{ label }}
          </option>
        </select></label
      >
      <label
        >负责人<select v-model="assignedTo">
          <option value="">全部负责人</option>
          <option v-for="user in users" :key="user.id" :value="user.id">
            {{ user.display_name || user.email }}
          </option>
        </select></label
      >
      <label>开始日期<input v-model="createdFrom" type="date" /></label>
      <label>结束日期<input v-model="createdTo" type="date" /></label>
      <div class="filter-actions">
        <button type="submit">应用筛选</button
        ><button type="button" class="secondary" @click="clearFilters">清空筛选</button>
      </div>
    </form>

    <p v-if="loading" role="status">正在读取询盘…</p>
    <p v-else-if="errorMessage" class="error-message" role="alert">
      {{ errorMessage }}
    </p>
    <section v-else-if="items.length" class="table-card" aria-label="询盘列表">
      <table>
        <thead>
          <tr>
            <th>询盘编号</th>
            <th>公司与联系人</th>
            <th>状态</th>
            <th>负责人</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.id">
            <td>
              <strong>{{ item.public_reference }}</strong
              ><small>{{ item.email }}</small>
            </td>
            <td>
              <strong>{{ item.company_name || '未填写公司' }}</strong
              ><small>{{ item.contact_name || '未填写联系人' }}</small>
            </td>
            <td>
              <span class="status-chip">{{ labelFrom(RFQ_STATUS_LABELS, item.status) }}</span>
            </td>
            <td>{{ userLabel(item.assigned_to) }}</td>
            <td>{{ formatBeijingTime(item.created_at) }}</td>
            <td><NuxtLink :to="`/rfqs/${item.id}`">查看详情</NuxtLink></td>
          </tr>
        </tbody>
      </table>
    </section>
    <section v-else class="empty-state">
      <h2>{{ hasFilters ? '没有符合筛选条件的询盘' : '暂无询盘' }}</h2>
      <p>
        {{ hasFilters ? '请调整条件或清空筛选。' : '新询盘出现后会显示在这里。' }}
      </p>
    </section>

    <nav class="pagination" aria-label="询盘分页">
      <button type="button" :disabled="loading || page <= 1" @click="goToPage(page - 1)">
        上一页
      </button>
      <span>第 {{ page }} / {{ totalPages }} 页</span>
      <button type="button" :disabled="loading || page >= totalPages" @click="goToPage(page + 1)">
        下一页
      </button>
    </nav>
  </main>
</template>

<style scoped>
.rfq-page {
  display: grid;
  gap: 1rem;
  align-content: start;
}
.page-heading {
  display: flex;
  justify-content: space-between;
  align-items: end;
  gap: 1rem;
}
.page-heading p,
.page-heading h1 {
  margin: 0;
}
.page-heading p {
  color: #0f70c9;
  font-size: 0.7rem;
  font-weight: 800;
  letter-spacing: 0.12em;
}
.page-heading span {
  color: #6f8092;
}
.filter-panel {
  padding: 1rem;
  display: grid;
  grid-template-columns: 1.4fr repeat(4, minmax(8rem, 1fr));
  gap: 0.7rem;
  background: #fff;
  border: 1px solid #dfe7ee;
  border-radius: 0.75rem;
}
.filter-panel label {
  display: grid;
  gap: 0.35rem;
  color: #40566c;
  font-size: 0.76rem;
}
.filter-actions {
  grid-column: 1 / -1;
  display: flex;
  gap: 0.5rem;
}
.secondary {
  color: #29465f;
  background: #eef3f7;
}
.table-card {
  overflow-x: auto;
  background: #fff;
  border: 1px solid #dfe7ee;
  border-radius: 0.75rem;
}
table {
  width: 100%;
  border-collapse: collapse;
}
th,
td {
  padding: 0.8rem;
  text-align: left;
  border-bottom: 1px solid #e8eef3;
}
td strong,
td small {
  display: block;
}
td small {
  margin-top: 0.25rem;
  color: #788a9b;
}
.status-chip {
  padding: 0.25rem 0.5rem;
  color: #0b5f9c;
  background: #e7f4fc;
  border-radius: 999px;
  white-space: nowrap;
}
.empty-state {
  padding: 2.5rem;
  text-align: center;
  background: #fff;
  border: 1px dashed #cbd8e3;
  border-radius: 0.75rem;
}
.empty-state h2 {
  margin: 0;
  font-size: 1rem;
}
.pagination {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 0.7rem;
}
@media (max-width: 64rem) {
  .filter-panel {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
