// 模块用途：管理 RFQ 当前隐私政策和仅驻留客户端内存的短期上下文。

import { ref, shallowRef, type Ref } from 'vue'

import type { PublicPrivacyContextDto, PublicPrivacyPolicyDto } from '../types/public'

export interface RfqPrivacyOptions {
  initialPolicy: PublicPrivacyPolicyDto | null
  consentPrivacy: Ref<boolean>
  loadPolicy: () => Promise<PublicPrivacyPolicyDto>
  loadContext: (policy: PublicPrivacyPolicyDto) => Promise<PublicPrivacyContextDto>
}

/**
 * 创建 RFQ 隐私政策状态。
 *
 * 输入：options，SSR 初始政策、同意 ref 与两个公开 API 请求函数。
 * 输出：当前政策、内存 token、加载状态以及初始化/恢复动作。
 */
export function useRfqPrivacy(options: RfqPrivacyOptions) {
  const policy = shallowRef(options.initialPolicy)
  const contextToken = ref('')
  const isContextLoading = ref(false)

  /** 为指定政策请求并核对上下文，响应不匹配时绝不接受 token。 */
  async function requestContext(currentPolicy: PublicPrivacyPolicyDto): Promise<boolean> {
    contextToken.value = ''
    isContextLoading.value = true
    try {
      const context = await options.loadContext(currentPolicy)
      if (
        !context.token ||
        context.version_label !== currentPolicy.version_label ||
        context.locale !== currentPolicy.locale ||
        policy.value?.version_label !== currentPolicy.version_label
      ) {
        return false
      }
      contextToken.value = context.token
      return true
    } catch {
      return false
    } finally {
      isContextLoading.value = false
    }
  }

  /** 初始化当前 SSR 政策上下文；若挂载前已换版，只自动恢复一次并撤销旧同意。 */
  async function initializeContext(): Promise<boolean> {
    if (!policy.value) return false
    if (await requestContext(policy.value)) return true
    return recoverContext()
  }

  /** 重新读取最新政策和上下文，并撤销旧同意。 */
  async function recoverContext(): Promise<boolean> {
    // 版本、期限、签名或语言任一失效后，旧同意都不能沿用到新政策。
    options.consentPrivacy.value = false
    contextToken.value = ''
    try {
      policy.value = await options.loadPolicy()
    } catch {
      policy.value = null
      return false
    }
    return requestContext(policy.value)
  }

  return {
    policy,
    contextToken,
    isContextLoading,
    initializeContext,
    recoverContext,
  }
}
