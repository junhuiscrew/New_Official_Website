// 模块用途：统一选择浏览器公开 API 地址与 Nuxt SSR 容器内部 API 地址。
export function resolveApiBase(
  isServer: boolean,
  publicBase: string,
  internalBase: string,
): string {
  return isServer ? internalBase : publicBase
}
