<!-- 页面用途：以中文分组矩阵查看角色，并在服务端权限边界内编辑现有自定义角色。 -->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ROLE_NAME_LABELS, permissionPresentation } from '~/utils/adminZhCn'
import { buildPermissionChange } from '~/utils/rolePermissions'

interface RoleItem {
  id: string
  name: string
  display_name: string
  description: string | null
  is_system: boolean
  permissions: string[]
}

const api = useAuthorityApi()
const { currentUser } = useAuth()
const roles = ref<RoleItem[]>([])
const roleSearch = ref('')
const loading = ref(true)
const saving = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const selectedRoleId = ref('')
const beforePermissions = ref<string[]>([])
const draftPermissions = ref<string[]>([])
const reviewingChanges = ref(false)

const canManageRoles = computed(
  () => currentUser.value?.permissions.includes('role.manage') ?? false,
)
const selectedRole = computed(() => roles.value.find((role) => role.id === selectedRoleId.value))
const actorPermissions = computed(() => [...new Set(currentUser.value?.permissions || [])].sort())
const permissionChange = computed(() =>
  buildPermissionChange(beforePermissions.value, draftPermissions.value),
)
const exceedsActorCeiling = computed(() =>
  beforePermissions.value.some((code) => !actorPermissions.value.includes(code)),
)
const canEditSelected = computed(
  () =>
    Boolean(selectedRole.value) &&
    canManageRoles.value &&
    !selectedRole.value?.is_system &&
    !exceedsActorCeiling.value,
)

const filteredRoles = computed(() => {
  const keyword = roleSearch.value.trim().toLocaleLowerCase('zh-CN')
  if (!keyword) return roles.value
  return roles.value.filter((role) => {
    const searchable = [
      role.name,
      role.display_name,
      role.description,
      ROLE_NAME_LABELS[role.name],
      ...role.permissions.flatMap((code) => {
        const presentation = permissionPresentation(code)
        return [code, presentation.resourceLabel, presentation.actionLabel]
      }),
    ]
    return searchable.some((value) => value?.toLocaleLowerCase('zh-CN').includes(keyword))
  })
})

/** 输入权限代码；输出按中文业务资源分组的权限选项。 */
function groupedPermissionCodes(codes: string[]): Array<{
  label: string
  permissions: Array<ReturnType<typeof permissionPresentation> & { code: string }>
}> {
  const groups = new Map<
    string,
    Array<ReturnType<typeof permissionPresentation> & { code: string }>
  >()
  for (const code of codes) {
    const permission = { code, ...permissionPresentation(code) }
    const rows = groups.get(permission.resourceLabel) || []
    rows.push(permission)
    groups.set(permission.resourceLabel, rows)
  }
  return [...groups.entries()].map(([label, permissions]) => ({ label, permissions }))
}

/** 读取角色列表；保存后必须再次调用此函数完成 fresh GET。 */
async function loadRoles(preserveSelection = true): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    roles.value = await api.detail<RoleItem[]>('/rbac/roles')
    if (preserveSelection && selectedRoleId.value) {
      const freshRole = roles.value.find((role) => role.id === selectedRoleId.value)
      if (freshRole) {
        beforePermissions.value = [...freshRole.permissions]
        draftPermissions.value = [...freshRole.permissions]
      }
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '无法读取角色权限。'
  } finally {
    loading.value = false
  }
}

/** 选择现有角色并建立保存前基线；系统角色始终只读。 */
function openRole(role: RoleItem): void {
  selectedRoleId.value = role.id
  beforePermissions.value = [...role.permissions]
  draftPermissions.value = [...role.permissions]
  reviewingChanges.value = false
  successMessage.value = ''
  errorMessage.value = ''
}

/** 打开可读变更对比；没有变化或无权编辑时不进入确认阶段。 */
function reviewPermissionChange(): void {
  if (!canEditSelected.value || !permissionChange.value.changed) return
  reviewingChanges.value = true
  successMessage.value = ''
}

