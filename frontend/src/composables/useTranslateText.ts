/**
 * 文本翻译 composable（审核报告等）
 * POST /api/translate/text (SSE)
 */
import { useMessage } from 'naive-ui'
import { useSSE } from '@/composables/useSSE'

export function useTranslateText() {
  const message = useMessage()
  const sse = useSSE()

  async function translateText(
    content: string,
    targetLang: string,
    sourceLang?: string,
  ): Promise<{
    content: string
    source_lang: string
    target_lang: string
  } | null> {
    sse.abort()
    let result = ''
    let detectedSource = sourceLang || ''
    let detectedTarget = targetLang

    try {
      await sse.connect('/api/translate/text', {
        onProgress: (data) => {
          detectedSource = data?.detected || detectedSource
        },
        onToken: (token) => { result += token },
        onDone: (data) => {
          result = data?.content || result
          detectedSource = data?.source_lang || detectedSource
          detectedTarget = data?.target_lang || detectedTarget
        },
        onError: (msg) => { throw new Error(msg) },
      }, {
        method: 'POST',
        body: {
          content,
          source_lang: sourceLang || null,
          target_lang: targetLang,
        },
      })
      return { content: result, source_lang: detectedSource, target_lang: detectedTarget }
    } catch (e: any) {
      if (e.name === 'AbortError') return null
      message.error(e.message || '文本翻译失败')
      return null
    }
  }

  return {
    isStreaming: sse.isStreaming,
    abort: sse.abort,
    translateText,
  }
}