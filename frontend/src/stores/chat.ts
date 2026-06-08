import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface ChatMessage {
  id?: number
  review_id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  anchor_clause_id?: string
  anchor_clause_text?: string
  created_at?: string
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const isStreaming = ref(false)
  const streamingMessage = ref('')
  const anchorClause = ref<{ id: string; text: string } | null>(null)
  const error = ref<string | null>(null)
  const abortController = ref<AbortController | null>(null)

  const hasMessages = computed(() => messages.value.length > 0)

  function addMessage(msg: ChatMessage) {
    messages.value.push(msg)
  }

  /** 取消正在进行的 SSE 流并重置状态 */
  function cancelStream() {
    if (abortController.value) {
      abortController.value.abort()
      abortController.value = null
    }
    isStreaming.value = false
    streamingMessage.value = ''
  }

  function clearMessages() {
    cancelStream()
    messages.value = []
  }

  function setAnchor(id: string, text: string) {
    anchorClause.value = { id, text }
  }

  function clearAnchor() {
    anchorClause.value = null
  }

  async function sendMessage(
    content: string,
    reviewId: number,
    provider?: string,
  ) {
    if (isStreaming.value) return

    // 取消之前的流（如果有残留）
    cancelStream()

    const userMsg: ChatMessage = {
      review_id: reviewId,
      role: 'user',
      content,
      anchor_clause_id: anchorClause.value?.id,
      anchor_clause_text: anchorClause.value?.text,
    }
    messages.value.push(userMsg)

    isStreaming.value = true
    streamingMessage.value = ''
    error.value = null
    let doneReceived = false

    const controller = new AbortController()
    abortController.value = controller

    try {
      const res = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content,
          review_id: reviewId,
          anchor_clause_id: anchorClause.value?.id,
          anchor_clause_text: anchorClause.value?.text,
          provider,
        }),
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
              const data = JSON.parse(line.slice(6))
              if (data.event === 'token') {
                streamingMessage.value += data.data
              } else if (data.event === 'done') {
                doneReceived = true
                const assistantMsg: ChatMessage = {
                  review_id: reviewId,
                  role: 'assistant',
                  content: streamingMessage.value,
                  anchor_clause_id: anchorClause.value?.id,
                  anchor_clause_text: anchorClause.value?.text,
                }
                messages.value.push(assistantMsg)
                streamingMessage.value = ''
              } else if (data.event === 'error') {
                error.value = data.data
                messages.value.push({
                  review_id: reviewId,
                  role: 'system',
                  content: `❌ 发生错误：${data.data}`,
                })
              }
            } catch { /* ignore malformed SSE lines */ }
          }
        }
      }

      // 流结束但未收到 done 事件：保留已接收的内容
      if (!doneReceived && streamingMessage.value) {
        const partialMsg: ChatMessage = {
          review_id: reviewId,
          role: 'assistant',
          content: streamingMessage.value + '\n\n> ⚠️ 连接已中断，回复可能不完整',
          anchor_clause_id: anchorClause.value?.id,
          anchor_clause_text: anchorClause.value?.text,
        }
        messages.value.push(partialMsg)
        streamingMessage.value = ''
        error.value = 'AI 回复中断，请重试'
      } else if (!doneReceived && !streamingMessage.value) {
        error.value = 'AI 未返回任何内容，请重试'
      }
    } catch (e: any) {
      // AbortError 是主动取消的，不是错误，静默处理
      if (e.name === 'AbortError') return
      error.value = e.message
      messages.value.push({
        review_id: reviewId,
        role: 'system',
        content: `❌ ${e.message}`,
      })
    } finally {
      isStreaming.value = false
      if (abortController.value === controller) {
        abortController.value = null
      }
    }
  }

  async function loadHistory(reviewId: number) {
    try {
      const res = await fetch(`/api/chat/${reviewId}/history`)
      if (res.ok) {
        messages.value = await res.json()
      } else {
        console.warn(`加载对话历史失败: HTTP ${res.status}`)
      }
    } catch (e: any) {
      console.warn(`加载对话历史失败: ${e.message}`)
    }
  }

  return {
    messages,
    isStreaming,
    streamingMessage,
    anchorClause,
    error,
    hasMessages,
    addMessage,
    clearMessages,
    cancelStream,
    setAnchor,
    clearAnchor,
    sendMessage,
    loadHistory,
  }
})
