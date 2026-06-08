<template>
  <div class="clause-card" :class="`risk-${clause.risk}`">
    <div class="card-header">
      <RiskBadge :level="clause.risk" />
      <span class="clause-summary">{{ clause.summary }}</span>
    </div>

    <div class="original-text">
      <div class="label">原文</div>
      <p>{{ clause.original_text }}</p>
    </div>

    <div v-if="clause.issues.length > 0" class="issues">
      <div class="label">发现的问题</div>
      <div v-for="(issue, i) in clause.issues" :key="i" class="issue-item">
        <n-tag size="tiny" :bordered="false" type="info">{{ issue.type }}</n-tag>
        <span>{{ issue.detail }}</span>
      </div>
    </div>

    <div v-if="clause.suggestions.length > 0" class="suggestions">
      <div class="label">修改建议</div>
      <ul>
        <li v-for="(s, i) in clause.suggestions" :key="i">{{ s }}</li>
      </ul>
    </div>

    <div v-if="clause.revised_text" class="revised">
      <div class="label">推荐修改后文本</div>
      <div class="revised-text">{{ clause.revised_text }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { NTag } from 'naive-ui'
import RiskBadge from './RiskBadge.vue'
import type { ClauseResult } from '@/stores/review'

defineProps<{
  clause: ClauseResult
}>()
</script>

<style scoped>
.clause-card {
  padding: 16px;
  margin-bottom: 12px;
  border-radius: 10px;
  border: 1px solid #e8e8e8;
  background: #fff;
}

.clause-card.risk-high {
  border-left: 3px solid #e03131;
}

.clause-card.risk-medium {
  border-left: 3px solid #f08c00;
}

.clause-card.risk-low {
  border-left: 3px solid #2f9e44;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.clause-summary {
  font-weight: 600;
  font-size: 15px;
}

.label {
  font-size: 12px;
  font-weight: 600;
  color: #999;
  text-transform: uppercase;
  margin-bottom: 6px;
}

.original-text p {
  font-size: 13px;
  color: #666;
  background: #f8f9fa;
  padding: 10px;
  border-radius: 6px;
  margin: 0;
  line-height: 1.6;
}

.issues {
  margin-top: 12px;
}

.issue-item {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin-bottom: 6px;
  font-size: 13px;
  line-height: 1.5;
}

.suggestions {
  margin-top: 12px;
}

.suggestions ul {
  margin: 0;
  padding-left: 18px;
}

.suggestions li {
  font-size: 13px;
  color: #2f9e44;
  margin-bottom: 4px;
  line-height: 1.5;
}

.revised {
  margin-top: 12px;
}

.revised-text {
  font-size: 13px;
  background: #f0f9f4;
  padding: 10px;
  border-radius: 6px;
  border: 1px solid #d3f0de;
  line-height: 1.6;
  color: #2f6e44;
}
</style>