/** 通过既有 RBAC API 保存权限，再执行 fresh GET 并核对重开基线。 */
async function savePermissions(): Promise<void> {
  const role = selectedRole.value
  if (!role || !canEditSelected.value || !permissionChange.value.changed) return
  saving.value = true
  errorMessage.value = ''
  try {
    const expected = [...new Set(draftPermissions.value)].sort()
    await api.replace<RoleItem>(`/rbac/roles/${role.id}/permissions`, {
      permission_codes: expected,
    })
    await loadRoles(true)
    const freshRole = roles.value.find((item) => item.id === role.id)
    if (!freshRole || JSON.stringify(freshRole.permissions) !== JSON.stringify(expected)) {
      throw new Error('fresh GET 与保存结果不一致')
    }
    reviewingChanges.value = false
    successMessage.value = `已保存“${freshRole.display_name}”，fresh GET 回读一致；可刷新页面重开确认。`
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '角色权限保存失败。'
  } finally {
    saving.value = false
  }
}

onMounted(() => loadRoles(false))
</script>

<template>
  <main class="admin-shell roles-page">
    <header>
      <p>账号与安全</p>
      <h1>角色权限</h1>
      <span>系统角色只读；具备 role.manage 的账号可编辑现有自定义角色。</span>
    </header>
    <p v-if="loading" role="status">正在读取角色权限…</p>
    <p v-if="errorMessage" class="error-message" role="alert">{{ errorMessage }}</p>
    <p v-if="successMessage" class="success-message" role="status">{{ successMessage }}</p>

    <section class="role-management" aria-label="角色权限管理能力">
      <label>
        搜索角色或权限
        <input v-model="roleSearch" type="search" placeholder="输入中文名称、权限或系统代码" />
      </label>
      <p v-if="canManageRoles">当前账号可在下方编辑现有自定义角色，保存仍受服务端权限上限检查。</p>
      <p v-else>当前账号仅可查看，缺少 role.manage；所有编辑控件均不开放。</p>
      <p>当前后端没有角色新建或删除接口，因此本页不显示无效的新建、删除按钮。</p>
    </section>

    <section v-if="filteredRoles.length" class="role-grid" aria-label="权限分组">
      <article v-for="role in filteredRoles" :key="role.id">
        <header>
          <div>
            <h2>{{ ROLE_NAME_LABELS[role.name] || role.display_name || role.name }}</h2>
            <small>{{ role.is_system ? '系统角色（只读）' : '自定义角色' }}</small>
          </div>
          <span>{{ role.permissions.length }} 项权限</span>
        </header>
        <div v-if="role.permissions.length" class="permission-groups">
          <section v-for="group in groupedPermissionCodes(role.permissions)" :key="group.label">
            <strong>{{ group.label }}</strong>
            <span v-for="permission in group.permissions" :key="permission.code">
              {{ permission.actionLabel }}
            </span>
          </section>
        </div>
        <p v-else>此角色尚未配置权限。</p>
        <button type="button" class="role-open" @click="openRole(role)">
          {{ canManageRoles && !role.is_system ? '编辑权限' : '查看权限' }}
        </button>
        <details>
          <summary>技术详情</summary>
          <code>{{ role.name }}</code>
          <ul>
            <li v-for="code in role.permissions" :key="code">
              <code>{{ code }}</code>
            </li>
          </ul>
        </details>
      </article>
    </section>
    <section v-else-if="!loading" class="empty-state">
      <h2>{{ roleSearch ? '没有匹配的角色' : '暂无角色' }}</h2>
      <p>{{ roleSearch ? '请更换搜索词。' : '系统尚未返回可查看的角色。' }}</p>
    </section>

    <section v-if="selectedRole" class="role-editor" aria-label="角色权限编辑器">
      <header>
        <div>
          <p>当前角色</p>
          <h2>{{ selectedRole.display_name }}</h2>
        </div>
        <span>{{ selectedRole.is_system ? '系统角色只读' : '自定义角色' }}</span>
      </header>
      <p v-if="selectedRole.is_system">系统角色不在本页修改，请选择独立自定义角色。</p>
      <p v-else-if="!canManageRoles">缺少 role.manage，当前角色只能查看。</p>
      <p v-else-if="exceedsActorCeiling">
        该角色包含超出当前账号授权上限的权限，服务端禁止保存；请由具备完整权限的管理员处理。
      </p>
      <div class="permission-editor-groups">
        <fieldset v-for="group in groupedPermissionCodes(actorPermissions)" :key="group.label">
          <legend>{{ group.label }}</legend>
          <label v-for="permission in group.permissions" :key="permission.code">
            <input
              v-model="draftPermissions"
              type="checkbox"
              :value="permission.code"
              :disabled="!canEditSelected || saving"
            />
            {{ permission.actionLabel }}
          </label>
        </fieldset>
      </div>
      <div class="editor-actions">
        <button
          type="button"
          :disabled="!canEditSelected || !permissionChange.changed || saving"
          @click="reviewPermissionChange"
        >
          查看变更并确认
        </button>
        <button type="button" :disabled="saving" @click="openRole(selectedRole)">
          撤销未保存变更
        </button>
      </div>

      <section v-if="reviewingChanges" class="change-review" aria-label="权限变更确认">
        <h3>确认权限变更</h3>
        <div>
          <section>
            <strong>新增 {{ permissionChange.added.length }} 项</strong>
            <ul>
              <li v-for="code in permissionChange.added" :key="code">{{ code }}</li>
            </ul>
          </section>
          <section>
            <strong>移除 {{ permissionChange.removed.length }} 项</strong>
            <ul>
              <li v-for="code in permissionChange.removed" :key="code">{{ code }}</li>
            </ul>
          </section>
        </div>
        <p>保存将写入既有 Audit 审计链，并在完成后执行 fresh GET 核对。</p>
        <button type="button" :disabled="saving" @click="savePermissions">
          {{ saving ? '正在保存…' : '确认保存权限' }}
        </button>
        <button type="button" :disabled="saving" @click="reviewingChanges = false">
          返回继续编辑
        </button>
      </section>
    </section>
  </main>
