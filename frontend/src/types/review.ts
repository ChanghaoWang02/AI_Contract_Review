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