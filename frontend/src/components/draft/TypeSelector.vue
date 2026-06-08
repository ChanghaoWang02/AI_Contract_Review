<template>
  <div class="type-selector">
    <h3>选择合同类型</h3>
    <div class="type-cards">
      <div
        v-for="t in CONTRACT_TYPES"
        :key="t.key"
        class="type-card"
        :class="{ selected: draft.contractType === t.key }"
        @click="draft.setContractType(t.key)"
      >
        <span class="type-icon">{{ t.icon }}</span>
        <span class="type-label">{{ t.label }}</span>
      </div>
    </div>
    <div class="step-actions">
      <n-button type="primary" :disabled="!draft.contractType" @click="draft.currentStep = 1">
        下一步
      </n-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { NButton } from 'naive-ui'
import { useDraftStore, CONTRACT_TYPES } from '@/stores/draft'

const draft = useDraftStore()
</script>

<style scoped>
.type-selector h3 { margin: 0 0 16px; }
.type-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
.type-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 20px 12px;
  border: 2px solid #e8e8e8;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
}
.type-card:hover { border-color: #c4ccff; background: #f5f6ff; }
.type-card.selected { border-color: #4C6EF5; background: #e8ebff; }
.type-icon { font-size: 32px; }
.type-label { font-size: 14px; font-weight: 500; }
.step-actions { margin-top: 24px; display: flex; justify-content: flex-end; }
</style>
