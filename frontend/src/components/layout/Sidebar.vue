<template>
  <nav class="sidebar">
    <div class="sidebar-header">
      <h2 class="logo">AI CONTRACT REVIEW</h2>
      <span class="subtitle">AI 合同审核</span>
    </div>

    <n-button
      type="primary"
      block
      :loading="loading"
      @click="$emit('upload')"
      class="upload-btn"
    >
      <template #icon>
        <n-icon><add-outline /></n-icon>
      </template>
      上传合同
    </n-button>

    <div class="nav-section">
      <div class="nav-title">合同列表</div>
      <n-scrollbar style="max-height: calc(100vh - 240px)">
        <div v-if="contracts.length === 0 && !loading" class="empty-hint">
          暂无合同，点击上方按钮上传
        </div>
        <div
          v-for="c in contracts"
          :key="c.id"
          class="contract-item"
          :class="{ active: c.id === activeId }"
          @click="$emit('select', c.id)"
        >
          <div class="contract-name">
            {{ c.original_filename }}
            <n-tag v-if="c.review_status === 'completed'" type="success" size="tiny" :bordered="false" class="review-tag">
              已审核
            </n-tag>
            <n-tag v-else-if="c.review_status === 'processing'" type="warning" size="tiny" :bordered="false" class="review-tag">
              未完成
            </n-tag>
            <n-tag v-else-if="c.review_status === 'error'" type="error" size="tiny" :bordered="false" class="review-tag">
              审核失败
            </n-tag>
            <n-tag v-else type="default" size="tiny" :bordered="false" class="review-tag">
              待审核
            </n-tag>
          </div>
          <div class="contract-meta">
            {{ formatDate(c.created_at) }}
            <span class="clause-count" v-if="c.clause_count">
              · {{ c.clause_count }}条
            </span>
          </div>
          <n-button
            text
            size="tiny"
            class="export-btn"
            @click.stop="handleExport(c.id)"
            :loading="exportingId === c.id"
          >
            <n-icon><download-outline /></n-icon>
          </n-button>
          <n-button
            text
            size="tiny"
            type="error"
            class="delete-btn"
            @click.stop="$emit('delete', c.id)"
          >
            <n-icon><trash-outline /></n-icon>
          </n-button>
        </div>
      </n-scrollbar>
    </div>

    <div class="sidebar-footer">
      <div class="nav-section" style="margin-bottom: 8px">
        <router-link to="/draft" class="nav-link draft-link">
          <n-icon><create-outline /></n-icon> 起草合同
        </router-link>
      </div>
      <router-link to="/rules" class="nav-link">
        <n-icon><settings-outline /></n-icon> 审核规则
      </router-link>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { NButton, NIcon, NScrollbar, NTag } from 'naive-ui'
import { AddOutline, TrashOutline, SettingsOutline, DownloadOutline, CreateOutline } from '@vicons/ionicons5'
import { useExportPDF } from '@/composables/useExportPDF'
import { useReviewStore } from '@/stores/review'
import type { Contract } from '@/stores/contract'

defineProps<{
  contracts: Contract[]
  activeId: number | null
  loading: boolean
}>()

defineEmits<{
  select: [id: number]
  upload: []
  delete: [id: number]
}>()

const { exporting, exportReviewPDF } = useExportPDF()
const reviewStore = useReviewStore()
const exportingId = ref<number | null>(null)

async function handleExport(contractId: number) {
  const reviews = await reviewStore.fetchReviews(contractId)
  const completed = reviews.filter((r) => r.status === 'completed')
  if (completed.length === 0) return
  exportingId.value = contractId
  await exportReviewPDF(completed[0].id)
  exportingId.value = null
}

function formatDate(dateStr: string): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`
}
</script>

<style scoped>
.sidebar {
  width: 240px;
  min-width: 240px;
  background: #fff;
  border-right: 1px solid #e8e8e8;
  display: flex;
  flex-direction: column;
  padding: 16px;
}

.sidebar-header {
  margin-bottom: 16px;
}
.logo {
  font-size: 22px;
  font-weight: 700;
  color: #4C6EF5;
  margin: 0;
}
.subtitle {
  font-size: 12px;
  color: #999;
}

.upload-btn {
  margin-bottom: 20px;
}

.nav-title {
  font-size: 13px;
  color: #999;
  margin-bottom: 8px;
  font-weight: 500;
}

.contract-item {
  position: relative;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  transition: background 0.15s;
}
.contract-item:hover {
  background: #f0f2ff;
}
.contract-item.active {
  background: #e8ebff;
  border: 1px solid #c4ccff;
}

.contract-name {
  font-size: 14px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding-right: 24px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.review-tag {
  flex-shrink: 0;
}
.contract-meta {
  font-size: 12px;
  color: #999;
  margin-top: 2px;
}

.export-btn {
  position: absolute;
  right: 28px;
  top: 8px;
  opacity: 0;
}
.contract-item:hover .export-btn {
  opacity: 1;
}

.delete-btn {
  position: absolute;
  right: 4px;
  top: 8px;
  opacity: 0;
}
.contract-item:hover .delete-btn {
  opacity: 1;
}

.empty-hint {
  text-align: center;
  color: #ccc;
  font-size: 13px;
  padding: 24px 0;
}

.sidebar-footer {
  margin-top: auto;
  padding-top: 12px;
  border-top: 1px solid #eee;
}
.nav-link {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: #666;
  text-decoration: none;
  padding: 8px;
  border-radius: 6px;
}
.nav-link:hover {
  background: #f5f5f5;
}
.draft-link {
  color: #4C6EF5;
  font-weight: 500;
}
.draft-link:hover {
  background: #e8ebff;
}
</style>
