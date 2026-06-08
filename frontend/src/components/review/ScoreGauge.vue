<template>
  <div class="score-gauge">
    <div class="gauge-ring">
      <svg viewBox="0 0 100 100" class="ring-svg">
        <circle
          cx="50" cy="50" r="42"
          fill="none"
          stroke="#eee"
          stroke-width="8"
        />
        <circle
          cx="50" cy="50" r="42"
          fill="none"
          :stroke="color"
          stroke-width="8"
          stroke-linecap="round"
          :stroke-dasharray="`${(score / 100) * 264} 264`"
          transform="rotate(-90 50 50)"
          class="ring-progress"
        />
      </svg>
      <div class="score-text">
        <span class="score-num">{{ score }}</span>
        <span class="score-label">分</span>
      </div>
    </div>
    <div class="level-label">{{ levelLabel }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  score: number
  riskLevel?: string
}>()

const color = computed(() => {
  if (props.score >= 80) return '#2f9e44'
  if (props.score >= 60) return '#f08c00'
  return '#e03131'
})

const levelLabel = computed(() => {
  if (props.score >= 80) return '合同质量较好'
  if (props.score >= 60) return '存在一定风险'
  return '风险较高，需关注'
})
</script>

<style scoped>
.score-gauge {
  text-align: center;
}

.gauge-ring {
  position: relative;
  width: 100px;
  height: 100px;
  margin: 0 auto;
}

.ring-svg {
  width: 100%;
  height: 100%;
}

.ring-progress {
  transition: stroke-dasharray 0.6s ease;
}

.score-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

.score-num {
  font-size: 28px;
  font-weight: 700;
  color: #333;
}

.score-label {
  font-size: 14px;
  color: #999;
}

.level-label {
  margin-top: 8px;
  font-size: 13px;
  color: #666;
}
</style>
