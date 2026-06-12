import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useSSE } from '@/composables/useSSE'
import { useApiClient } from '@/composables/useApiClient'
import type { ClauseIssue, ClauseResult, Findings } from '@/types/review'

export type { ClauseIssue, ClauseResult, Findings }

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
  const currentReview = ref<ReviewRecord | null>(null)
  const streamingContent = ref('')
  const isStreaming = ref(false)
  const error = ref<string | null>(null)
  const sse = useSSE()

  async function createReview(contractId: number, provider?: string) {
    isStreaming.value = true
    error.value = null
    streamingContent.value = ''

    try {
      await sse.connect('/api/reviews/stream', {
        onToken: (token) => { streamingContent.value += token },
        onProgress: (data) => { streamingContent.value += `\n\n${data}\n` },
        onDone: (data) => {
          const score = data.findings?.overall_score ?? 0
          currentReview.value = {
            id: data.review_id || 0,
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
        },
        onError: (msg) => {
          error.value = msg
          currentReview.value = null
        },
      }, {
        method: 'POST',
        body: { contract_id: contractId, provider },
      })
      return currentReview.value
    } catch (e: any) {
      if (e.name === 'AbortError') return null
      error.value = e.message
      return null
    } finally {
      isStreaming.value = false
    }
  }

  async function fetchReview(reviewId: number) {
    try {
      const api = useApiClient()
      currentReview.value = await api.get<ReviewRecord>(`/api/reviews/${reviewId}`)
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
      await sse.connect(`/api/reviews/${reviewId}/stream`, {
        onDone: (data) => {
          if (currentReview.value) {
            if (data.findings) {
              currentReview.value.findings = data.findings
              const score = data.findings.overall_score ?? 0
              currentReview.value.overall_score = score
              currentReview.value.summary = data.findings.summary
              currentReview.value.risk_level = score <= 45 ? 'high' : score <= 70 ? 'medium' : 'low'
            }
            currentReview.value.status = data.parse_error ? 'error' : 'completed'
            currentReview.value.provider_used = data.provider_used || currentReview.value.provider_used
            currentReview.value.token_usage = data.token_usage ?? currentReview.value.token_usage
          }
        },
        onError: (msg) => { error.value = msg },
      })
    } catch (e: any) {
      if (e.name === 'AbortError') return
      error.value = e.message
    } finally {
      isStreaming.value = false
    }
  }

  async function fetchReviews(contractId: number): Promise<ReviewRecord[]> {
    const api = useApiClient()
    return await api.get<ReviewRecord[]>(`/api/reviews/by-contract/${contractId}`)
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
