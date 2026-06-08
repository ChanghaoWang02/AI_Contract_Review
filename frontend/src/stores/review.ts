import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface ClauseIssue {
  type: string
  detail: string
}

export interface ClauseResult {
  id: string
  original_text: string
  summary: string
  risk: 'high' | 'medium' | 'low'
  issues: ClauseIssue[]
  suggestions: string[]
  revised_text?: string
}

export interface Findings {
  clauses: ClauseResult[]
  overall_score: number
  summary: string
}

export interface ReviewRecord {
  id: number
  contract_id: number
  status: 'pending' | 'processing' | 'completed' | 'error'
  summary?: string
  risk_level?: 'high' | 'medium' | 'low'
  overall_score?: number
  findings?: Findings
  token_usage?: number
  provider_used?: string
  created_at: string
  completed_at?: string
}

export const useReviewStore = defineStore('review', () => {
  // TODO: `createReview` 和 `streamReview` 使用裸 fetch + AbortController 管理。
  // 后续应统一迁移到 useSSE composable，与 chat store 共享 SSE 生命周期管理，
  // 获得 abort() 取消能力，避免切合同时流污染（参见 2026-06-08 chat SSE 修复）。
  const currentReview = ref<ReviewRecord | null>(null)
  const streamingContent = ref('')
  const isStreaming = ref(false)
  const error = ref<string | null>(null)

  async function createReview(contractId: number, provider?: string) {
    isStreaming.value = true
    error.value = null
    streamingContent.value = ''

    try {
      const res = await fetch('/api/reviews/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ contract_id: contractId, provider }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || '创建审核失败')
      }

      const reader = res.body?.getReader()
      if (!reader) throw new Error('无法读取流')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))
            if (event.event === 'token') {
              streamingContent.value += event.data
            } else if (event.event === 'progress') {
              streamingContent.value += `\n\n${event.data}\n`
            } else if (event.event === 'done') {
              const data = JSON.parse(event.data)
              const score = data.findings?.overall_score ?? 0
              currentReview.value = {
                id: data.review_id || 0,  // 使用服务器返回的真实 review_id
                contract_id: contractId,
                status: data.parse_error ? 'error' : 'completed',
                findings: data.findings,
                overall_score: score,
                summary: data.findings?.summary,
                provider_used: data.provider_used,
                token_usage: data.token_usage,
                risk_level: score <= 45 ? 'high' : score <= 70 ? 'medium' : 'low',
                created_at: new Date().toISOString(),
              } as ReviewRecord
              streamingContent.value = ''
              return currentReview.value
            } else if (event.event === 'error') {
              error.value = event.data
              currentReview.value = null
              return null
            }
          } catch {
            // 跳过无法解析的 SSE 行（JSON 不完整或格式异常）
          }
        }
      }
      // 流结束但未收到 done 事件：如果有内容则保留
      if (!currentReview.value && streamingContent.value) {
        error.value = '审核流中断，但部分结果可能已保存'
      }
      return null
    } catch (e: any) {
      error.value = e.message
      return null
    } finally {
      isStreaming.value = false
    }
  }

  async function fetchReview(reviewId: number) {
    try {
      const res = await fetch(`/api/reviews/${reviewId}`)
      if (!res.ok) throw new Error('审核记录不存在')
      currentReview.value = await res.json()
      return currentReview.value
    } catch (e: any) {
      error.value = e.message
      throw e
    }
  }

  async function streamReview(reviewId: number) {
    isStreaming.value = true
    streamingContent.value = ''

    try {
      const res = await fetch(`/api/reviews/${reviewId}/stream`)
      const reader = res.body?.getReader()
      if (!reader) throw new Error('无法读取流')

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
              if (data.event === 'done') {
                const parsed = JSON.parse(data.data)
                if (currentReview.value) {
                  if (parsed.findings) {
                    currentReview.value.findings = parsed.findings
                    const score = parsed.findings.overall_score ?? 0
                    currentReview.value.overall_score = score
                    currentReview.value.summary = parsed.findings.summary
                    currentReview.value.risk_level = score <= 45 ? 'high' : score <= 70 ? 'medium' : 'low'
                  }
                  currentReview.value.status = parsed.parse_error ? 'error' : 'completed'
                  currentReview.value.provider_used = parsed.provider_used || currentReview.value.provider_used
                  currentReview.value.token_usage = parsed.token_usage ?? currentReview.value.token_usage
                }
              }
            } catch { /* ignore parse errors */ }
          }
        }
      }
    } catch (e: any) {
      error.value = e.message
    } finally {
      isStreaming.value = false
    }
  }

  async function fetchReviews(contractId: number): Promise<ReviewRecord[]> {
    const res = await fetch(`/api/reviews/by-contract/${contractId}`)
    if (!res.ok) return []
    return res.json()
  }

  return {
    currentReview,
    streamingContent,
    isStreaming,
    error,
    createReview,
    fetchReview,
    streamReview,
    fetchReviews,
  }
})
