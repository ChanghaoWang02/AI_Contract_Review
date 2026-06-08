<template>
  <div class="rule-list">
    <n-spin :show="loading">
      <n-empty v-if="!loading && rules.length === 0" description="暂无审核规则" />

      <div v-for="rule in rules" :key="rule.id" class="rule-item">
        <div class="rule-info">
          <div class="rule-name">
            {{ rule.name }}
            <n-tag
              :type="rule.category === 'system' ? 'info' : 'default'"
              size="tiny"
              :bordered="false"
            >
              {{ rule.category === 'system' ? '系统' : '自定义' }}
            </n-tag>
            <n-tag
              :type="rule.is_active ? 'success' : 'default'"
              size="tiny"
              :bordered="false"
            >
              {{ rule.is_active ? '启用' : '停用' }}
            </n-tag>
          </div>
          <div class="rule-prompt">{{ rule.prompt_template }}</div>
        </div>
        <div class="rule-actions">
          <n-button text size="small" @click="$emit('toggle', rule)">
            {{ rule.is_active ? '停用' : '启用' }}
          </n-button>
          <n-button
            text size="small"
            @click="$emit('edit', rule)"
            :disabled="rule.category === 'system'"
          >
            编辑
          </n-button>
          <n-button
            text size="small"
            type="error"
            @click="$emit('delete', rule)"
            :disabled="rule.category === 'system'"
          >
            删除
          </n-button>
        </div>
      </div>
    </n-spin>
  </div>
</template>

<script setup lang="ts">
import { NSpin, NEmpty, NTag, NButton } from 'naive-ui'

defineProps<{
  rules: any[]
  loading: boolean
}>()

defineEmits<{
  edit: [rule: any]
  toggle: [rule: any]
  delete: [rule: any]
}>()
</script>

<style scoped>
.rule-item {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 14px 16px;
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 10px;
  margin-bottom: 8px;
}
.rule-info { flex: 1; }
.rule-name {
  font-weight: 600;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.rule-prompt {
  font-size: 13px;
  color: #888;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.rule-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
  margin-left: 16px;
}
</style>
