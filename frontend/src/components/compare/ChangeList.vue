<template>
  <div class="change-list">
    <div class="list-header">
      <span class="list-title">变更摘要</span>
      <span class="list-count">{{ changes.length }} 条</span>
    </div>
    <n-scrollbar class="list-scroll">
      <div
        v-for="item in changes"
        :key="item.clause_id"
        class="change-item"
        :class="{ active: activeId === item.clause_id }"
        @click="$emit('select', item.clause_id)"
      >
        <div class="change-top">
          <span class="risk-badge" :class="'risk-' + item.risk">
            {{ riskLabel(item.risk) }}
          </span>
          <span class="change-type" :class="'type-' + item.change">
            {{ changeLabel(item.change) }}
          </span>
          <span class="change-clause">{{ item.title }}</span>
        </div>
        <div class="change-reason">{{ item.reason }}</div>
      </div>
      <div v-if="changes.length === 0" class="empty-hint">
        未检测到变更
      </div>
    </n-scrollbar>
  </div>
</template>

<script setup lang="ts">
import { NScrollbar } from 'naive-ui'

export interface ChangeItem {
  clause_id: string
  change: string   // 'modified' | 'added' | 'deleted'
  risk: string      // 'favorable' | 'neutral' | 'unfavorable' | 'unknown'
  reason: string
  title: string     // short display title
}

defineProps<{
  changes: ChangeItem[]
  activeId: string | null
}>()

defineEmits<{
  select: [clauseId: string]
}>()

function riskLabel(risk: string): string {
  switch (risk) {
    case 'favorable': return '有利'
    case 'unfavorable': return '不利'
    case 'neutral': return '中性'
    case 'unknown': return '未知'
    default: return risk
  }
}

function changeLabel(change: string): string {
  switch (change) {
    case 'modified': return '变更'
    case 'added': return '新增'
    case 'deleted': return '删除'
    default: return change
  }
}
</script>

<style scoped>
.change-list {
  width: 280px;
  min-width: 280px;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
}
.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  border-bottom: 1px solid #eee;
  background: #fafbfc;
}
.list-title {
  font-weight: 600;
  font-size: 14px;
}
.list-count {
  font-size: 12px;
  color: #999;
}
.list-scroll {
  flex: 1;
  height: 0;
}
.change-item {
  padding: 10px 16px;
  cursor: pointer;
  transition: background 0.15s;
  border-bottom: 1px solid #f0f0f0;
}
.change-item:hover {
  background: #fafbff;
}
.change-item.active {
  background: #f0f2ff;
  border-left: 3px solid #4C6EF5;
}
.change-top {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}
.change-type {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 3px;
}
.type-modified { background: #fff3cd; color: #856404; }
.type-added { background: #d1ecf1; color: #0c5460; }
.type-deleted { background: #f5f5f5; color: #999; }
.change-clause {
  font-size: 12px;
  color: #333;
  font-weight: 500;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.change-reason {
  font-size: 12px;
  color: #888;
  line-height: 1.5;
  padding-left: 2px;
}
.risk-badge {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: 500;
}
.risk-favorable { background: #d4edda; color: #155724; }
.risk-unfavorable { background: #f8d7da; color: #721c24; }
.risk-neutral { background: #fff3cd; color: #856404; }
.risk-unknown { background: #e2e3e5; color: #383d41; }
.empty-hint {
  text-align: center;
  color: #ccc;
  padding: 40px 0;
  font-size: 14px;
}
</style>
