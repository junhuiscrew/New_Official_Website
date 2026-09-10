<!-- 页面用途：以中文分组矩阵只读展示角色权限，原权限代码仅作为技术详情。 -->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { ROLE_NAME_LABELS, permissionPresentation } from '~/utils/adminZhCn'

interface RoleItem {
  id: string
  name: string
  display_name: string
  permissions: string[]
}
const { apiBase, currentUser } = useAuth()
const roleSearch = ref('')
const { data, error, status } = await useFetch<{ data: RoleItem[] }>('/rbac/roles', {
  baseURL: apiBase,
  credentials: 'include',
  server: false,
})
const filteredRoles = computed(() => {
  const keyword = roleSearch.value.trim().toLocaleLowerCase('zh-CN')
  if (!keyword) return data.value?.data || []
  return (data.value?.data || []).filter((role) => {
    const searchable = [
      role.name,
      role.display_name,
      ROLE_NAME_LABELS[role.name],
      ...role.permissions.flatMap((code) => {
        const presentation = permissionPresentation(code)
        return [code, presentation.resourceLabel, presentation.actionLabel]
      }),
    ]
    return searchable.some((value) => value?.toLocaleLowerCase('zh-CN').includes(keyword))
  })
})
const canManageRoles = computed(() => currentUser.value?.permissions.includes('role.manage') ?? false)

/** 输入角色；输出按中文业务资源分组的权限矩阵。 */
function groupedPermissions(role: RoleItem): Array<{
  label: string
  permissions: ReturnType<typeof permissionPresentation>[]
}> {
  const groups = new Map<string, ReturnType<typeof permissionPresentation>[]>()
  for (const code of role.permissions) {
    const permission = permissionPresentation(code)
    const rows = groups.get(permission.resourceLabel) || []
    rows.push(permission)
    groups.set(permission.resourceLabel, rows)
  }
  return [...groups.entries()].map(([label, permissions]) => ({
    label,
    permissions,
  }))
}
</script>

<template>
  <main class="admin-shell roles-page">
    <header>
      <p>账号与安全</p>
      <h1>角色权限</h1>
      <span>权限分组以中文业务名称展示；系统权限代码未被修改。</span>
    </header>
    <!-- SSR 的 idle 与客户端刚启动请求时的 pending 使用同一节点，避免首次渲染不一致。 -->
    <p v-if="status === 'idle' || status === 'pending'" role="status">正在读取角色权限…</p>
    <p v-else-if="error" class="error-message" role="alert">
      无法读取角色权限，请检查当前账号权限。
    </p>
    <template v-else>
      <section class="role-management" aria-label="角色权限管理能力">
        <label>
          搜索角色或权限
          <input v-model="roleSearch" type="search" placeholder="输入中文名称、权限或系统代码" />
        </label>
        <p v-if="canManageRoles">
          角色权限管理：当前账号具备管理权限，可通过既有接口修改；本轮不修改系统角色。
        </p>
        <p v-else>
          角色权限管理：当前账号仅可查看，缺少 role.manage；修改入口不开放。
        </p>
      </section>
      <section v-if="filteredRoles.length" class="role-grid" aria-label="权限分组">
      <article v-for="role in filteredRoles" :key="role.id">
        <header>
          <h2>
            {{ ROLE_NAME_LABELS[role.name] || role.display_name || role.name }}
          </h2>
          <span>{{ role.permissions.length }} 项权限</span>
        </header>
        <div v-if="role.permissions.length" class="permission-groups">
          <section v-for="group in groupedPermissions(role)" :key="group.label">
            <strong>{{ group.label }}</strong>
            <span
              v-for="permission in group.permissions"
              :key="permission.resource + permission.action"
              >{{ permission.actionLabel }}</span
            >
          </section>
        </div>
        <p v-else>此角色尚未配置权限。</p>
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
      <section v-else class="empty-state">
        <h2>{{ roleSearch ? '没有匹配的角色' : '暂无角色' }}</h2>
        <p>{{ roleSearch ? '请更换搜索词。' : '系统尚未返回可查看的角色。' }}</p>
      </section>
    </template>
  </main>
</template>

<style scoped>
.roles-page {
  display: grid;
  gap: 1rem;
  align-content: start;
}
.roles-page > header p,
.roles-page > header h1 {
  margin: 0;
}
.roles-page > header p {
  color: #0f70c9;
  font-size: 0.7rem;
  font-weight: 800;
  letter-spacing: 0.12em;
}
.roles-page > header span {
  color: #687b8e;
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
.role-grid > article {
  padding: 1rem;
  background: #fff;
  border: 1px solid #dce5ed;
  border-radius: 0.8rem;
}
.role-grid > article > header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 0.5rem;
}
.role-grid h2 {
  margin: 0;
  font-size: 1.05rem;
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
details {
  margin-top: 1rem;
  color: #738596;
}
details ul {
  columns: 2;
}
</style>
