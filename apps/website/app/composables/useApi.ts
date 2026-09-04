// 组合式模块用途：为 Website 的浏览器请求与 SSR 请求统一选择正确的 API 地址。
import { resolveApiBase } from '@junhui/config/api-base'

export function useApi() {
  const config = useRuntimeConfig()
  const apiBase = resolveApiBase(import.meta.server, config.public.apiBase, config.apiInternalBase)

  // SSR 请求转发 Cookie；浏览器请求使用同源 /api/v1，避免依赖容器内部主机名。
  const headers = import.meta.server ? useRequestHeaders(['cookie']) : undefined

  return $fetch.create({
    baseURL: apiBase,
    credentials: 'include',
    headers,
  })
}
