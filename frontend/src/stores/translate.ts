import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface TranslateClause {
  index: number
  clauseId: string
  original: string
  translated: string
  status: 'pending' | 'streaming' | 'done' | 'error'
  errorMsg?: string
}

export type SessionState = 'idle' | 'ready' | 'translating' | 'done'

export const useTranslateStore = defineStore('translate', () => {
  // ── 状态 ──
  const sessionState = ref<SessionState>('idle')
  const contractId = ref<number | null>(null)
  const clauses = ref<TranslateClause[]>([])
  const targetLang = ref('zh')
  const sourceLang = ref<string | null>(null)
  const tier = ref(1)
  const error = ref<string | null>(null)
  const skippedClauses = ref<Array<{ clause_index: number; error: string }>>([])

  // ── 计算属性 ──
  const totalCount = computed(() => clauses.value.length)
  const completedCount = computed(() => clauses.value.filter((c) => c.status === 'done').length)
  const isTranslating = computed(() => sessionState.value === 'translating')
  const hasError = computed(() => error.value !== null)
  const translatedText = computed(() =>
    clauses.value.map((c) => c.translated).join('\n\n')
  )

  // ── 操作 ──
  function startSession(cId: number, tgtLang?: string) {
    sessionState.value = 'ready'
    contractId.value = cId
    targetLang.value = tgtLang || 'zh'
    sourceLang.value = null
    tier.value = 1
    error.value = null
    clauses.value = []
    skippedClauses.value = []
  }

  function initClauses(
    raw: Array<{ index: number; id: string; title: string; content: string }>,
  ) {
    clauses.value = raw.map((c) => ({
      index: c.index,
      clauseId: c.id,
      original: c.content,
      translated: '',
      status: 'pending' as const,
    }))
    sessionState.value = 'translating'
  }

  function updateClauseToken(index: number, token: string) {
    const clause = clauses.value.find((c) => c.index === index)
    if (clause) {
      clause.translated += token
      if (clause.status === 'pending') {
        clause.status = 'streaming'
      }
    }
  }

  function markClauseDone(index: number, data: { clause_id: string; original: string; translated: string }) {
    const clause = clauses.value.find((c) => c.index === index)
    if (clause) {
      clause.status = 'done'
      clause.translated = data.translated
    }
  }

  function markClauseError(index: number, errMsg: string) {
    const clause = clauses.value.find((c) => c.index === index)
    if (clause) {
      clause.status = 'error'
      clause.errorMsg = errMsg
    }
  }

  function finishSession(data: {
    total_clauses: number
    translated: number
    skipped_clauses?: Array<{ clause_index: number; error: string }>
    source_lang: string
    target_lang: string
  }) {
    sessionState.value = 'done'
    sourceLang.value = data.source_lang
    targetLang.value = data.target_lang
    if (data.skipped_clauses) {
      skippedClauses.value = data.skipped_clauses
    }
  }

  function setSourceInfo(lang: string, t: number) {
    sourceLang.value = lang
    tier.value = t
  }

  function reset() {
    sessionState.value = 'idle'
    contractId.value = null
    clauses.value = []
    sourceLang.value = null
    tier.value = 1
    error.value = null
    skippedClauses.value = []
  }

  return {
    sessionState,
    contractId,
    clauses,
    targetLang,
    sourceLang,
    tier,
    error,
    skippedClauses,
    totalCount,
    completedCount,
    isTranslating,
    hasError,
    translatedText,
    startSession,
    initClauses,
    updateClauseToken,
    markClauseDone,
    markClauseError,
    finishSession,
    setSourceInfo,
    reset,
  }
})
