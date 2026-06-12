import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useSSE } from '@/composables/useSSE'
import { useApiClient } from '@/composables/useApiClient'

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
  const sse = useSSE()

  const hasMessages = computed(() => messages.value.length > 0)

  function addMessage(msg: ChatMessage) {
    messages.value.push(msg)
  }

  /** 取消正在进行的 SSE 流并重置状态 */
  function cancelStream() {
    sse.abort()
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
    if (sse.isStreaming.value) return

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
    let errorHandled = false

    try {
      await sse.connect('/api/chat/stream', {
        onToken: (token) => { streamingMessage.value += token },
        onDone: () => {
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
        },
        onError: (msg) => {
          errorHandled = true
          error.value = msg
          messages.value.push({
            review_id: reviewId,
            role: 'system',
            content: `❌ 发生错误：${msg}`,
          })
        },
      }, {
        method: 'POST',
        body: {
          content,
          review_id: reviewId,
          anchor_clause_id: anchorClause.value?.id,
          anchor_clause_text: anchorClause.value?.text,
          provider,
        },
      })

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
      if (e.name === 'AbortError') return
      // 如果 error 已经由 onError 处理过，不再重复推送系统消息
      if (!errorHandled) {
        error.value = e.message
        messages.value.push({
          review_id: reviewId,
          role: 'system',
          content: `❌ ${e.message}`,
        })
      }
    } finally {
      isStreaming.value = false
    }
  }

  async function loadHistory(reviewId: number) {
    try {
      const api = useApiClient()
      messages.value = await api.get<ChatMessage[]>(`/api/chat/${reviewId}/history`)
    } catch (e: any) {
      error.value = e.message
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
