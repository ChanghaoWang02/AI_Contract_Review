<template>
  <div class="review-report">
    <h3>审核报告</h3>

    <!-- 总览 -->
    <div class="overview">
      <ScoreGauge :score="overallScore" />
      <div class="overview-text">
        <div class="risk-info">
          <RiskBadge :level="riskLevel || 'medium'" size="medium" />
          <span class="risk-summary">{{ summaryText }}</span>
        </div>
        <div class="stats">
          <div class="stat">
            <span class="stat-num">{{ findings.clauses.length }}</span>
            <span class="stat-label">审核条款</span>
          </div>
          <div class="stat">
            <span class="stat-num high">{{ highCount }}</span>
            <span class="stat-label">高风险</span>
          </div>
          <div class="stat">
            <span class="stat-num medium">{{ mediumCount }}</span>
            <span class="stat-label">中风险</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 摘要 -->
    <n-alert type="info" class="summary-alert">
      {{ findings.summary }}
    </n-alert>

    <!-- 逐条分析 -->
    <ClauseCard
      v-for="clause in findings.clauses"
      :key="clause.id"
      :clause="clause"
    />

    <!-- 导出按钮 -->
    <div class="export-section">
      <n-button type="primary" :loading="exporting" @click="doExport">
        <template #icon>
          <n-icon><download-outline /></n-icon>
        </template>
        导出审核报告
      </n-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { NAlert, NButton, NIcon } from 'naive-ui'
import { DownloadOutline } from '@vicons/ionicons5'
import RiskBadge from './RiskBadge.vue'
import ScoreGauge from './ScoreGauge.vue'
import ClauseCard from './ClauseCard.vue'
import { useExportPDF } from '@/composables/useExportPDF'
import type { Findings } from '@/stores/review'

const props = defineProps<{
  findings: Findings
  riskLevel?: string
  overallScore: number
  reviewId: number
}>()

const { exporting, exportReviewPDF } = useExportPDF()

async function doExport() {
  await exportReviewPDF(props.reviewId)
}

const highCount = computed(() =>
  props.findings.clauses.filter((c) => c.risk === 'high').length
)

const mediumCount = computed(() =>
  props.findings.clauses.filter((c) => c.risk === 'medium').length
)

const summaryText = computed(() => {
  if (props.riskLevel === 'high') return '合同存在重大风险，建议重点关注高风险条款。'
  if (props.riskLevel === 'medium') return '合同整体可接受，但存在需关注的条款。'
  return '合同整体合规，风险可控。'
})
</script>

<style scoped>
.review-report {
  background: #fff;
  border-radius: 8px;
  padding: 24px;
}

.review-report h3 {
  margin: 0 0 16px;
  font-size: 18px;
}

.overview {
  display: flex;
  gap: 24px;
  align-items: center;
  margin-bottom: 16px;
}

.overview-text {
  flex: 1;
}

.risk-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.risk-summary {
  font-size: 14px;
  color: #555;
}

.stats {
  display: flex;
  gap: 16px;
}

.stat {
  text-align: center;
}

.stat-num {
  display: block;
  font-size: 22px;
  font-weight: 700;
  color: #333;
}

.stat-num.high { color: #e03131; }
.stat-num.medium { color: #f08c00; }

.stat-label {
  font-size: 12px;
  color: #999;
}

.summary-alert {
  margin-bottom: 16px;
}

.export-section {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #eee;
  text-align: center;
}
</style>
