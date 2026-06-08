/**
 * 前端合同条款分割器
 * 与后端 Python ContractChunker 保持一致的分割逻辑
 */

export interface Clause {
  id: string
  title: string
  content: string
  index: number
}

const CLAUSE_PATTERNS = [
  /^第[一二三四五六七八九十百千\d]+[条章节款]/,
  /^[一二三四五六七八九十]+[、，．.]/,
  /^[(（][一二三四五六七八九十\d]+[)）]/,
  /^\d+[\.、\)）]\s*/,
  /^(甲方|乙方|卖方|买方|违约责任|争议解决|保密|知识产权|合同标的|付款|交付|验收|质量|期限|终止|解除|不可抗力|通知|送达|管辖|法律适用)/,
]

export class ContractChunkerClient {
  static split(text: string, minClauseLength: number = 20): Clause[] {
    const lines = text.split('\n')
    const clauses: Clause[] = []

    let currentTitle = '首部'
    let currentLines: string[] = []
    let clauseIndex = 0

    for (const line of lines) {
      const stripped = line.trim()
      if (!stripped) continue

      let isNewClause = false
      for (const pattern of CLAUSE_PATTERNS) {
        if (pattern.test(stripped)) {
          isNewClause = true
          break
        }
      }

      if (isNewClause && currentLines.length > 0) {
        const content = currentLines.join('\n').trim()
        if (content.length >= minClauseLength) {
          clauses.push({
            id: `clause_${clauseIndex}`,
            title: currentTitle,
            content,
            index: clauseIndex,
          })
          clauseIndex++
        }
        currentTitle = stripped.slice(0, 60)
        currentLines = [stripped]
      } else {
        currentLines.push(stripped)
      }
    }

    // Last clause
    if (currentLines.length > 0) {
      const content = currentLines.join('\n').trim()
      if (content.length >= minClauseLength) {
        clauses.push({
          id: `clause_${clauseIndex}`,
          title: currentTitle,
          content,
          index: clauseIndex,
        })
      }
    }

    if (clauses.length === 0) {
      clauses.push({
        id: 'clause_0',
        title: '合同全文',
        content: text.trim(),
        index: 0,
      })
    }

    return clauses
  }
}
