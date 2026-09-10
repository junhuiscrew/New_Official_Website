<!-- 页面用途：以中文字段展示询盘详情、项目、私有附件、分配、状态和审计记录。 -->
<script setup lang="ts">
import {
  RFQ_PRIORITY_LABELS,
  RFQ_STATUS_LABELS,
  formatBeijingTime,
  labelFrom,
} from '~/utils/adminZhCn'

interface UserItem {
  id: string
  email: string
  display_name: string | null
}
interface RfqDetail {
  rfq: Record<string, unknown>
  items: Array<Record<string, unknown>>
  files: Array<Record<string, unknown>>
  audit_logs: Array<Record<string, unknown>>
}

useHead({
  title: '询盘详情',
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})
const route = useRoute()
const api = useAuthorityApi()
const detail = ref<RfqDetail | null>(null)
const users = ref<UserItem[]>([])
const assignedTo = ref('')
const status = ref('')
const uploadFile = ref<File | null>(null)
const uploadItemId = ref('')
const loading = ref(true)
const saving = ref(false)
const errorMessage = ref('')
const successMessage = ref('')

const statusOptions = [
  'new',
  'qualified',
  'in_progress',
  'waiting_customer',
  'quoted',
  'won',
  'lost',
  'spam',
  'closed',
]
const itemTypeLabels: Record<string, string> = {
  product: '产品',
  screw: '螺杆',
  barrel: '机筒',
  component: '零部件',
  custom: '定制需求',
  other: '其他',
}
const fileCategoryLabels: Record<string, string> = {
  drawing: '图纸',
  cad: 'CAD 文件',
  photo: '照片',
  pdf: 'PDF',
  specification: '规格文件',
  other: '其他',
}
const fileStatusLabels: Record<string, string> = {
  pending: '等待扫描',
  clean: '安全检查通过',
  infected: '发现风险',
  rejected: '已拒绝',
  uploaded: '已上传',
  missing: '文件缺失',
}
const auditActionLabels: Record<string, string> = {
  'rfq.status_change': '变更询盘状态',
  'rfq.priority_change': '变更优先级',
  'rfq.assign': '分配负责人',
  'rfq.private_file_download': '下载私有附件',
}

/** 读取询盘详情和可分配用户；输入无，输出 Promise<void>。 */
async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const [result, userResult] = await Promise.all([
      api.detail<RfqDetail>(`/rfqs/${route.params.id}`),
      api.detail<UserItem[]>('/users').catch(() => []),
    ])
    detail.value = result
    users.value = userResult
    status.value = String(result.rfq.status || '')
    assignedTo.value = String(result.rfq.assigned_to || '')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '无法读取询盘详情。'
  } finally {
    loading.value = false
  }
}

/** 保存负责人并重新读取，避免仅显示前端成功状态。 */
async function assign(): Promise<void> {
  saving.value = true
  try {
    await api.create(`/rfqs/${route.params.id}/assign`, {
      assigned_to: assignedTo.value || null,
    })
    await load()
    successMessage.value = '负责人已保存并重新读取。'
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '负责人保存失败。'
  } finally {
    saving.value = false
  }
}

/** 保存询盘状态并重新读取。 */
async function updateStatus(): Promise<void> {
  saving.value = true
  try {
    await api.update(`/rfqs/${route.params.id}`, { status: status.value })
    await load()
    successMessage.value = '询盘状态已保存并重新读取。'
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '状态更新失败。'
  } finally {
    saving.value = false
  }
}

/** 请求受权限保护的短时下载地址。 */
async function download(fileId: unknown): Promise<void> {
  const result = await api.create<{ url: string }>(
    `/rfqs/${route.params.id}/files/${fileId}/download-url`,
    {},
  )
  window.location.assign(result.url)
}

/** 上传询盘私有附件；文件不会进入公开媒体库。 */
async function upload(): Promise<void> {
  if (!uploadFile.value) return
  const body = new FormData()
  body.append('file', uploadFile.value)
  body.append('file_category', 'other')
  if (uploadItemId.value) body.append('item_id', uploadItemId.value)
  try {
    await api.upload(`/rfqs/${route.params.id}/files`, body)
    uploadFile.value = null
    await load()
    successMessage.value = '私有附件已上传并重新读取。'
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '附件上传失败。'
  }
}

