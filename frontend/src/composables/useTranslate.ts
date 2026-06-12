/**
 * 合同翻译 composable — backward-compat re-exports
 * 新代码应直接 import 具体的 composable：
 *   useTranslateContract / useRetranslateClause / useTranslateText
 */
import { useMessage } from 'naive-ui'
import { useTranslateContract } from './useTranslateContract'
import { useRetranslateClause } from './useRetranslateClause'
import { useTranslateText } from './useTranslateText'

// Re-export 新 composables
export { useTranslateContract } from './useTranslateContract'
export { useRetranslateClause } from './useRetranslateClause'
export { useTranslateText } from './useTranslateText'

// backward compat: useTranslate() 返回的对象结构不变
export function useTranslate() {
  const message = useMessage()
  const contract = useTranslateContract()
  const clause = useRetranslateClause()
  const text = useTranslateText()

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
    isStreaming: contract.isStreaming,
    abort: contract.abort,
    translateContract: contract.translateContract,
    retranslateClause: clause.retranslateClause,
    translateText: text.translateText,
    saveTranslation,
  }
}