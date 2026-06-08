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
  onProgress?: (message: string) => void
  onDone?: (data: any) => void
  onError?: (error: string) => void
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
    if (connectOpts.body) {
      headers['Content-Type'] = 'application/json'
    }

    try {
      const res = await fetch(url, {
        method,
        headers,
        body: connectOpts.body ? JSON.stringify(connectOpts.body) : undefined,
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

              if (payload.event === 'token' && options.onToken) {
                options.onToken(payload.data)
              } else if (payload.event === 'progress' && options.onProgress) {
                options.onProgress(payload.data)
              } else if (payload.event === 'done' && options.onDone) {
                const result = payload.data ? JSON.parse(payload.data) : {}
                options.onDone(result)
              } else if (payload.event === 'error' && options.onError) {
                options.onError(payload.data || '未知错误')
              }
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