</template>

<style scoped>
.roles-page {
  display: grid;
  gap: 1rem;
  align-content: start;
}
.roles-page > header p,
.roles-page > header h1,
.role-editor h2,
.role-editor p {
  margin: 0;
}
.roles-page > header p,
.role-editor header p {
  color: #0f70c9;
  font-size: 0.7rem;
  font-weight: 800;
  letter-spacing: 0.12em;
}
.roles-page > header span,
.role-editor > header span {
  color: #687b8e;
}
.success-message {
  padding: 0.75rem 1rem;
  color: #155e40;
  background: #eaf8f1;
  border: 1px solid #b9e5cf;
  border-radius: 0.7rem;
}
.role-management {
  padding: 0.9rem 1rem;
  display: grid;
  gap: 0.45rem;
  background: #f3f8fc;
  border: 1px solid #dce8f0;
  border-radius: 0.75rem;
}
.role-management label {
  max-width: 34rem;
  display: grid;
  gap: 0.3rem;
  color: #3e5870;
  font-size: 0.76rem;
}
.role-management p {
  margin: 0;
  color: #5e7487;
  font-size: 0.75rem;
}
.role-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(22rem, 1fr));
  gap: 1rem;
}
.role-grid > article,
.role-editor {
  min-width: 0;
  padding: 1rem;
  background: #fff;
  border: 1px solid #dce5ed;
  border-radius: 0.8rem;
}
.role-grid > article > header,
.role-editor > header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 0.5rem;
}
.role-grid h2 {
  margin: 0;
  font-size: 1.05rem;
}
.role-grid header small {
  color: #748697;
}
.permission-groups {
  margin-top: 0.8rem;
  display: grid;
  gap: 0.5rem;
}
.permission-groups section {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.4rem;
}
.permission-groups strong {
  min-width: 8rem;
  color: #27435b;
}
.permission-groups span {
  padding: 0.2rem 0.45rem;
  color: #0b5f9c;
  background: #eaf5fc;
  border-radius: 999px;
  font-size: 0.72rem;
}
.role-open {
  margin-top: 0.9rem;
}
.role-editor {
  display: grid;
  gap: 1rem;
}
.permission-editor-groups {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
  gap: 0.75rem;
}
.permission-editor-groups fieldset {
  min-width: 0;
  padding: 0.75rem;
  display: grid;
  gap: 0.45rem;
  border: 1px solid #dce5ed;
  border-radius: 0.65rem;
}
.permission-editor-groups label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  color: #38536a;
  font-size: 0.78rem;
}
.editor-actions,
.change-review > div {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}
.change-review {
  padding: 1rem;
  background: #f7fafc;
  border: 1px solid #cfdce6;
  border-radius: 0.7rem;
}
.change-review > div > section {
  min-width: 15rem;
  flex: 1;
}
.change-review li,
details code {
  overflow-wrap: anywhere;
}
details {
  margin-top: 1rem;
  color: #738596;
}
details ul {
  columns: 2;
}
@media (max-width: 56rem) {
  .role-grid {
    grid-template-columns: 1fr;
  }
  details ul {
    columns: 1;
  }
}
</style>
