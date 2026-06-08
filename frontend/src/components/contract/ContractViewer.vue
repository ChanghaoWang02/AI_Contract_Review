<template>
  <div class="contract-viewer">
    <div class="panel-header">
      <div class="header-title">
        <n-icon><document-text-outline /></n-icon>
        <span>合同原文</span>
      </div>
      <n-button text size="small" @click="$emit('close')">
        <n-icon><chevron-forward-outline /></n-icon>
      </n-button>
    </div>

    <div class="panel-body" v-if="contract">
      <div class="contract-info">
        <h3>{{ contract.original_filename }}</h3>
        <p class="meta">
          {{ contract.content_type.toUpperCase() }} ·
          {{ formatSize(contract.file_size) }} ·
          {{ contract.clause_count }} 个条款
        </p>
      </div>

      <n-divider />

      <n-scrollbar style="max-height: calc(100vh - 200px)">
        <div class="contract-content">
          <template v-if="clauseList.length > 0">
            <div
              v-for="(cls, i) in clauseList"
              :key="cls.id"
              class="clause-block"
              :class="{ clickable: true, highlighted: highlightedClause === cls.id }"
              @click="onClickClause(cls)"
            >
              <div class="clause-header">
                <span class="clause-num">{{ i + 1 }}</span>
                <span class="clause-title">{{ cls.title }}</span>
                <RiskBadge
                  v-if="getClauseRisk(cls.id)"
                  :level="getClauseRisk(cls.id)!"
                  size="small"
                />
              </div>
              <div class="clause-text">{{ cls.content }}</div>
            </div>
          </template>
          <div v-else class="raw-text">
            {{ contract.content }}
          </div>
        </div>
      </n-scrollbar>
    </div>

    <div v-else class="empty-panel">
      <p>暂无合同内容</p>
      <p class="hint">上传合同并选中以查看原文</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { NIcon, NButton, NDivider, NScrollbar } from 'naive-ui'
import { DocumentTextOutline, ChevronForwardOutline } from '@vicons/ionicons5'
import { ContractChunkerClient } from '@/core/chunker'
import RiskBadge from '@/components/review/RiskBadge.vue'
import type { ContractDetail } from '@/stores/contract'
import type { Findings } from '@/stores/review'

const props = defineProps<{
  contract: ContractDetail | null
  findings?: Findings | null
}>()

const emit = defineEmits<{
  close: []
  clauseClick: [clauseId: string, clauseText: string]
}>()

const highlightedClause = ref<string | null>(null)

interface LocalClause {
  id: string
  title: string
  content: string
}

const clauseList = computed<LocalClause[]>(() => {
  if (!props.contract?.content) return []
  return ContractChunkerClient.split(props.contract.content)
})

function getClauseRisk(clauseId: string): string | null {
  if (!props.findings?.clauses) return null
  const found = props.findings.clauses.find((c) => c.id === clauseId)
  return found?.risk || null
}

function onClickClause(cls: LocalClause) {
  highlightedClause.value = cls.id
  emit('clauseClick', cls.id, cls.content)
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
}
</script>

<style scoped>
.contract-viewer {
  width: 360px;
  min-width: 360px;
  background: #fff;
  border-left: 1px solid #e8e8e8;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #eee;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 15px;
}

.panel-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 0 16px;
}

.contract-info h3 {
  margin: 12px 0 4px;
  font-size: 15px;
}
.meta {
  font-size: 12px;
  color: #999;
  margin: 0;
}

.contract-content {
  padding-bottom: 24px;
}

.clause-block {
  padding: 12px;
  margin-bottom: 8px;
  border: 1px solid #eee;
  border-radius: 8px;
  transition: all 0.15s;
}

.clause-block.clickable {
  cursor: pointer;
}

.clause-block:hover {
  border-color: #c4ccff;
  background: #fafbff;
}

.clause-block.highlighted {
  border-color: #4C6EF5;
  background: #f0f2ff;
}

.clause-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.clause-num {
  background: #4C6EF5;
  color: #fff;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  flex-shrink: 0;
}

.clause-title {
  font-size: 14px;
  font-weight: 600;
  flex: 1;
}

.clause-text {
  font-size: 13px;
  color: #555;
  line-height: 1.7;
  max-height: 120px;
  overflow: hidden;
  position: relative;
}

.clause-text::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 40px;
  background: linear-gradient(transparent, #fff);
}

.raw-text {
  font-size: 14px;
  line-height: 1.8;
  white-space: pre-wrap;
  color: #333;
}

.empty-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #ccc;
}
.hint {
  font-size: 13px;
}
</style>