/** 输入用户ID；输出可读账号名称。 */
function userLabel(userId: unknown): string {
  if (!userId) return '系统或未知账号'
  const user = users.value.find((item) => item.id === String(userId))
  return user?.display_name || user?.email || '账号已不可用'
}

onMounted(load)
</script>

<template>
  <main class="admin-shell rfq-detail-page">
    <header>
      <NuxtLink to="/rfqs">← 返回询盘中心</NuxtLink>
      <p>询盘详情</p>
      <h1>{{ detail?.rfq.public_reference || '正在读取…' }}</h1>
    </header>
    <p v-if="loading" role="status">正在读取询盘详情…</p>
    <p v-if="errorMessage" class="error-message" role="alert">
      {{ errorMessage }}
    </p>
    <p v-if="successMessage" role="status">{{ successMessage }}</p>

    <template v-if="detail && !loading">
      <section class="detail-card">
        <h2>基本信息</h2>
        <dl>
          <div>
            <dt>公司</dt>
            <dd>{{ detail.rfq.company_name || '未填写' }}</dd>
          </div>
          <div>
            <dt>联系人</dt>
            <dd>{{ detail.rfq.contact_name || '未填写' }}</dd>
          </div>
          <div>
            <dt>邮箱</dt>
            <dd>{{ detail.rfq.email || '未填写' }}</dd>
          </div>
          <div>
            <dt>电话</dt>
            <dd>{{ detail.rfq.phone || '未填写' }}</dd>
          </div>
          <div>
            <dt>优先级</dt>
            <dd>{{ labelFrom(RFQ_PRIORITY_LABELS, detail.rfq.priority) }}</dd>
          </div>
          <div>
            <dt>创建时间</dt>
            <dd>{{ formatBeijingTime(detail.rfq.created_at) }}</dd>
          </div>
          <div class="wide">
            <dt>来源页面</dt>
            <dd>{{ detail.rfq.source_page_url || '未记录' }}</dd>
          </div>
          <div class="wide">
            <dt>客户留言</dt>
            <dd>{{ detail.rfq.message || '未填写' }}</dd>
          </div>
        </dl>
      </section>

      <section class="detail-card management-grid">
        <div>
          <h2>负责人</h2>
          <label
            >分配给<select v-model="assignedTo">
              <option value="">未分配</option>
              <option v-for="user in users" :key="user.id" :value="user.id">
                {{ user.display_name || user.email }}
              </option>
            </select></label
          ><button type="button" :disabled="saving" @click="assign">保存负责人</button>
        </div>
        <div>
          <h2>询盘状态</h2>
          <label
            >当前状态<select v-model="status">
              <option v-for="value in statusOptions" :key="value" :value="value">
                {{ labelFrom(RFQ_STATUS_LABELS, value) }}
              </option>
            </select></label
          ><button
            type="button"
            :disabled="saving || status === detail.rfq.status"
            @click="updateStatus"
          >
            保存状态
          </button>
        </div>
      </section>

      <section class="detail-card">
        <h2>询价项目</h2>
        <p v-if="!detail.items.length">未填写结构化项目。</p>
        <div v-else class="item-grid">
          <article v-for="(item, index) in detail.items" :key="String(item.id)">
            <strong>项目 {{ index + 1 }} · {{ labelFrom(itemTypeLabels, item.item_type) }}</strong>
            <dl>
              <div>
                <dt>产品名称</dt>
                <dd>{{ item.product_name_text || '未填写' }}</dd>
              </div>
              <div>
                <dt>数量</dt>
                <dd>{{ item.quantity || '未填写' }}</dd>
              </div>
              <div>
                <dt>材料</dt>
                <dd>{{ item.material_text || '未填写' }}</dd>
              </div>
              <div>
                <dt>螺杆直径</dt>
                <dd>{{ item.screw_diameter || '未填写' }}</dd>
              </div>
              <div>
                <dt>长度</dt>
                <dd>{{ item.length || '未填写' }}</dd>
              </div>
              <div>
                <dt>设备</dt>
                <dd>
                  {{
                    [item.machine_brand, item.machine_model].filter(Boolean).join(' ') || '未填写'
                  }}
                </dd>
              </div>
              <div class="wide">
                <dt>定制要求</dt>
                <dd>{{ item.requirements || '未填写' }}</dd>
              </div>
            </dl>
          </article>
        </div>
      </section>

      <section class="detail-card">
        <h2>私有附件</h2>
        <p>附件仅限有权限的后台账号访问，不会进入公开媒体库。</p>
        <form class="upload-form" @submit.prevent="upload">
          <label
            >选择文件<input
              type="file"
              @change="
                uploadFile = ($event.target as HTMLInputElement).files?.[0] || null
              " /></label
          ><label
            >关联项目<select v-model="uploadItemId">
              <option value="">整条询盘</option>
              <option
                v-for="(item, index) in detail.items"
                :key="String(item.id)"
                :value="String(item.id)"
              >
                项目 {{ index + 1 }} ·
                {{ item.product_name_text || labelFrom(itemTypeLabels, item.item_type) }}
              </option>
            </select></label
          ><button type="submit" :disabled="!uploadFile">上传私有附件</button>
        </form>
        <p v-if="!detail.files.length">暂无附件。</p>
        <table v-else>
          <thead>
            <tr>
              <th>文件名</th>
              <th>类型</th>
              <th>安全状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="fileItem in detail.files" :key="String(fileItem.id)">
              <td>{{ fileItem.original_filename }}</td>
              <td>
                {{ labelFrom(fileCategoryLabels, fileItem.file_category) }}
              </td>
              <td>
                {{ labelFrom(fileStatusLabels, fileItem.malware_scan_status) }}
                ·
                {{ labelFrom(fileStatusLabels, fileItem.upload_status) }}
              </td>
              <td>
                <button
                  type="button"
                  :disabled="fileItem.malware_scan_status !== 'clean'"
                  @click="download(fileItem.id)"
                >
                  安全下载
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="detail-card">
        <h2>发布与操作历史</h2>
        <p v-if="!detail.audit_logs.length">暂无操作记录。</p>
        <ol v-else class="audit-list">
          <li v-for="log in detail.audit_logs" :key="String(log.id)">
            <strong>{{ labelFrom(auditActionLabels, log.action) }}</strong
            ><span>{{ userLabel(log.user_id) }} · {{ formatBeijingTime(log.created_at) }}</span>
          </li>
        </ol>
      </section>
    </template>
  </main>
