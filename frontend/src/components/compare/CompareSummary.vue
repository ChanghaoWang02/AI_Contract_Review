<template>
  <div class="compare-summary">
    <div class="summary-stats">
      <div class="stat-item">
        <span class="stat-value">{{ stats.total }}</span>
        <span class="stat-label">总变更</span>
      </div>
      <div class="stat-divider" />
      <div class="stat-item favorable">
        <span class="stat-value">{{ stats.favorable }}</span>
        <span class="stat-label">有利</span>
      </div>
      <div class="stat-item unfavorable">
        <span class="stat-value">{{ stats.unfavorable }}</span>
        <span class="stat-label">不利</span>
      </div>
      <div class="stat-item neutral">
        <span class="stat-value">{{ stats.neutral }}</span>
        <span class="stat-label">中性</span>
      </div>
      <div v-if="stats.added > 0 || stats.deleted > 0" class="stat-divider" />
      <div v-if="stats.added > 0" class="stat-item added">
        <span class="stat-value">{{ stats.added }}</span>
        <span class="stat-label">新增</span>
      </div>
      <div v-if="stats.deleted > 0" class="stat-item deleted">
        <span class="stat-value">{{ stats.deleted }}</span>
        <span class="stat-label">删除</span>
      </div>
    </div>
    <div class="summary-meta">
      <span class="perspective-tag">
        视角：{{ perspectiveLabel }}
      </span>
      <span v-if="stats.token_usage > 0" class="token-info">
        Tokens: {{ stats.token_usage }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

export interface CompareStats {
  total: number
  modified: number
  added: number
  deleted: number
  favorable: number
  neutral: number
  unfavorable: number
  unknown: number
  token_usage: number
}

const props = defineProps<{
  stats: CompareStats
  perspective: string
}>()

const perspectiveLabel = computed(() => {
  switch (props.perspective) {
    case 'party_a': return '甲方'
    case 'party_b': return '乙方'
    case 'neutral': return '中立'
    default: return props.perspective
  }
})
</script>

<style scoped>
.compare-summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background: #fafbfc;
  border-top: 1px solid #eee;
  flex-shrink: 0;
}
.summary-stats {
  display: flex;
  align-items: center;
  gap: 12px;
}
.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
}
.stat-value {
  font-weight: 600;
  font-size: 15px;
}
.stat-label {
  font-size: 12px;
  color: #999;
}
.favorable .stat-value { color: #155724; }
.unfavorable .stat-value { color: #721c24; }
.neutral .stat-value { color: #856404; }
.added .stat-value { color: #0c5460; }
.deleted .stat-value { color: #999; }
.stat-divider {
  width: 1px;
  height: 24px;
  background: #e0e0e0;
}
.summary-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}
.perspective-tag {
  font-size: 12px;
  padding: 2px 8px;
  background: #e8ecf1;
  border-radius: 3px;
  color: #666;
}
.token-info {
  font-size: 12px;
  color: #aaa;
}
</style>
