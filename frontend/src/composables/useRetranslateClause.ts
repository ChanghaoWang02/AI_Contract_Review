/**
 * 单条条款重新翻译 composable
 * POST /api/translate/clause (SSE)
 */
import { useMessage } from 'naive-ui'
import { useSSE } from '@/composables/useSSE'

export function useRetranslateClause() {
  const message = useMessage()
  const sse = useSSE()

  async function retranslateClause(
    cId: number,
    clauseIndex: number,
    originalText: string,
    targetLang: string,
    instruction?: string,
  ): Promise<string | null> {
    sse.abort()
    let result = ''

    try {
      await sse.connect('/api/translate/clause', {
        onToken: (token) => { result += token },
        onDone: (data) => { result = data?.translated || result },
        onError: (msg) => { throw new Error(msg) },
      }, {
        method: 'POST',
        body: {
          contract_id: cId,
          clause_index: clauseIndex,
          original_text: originalText,
          target_lang: targetLang,
          instruction: instruction || '',
        },
      })
      return result || null
    } catch (e: any) {
      if (e.name === 'AbortError') return null
      message.error(e.message || '重翻失败')
      return null
    }
  }

  return {
    isStreaming: sse.isStreaming,
    abort: sse.abort,
    retranslateClause,
  }
}