</template>

<style scoped>
.rfq-detail-page {
  display: grid;
  gap: 1rem;
  align-content: start;
}
.rfq-detail-page > header p,
.rfq-detail-page > header h1 {
  margin: 0.2rem 0 0;
}
.rfq-detail-page > header p {
  color: #0f70c9;
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.12em;
}
.detail-card {
  padding: 1rem;
  background: #fff;
  border: 1px solid #dce5ed;
  border-radius: 0.8rem;
}
.detail-card h2 {
  margin: 0 0 0.8rem;
  font-size: 1.05rem;
}
dl {
  margin: 0;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.75rem;
}
dl div {
  min-width: 0;
}
dt {
  color: #728495;
  font-size: 0.72rem;
}
dd {
  margin: 0.2rem 0 0;
  overflow-wrap: anywhere;
  color: #263f55;
}
.wide {
  grid-column: 1 / -1;
}
.management-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1.5rem;
}
.management-grid > div,
.upload-form {
  display: grid;
  gap: 0.65rem;
}
.item-grid {
  display: grid;
  gap: 0.75rem;
}
.item-grid article {
  padding: 0.8rem;
  background: #f6f9fb;
  border-radius: 0.6rem;
}
.upload-form {
  grid-template-columns: 1fr 1fr auto;
  align-items: end;
}
.audit-list {
  display: grid;
  gap: 0.6rem;
}
.audit-list li span {
  display: block;
  margin-top: 0.2rem;
  color: #728495;
  font-size: 0.76rem;
}
table {
  width: 100%;
  border-collapse: collapse;
}
th,
td {
  padding: 0.65rem;
  text-align: left;
  border-bottom: 1px solid #e3eaf0;
}
@media (max-width: 54rem) {
  dl,
  .management-grid,
  .upload-form {
    grid-template-columns: 1fr;
  }
}
</style>
