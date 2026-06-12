/**
 * 合同全文逐条翻译 composable
 * POST /api/translate/generate (SSE)
 */
import { useMessage } from 'naive-ui'
import { useSSE } from '@/composables/useSSE'
import { useTranslateStore } from '@/stores/translate'
import { ContractChunkerClient } from '@/core/chunker'

export function useTranslateContract() {
  const store = useTranslateStore()
  const message = useMessage()
  const sse = useSSE()

  async function translateContract(
    cId: number,
    content: string,
    tgtLang: string = 'zh',
  ): Promise<boolean> {
    sse.abort()
    store.startSession(cId, tgtLang)

    // 前端预分块，用于显示原文
    try {
      const chunks = ContractChunkerClient.split(content)
      store.initClauses(
        chunks.map((c) => ({
          index: c.index,
          id: c.id,
          title: c.title,
          content: c.content,
        })),
      )
    } catch {
      message.error('合同条款解析失败')
      return false
    }

    try {
      await sse.connect('/api/translate/generate', {
        onEvent: (event, data) => {
          if (event === 'progress' && data.stage === 'detect') {
            store.setSourceInfo(data.detected, data.tier)
          } else if (event === 'token' && data.clause_index !== undefined) {
            store.updateClauseToken(data.clause_index, data.content || '')
          } else if (event === 'clause_done') {
            store.markClauseDone(data.clause_index, data)
          } else if (event === 'clause_error') {
            store.markClauseError(data.clause_index, data.error || '翻译失败')
          } else if (event === 'done') {
            store.finishSession(data)
          } else if (event === 'error') {
            store.error = typeof data === 'string' ? data : data?.message || '翻译失败'
          }
        },
        onError: (msg) => {
          store.error = msg
          message.error(msg)
        },
      }, {
        method: 'POST',
        body: { contract_id: cId, target_lang: tgtLang },
      })
      return true
    } catch (e: any) {
      if (e.name === 'AbortError') return false
      const msg = e.message || '翻译失败'
      store.error = msg
      message.error(msg)
      return false
    }
  }

  return {
    isStreaming: sse.isStreaming,
    abort: sse.abort,
    translateContract,
  }
}