<template>
  <div class="compare-panel">
    <div class="panel-header">
      <span class="panel-label">{{ label }}</span>
      <span class="clause-count">{{ clauses.length }} 条</span>
    </div>
    <n-scrollbar ref="scrollRef" class="panel-scroll">
      <div
        v-for="(clause, i) in clauses"
        :key="clause.id"
        class="clause-row"
        :class="[getHighlightClass(clause.id), { active: activeId === clause.id }]"
        :data-clause-id="clause.id"
        @click="$emit('clauseClick', clause.id)"
      >
        <div class="clause-num">{{ i + 1 }}</div>
        <div class="clause-body">
          <div class="clause-title">{{ clause.title }}</div>
          <div class="clause-text">{{ clause.text }}</div>
          <div
            v-if="clause.changeLabel"
            class="clause-change-tag"
            :class="'tag-' + clause.change"
          >
            {{ clause.changeLabel }}
          </div>
        </div>
      </div>
      <div v-if="clauses.length === 0" class="empty-hint">
        暂无条款
      </div>
    </n-scrollbar>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { NScrollbar } from 'naive-ui'

export interface ClauseDisplay {
  id: string
  title: string
  text: string
  change?: string        // 'modified' | 'added' | 'deleted'
  changeLabel?: string    // 显示标签
  risk?: string           // 'favorable' | 'neutral' | 'unfavorable' | 'unknown'
}

const props = defineProps<{
  label: string
  clauses: ClauseDisplay[]
  activeId: string | null
  highlightMap: Record<string, string>  // clause_id → risk color
}>()

const emit = defineEmits<{
  clauseClick: [clauseId: string]
}>()

const scrollRef = ref<InstanceType<typeof NScrollbar> | null>(null)

function getHighlightClass(clauseId: string): string {
  const risk = props.highlightMap[clauseId]
  return risk ? `highlight-${risk}` : ''
}

function scrollTo(clauseId: string) {
  // exposed for parent to call
  const el = (scrollRef.value?.$el as HTMLElement)?.querySelector(
    `[data-clause-id="${clauseId}"]`
  )
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

defineExpose({ scrollTo })
</script>

<style scoped>
.compare-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  min-width: 0;
}
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  border-bottom: 1px solid #eee;
  background: #fafbfc;
}
.panel-label {
  font-weight: 600;
  font-size: 14px;
}
.clause-count {
  font-size: 12px;
  color: #999;
}
.panel-scroll {
  flex: 1;
  height: 0;
}
.clause-row {
  display: flex;
  gap: 10px;
  padding: 10px 16px;
  cursor: pointer;
  transition: background 0.15s;
  border-bottom: 1px solid #f0f0f0;
}
.clause-row:hover {
  background: #fafbff;
}
.clause-row.active {
  background: #f0f2ff;
  border-left: 3px solid #4C6EF5;
}
.clause-num {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #e8ecf1;
  color: #666;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  flex-shrink: 0;
  margin-top: 2px;
}
.clause-body {
  flex: 1;
  min-width: 0;
}
.clause-title {
  font-size: 13px;
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
}
.clause-text {
  font-size: 12px;
  color: #666;
  line-height: 1.6;
  max-height: 80px;
  overflow: hidden;
  position: relative;
}
.clause-text::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 30px;
  background: linear-gradient(transparent, #fff);
}
.clause-change-tag {
  display: inline-block;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 3px;
  margin-top: 4px;
}
.tag-modified { background: #fff3cd; color: #856404; }
.tag-added { background: #d1ecf1; color: #0c5460; }
.tag-deleted { background: #f5f5f5; color: #999; }

/* highlight colors */
.highlight-favorable .clause-text { background: #f0fff0; }
.highlight-unfavorable .clause-text { background: #fff0f0; }
.highlight-neutral .clause-text { background: #fffff0; }
.highlight-unknown .clause-text { background: #fafafa; }

.empty-hint {
  text-align: center;
  color: #ccc;
  padding: 40px 0;
}
</style>
