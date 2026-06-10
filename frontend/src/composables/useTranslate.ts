/**
 * 合同翻译 composable
 * SSE 流式翻译 + 单条重翻 + 文本翻译 + 保存
 */
import { ref } from 'vue'
import { useMessage } from 'naive-ui'
import { useTranslateStore } from '@/stores/translate'
import { ContractChunkerClient } from '@/core/chunker'

export function useTranslate() {
  const store = useTranslateStore()
  const message = useMessage()
  const abortController = ref<AbortController | null>(null)
  const isStreaming = ref(false)

  function abort() {
    if (abortController.value) {
      abortController.value.abort()
      abortController.value = null
    }
    isStreaming.value = false
  }

  /** SSE 事件处理 */
  function handleSSEEvent(payload: any) {
    const event = payload.event
    const data = payload.data

    switch (event) {
      case 'progress': {
        if (data.stage === 'detect') {
          store.setSourceInfo(data.detected, data.tier)
        } else if (data.stage === 'chunked') {
          // 预分配 clauses 占位（实际内容由 token/clause_done 填充）
          // initClauses 在 startTranslate 中调用
        }
        break
      }
      case 'token': {
        if (data.clause_index !== undefined) {
          store.updateClauseToken(data.clause_index, data.content || '')
        }
        break
      }
      case 'clause_done': {
        store.markClauseDone(data.clause_index, data)
        break
      }
      case 'clause_error': {
        store.markClauseError(
          data.clause_index,
          data.error || '翻译失败',
        )
        break
      }
      case 'done': {
        store.finishSession(data)
        isStreaming.value = false
        break
      }
      case 'error': {
        store.error = typeof data === 'string' ? data : data?.message || '翻译失败'
        isStreaming.value = false
        break
      }
    }
  }

  /** 通用 SSE 读取循环 */
  async function readSSEStream(res: Response): Promise<void> {
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
        if (!line.startsWith('data: ')) continue
        try {
          const payload = JSON.parse(line.slice(6))
          handleSSEEvent(payload)
        } catch {
          // 忽略无法解析的行
        }
      }
    }
  }

  /**
   * 合同全文逐条翻译
   * POST /api/translate/generate (SSE)
   */
  async function translateContract(
    cId: number,
    content: string,
    tgtLang: string = 'zh',
  ): Promise<boolean> {
    abort()
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

    const controller = new AbortController()
    abortController.value = controller
    isStreaming.value = true

    try {
      const res = await fetch('/api/translate/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        },
        body: JSON.stringify({
          contract_id: cId,
          target_lang: tgtLang,
        }),
        signal: controller.signal,
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: '翻译请求失败' }))
        throw new Error(err.detail || `请求失败 (HTTP ${res.status})`)
      }

      await readSSEStream(res)
      return true
    } catch (e: any) {
      if (e.name === 'AbortError') return false
      store.error = e.message || '翻译失败'
      message.error(store.error)
      return false
    } finally {
      isStreaming.value = false
      if (abortController.value === controller) {
        abortController.value = null
      }
    }
  }

  /**
   * 单条条款重新翻译
   * POST /api/translate/clause (SSE)
   */
  async function retranslateClause(
    cId: number,
    clauseIndex: number,
    originalText: string,
    instruction?: string,
  ): Promise<string | null> {
    abort()

    const controller = new AbortController()
    abortController.value = controller
    let result = ''

    try {
      const res = await fetch('/api/translate/clause', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        },
        body: JSON.stringify({
          contract_id: cId,
          clause_index: clauseIndex,
          original_text: originalText,
          instruction: instruction || '',
        }),
        signal: controller.signal,
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: '重翻失败' }))
        throw new Error(err.detail || `请求失败 (HTTP ${res.status})`)
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
          if (!line.startsWith('data: ')) continue
          try {
            const payload = JSON.parse(line.slice(6))
            if (payload.event === 'token') {
              result += payload.data || ''
            } else if (payload.event === 'done') {
              result = payload.data?.translated || result
            } else if (payload.event === 'error') {
              throw new Error(
                typeof payload.data === 'string'
                  ? payload.data
                  : payload.data?.error || '重翻失败',
              )
            }
          } catch {
            // 忽略
          }
        }
      }

      return result || null
    } catch (e: any) {
      if (e.name === 'AbortError') return null
      message.error(e.message || '重翻失败')
      return null
    } finally {
      if (abortController.value === controller) {
        abortController.value = null
      }
    }
  }

  /**
   * 文本翻译（审核报告等）
   * POST /api/translate/text (SSE)
   * 返回 { content, source_lang, target_lang } 或 null
   */
  async function translateText(
    content: string,
    targetLang: string,
    sourceLang?: string,
  ): Promise<{
    content: string
    source_lang: string
    target_lang: string
  } | null> {
    abort()

    const controller = new AbortController()
    abortController.value = controller
    isStreaming.value = true
    let result = ''
    let detectedSource = sourceLang || ''
    let detectedTarget = targetLang

    try {
      const res = await fetch('/api/translate/text', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        },
        body: JSON.stringify({
          content,
          source_lang: sourceLang || null,
          target_lang: targetLang,
        }),
        signal: controller.signal,
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: '文本翻译失败' }))
        throw new Error(err.detail || `请求失败 (HTTP ${res.status})`)
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
          if (!line.startsWith('data: ')) continue
          try {
            const payload = JSON.parse(line.slice(6))
            if (payload.event === 'progress') {
              detectedSource = payload.data?.detected || detectedSource
            } else if (payload.event === 'token') {
              result += payload.data || ''
            } else if (payload.event === 'done') {
              result = payload.data?.content || result
              detectedSource = payload.data?.source_lang || detectedSource
              detectedTarget = payload.data?.target_lang || detectedTarget
            } else if (payload.event === 'error') {
              throw new Error(
                typeof payload.data === 'string'
                  ? payload.data
                  : payload.data?.error || '文本翻译失败',
              )
            }
          } catch {
            // 忽略
          }
        }
      }

      return {
        content: result,
        source_lang: detectedSource,
        target_lang: detectedTarget,
      }
    } catch (e: any) {
      if (e.name === 'AbortError') return null
      message.error(e.message || '文本翻译失败')
      return null
    } finally {
      isStreaming.value = false
      if (abortController.value === controller) {
        abortController.value = null
      }
    }
  }

  /**
   * 保存译文为子合同
   * POST /api/translate/save (JSON)
   */
  async function saveTranslation(
    cId: number,
    translatedContent: string,
    srcLang: string,
    tgtLang: string,
    filename: string,
  ): Promise<{ id: number; clause_count: number } | null> {
    try {
      const res = await fetch('/api/translate/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contract_id: cId,
          translated_content: translatedContent,
          source_lang: srcLang,
          target_lang: tgtLang,
          filename,
        }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: '保存失败' }))
        throw new Error(err.detail || '保存失败')
      }

      const data = await res.json()
      message.success('译文已保存为合同')
      return data
    } catch (e: any) {
      message.error(e.message || '保存失败')
      return null
    }
  }

  return {
    isStreaming,
    abort,
    translateContract,
    retranslateClause,
    translateText,
    saveTranslation,
  }
}
