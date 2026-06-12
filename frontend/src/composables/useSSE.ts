/**
 * SSE 流式请求组合式函数
 * 用于审核和聊天的流式数据传输
 *
 * 支持 AbortController：调用 abort() 可取消正在进行的 SSE 连接，
 * 切换合同/页面时安全终止旧流，防止流污染。
 */

import { ref } from 'vue'

export interface SSEOptions {
  onToken?: (token: string) => void
  onProgress?: (data: any) => void
  onDone?: (data: any) => void
  onError?: (error: string) => void
  /** 通用事件分发回调，用于消费非标准事件名的结构化数据 */
  onEvent?: (event: string, data: any) => void
}

export interface SSEConnectOptions {
  method?: string
  body?: any
}

export function useSSE() {
  const isStreaming = ref(false)
  const error = ref<string | null>(null)
  const abortController = ref<AbortController | null>(null)

  /** 取消当前正在进行的 SSE 连接 */
  function abort() {
    if (abortController.value) {
      abortController.value.abort()
      abortController.value = null
    }
    isStreaming.value = false
  }

  async function connect(
    url: string,
    options: SSEOptions,
    connectOpts: SSEConnectOptions = {},
  ) {
    // 先取消之前的连接
    abort()

    const controller = new AbortController()
    abortController.value = controller

    isStreaming.value = true
    error.value = null

    const method = connectOpts.method || 'GET'
    const headers: Record<string, string> = { Accept: 'text/event-stream' }
    let body = connectOpts.body
    if (body && !(body instanceof FormData)) {
      headers['Content-Type'] = 'application/json'
      body = JSON.stringify(body)
    } else if (body instanceof FormData) {
      // 浏览器自动设置 Content-Type: multipart/form-data + boundary
      // 不手动设置任何 Content-Type header
    }

    try {
      const res = await fetch(url, {
        method,
        headers,
        body,
        signal: controller.signal,
      })

      if (!res.ok) {
        let detail = ''
        try { const err = await res.json(); detail = err.detail || '' } catch { /* ignore */ }
        throw new Error(detail || `请求失败 (HTTP ${res.status})`)
      }

      const reader = res.body?.getReader()
      if (!reader) throw new Error('无法读取响应流')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const payload = JSON.parse(line.slice(6))
              // Normalize data: payload.data 可能是 string 或 object
              // 只有当它是 JSON 字符串（以 { 或 [开头）时才 parse；普通文本 token 直接使用
              let data: any
              if (typeof payload.data === 'string') {
                const trimmed = payload.data.trim()
                data = (trimmed.startsWith('{') || trimmed.startsWith('['))
                  ? JSON.parse(payload.data)
                  : payload.data
              } else {
                data = payload.data
              }

              // Specific handlers fire first; onEvent fires after as supplementary notification
              if (payload.event === 'token' && options.onToken) {
                options.onToken(typeof data === 'string' ? data : JSON.stringify(data))
              } else if (payload.event === 'progress' && options.onProgress) {
                options.onProgress(data)
              } else if (payload.event === 'done' && options.onDone) {
                options.onDone(data)
              } else if (payload.event === 'error' && options.onError) {
                options.onError(typeof data === 'string' ? data : data?.message || '未知错误')
              }

              // 通用事件分发（在 specific handlers 之后，避免 double-dispatch 问题）
              options.onEvent?.(payload.event, data)
            } catch {
              // 忽略无法解析的行
            }
          }
        }
      }
    } catch (e: any) {
      if (e.name === 'AbortError') return // 主动取消，不是错误
      error.value = e.message
      options.onError?.(e.message)
    } finally {
      isStreaming.value = false
      if (abortController.value === controller) {
        abortController.value = null
      }
    }
  }

  return { isStreaming, error, connect, abort }
}
