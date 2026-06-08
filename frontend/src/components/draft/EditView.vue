<template>
  <div class="edit-view">
    <div class="edit-layout">
      <!-- 左侧：条款预览 -->
      <div class="clause-preview">
        <h4>合同预览</h4>
        <div class="clause-list">
          <div
            v-for="(clause, i) in clauses"
            :key="i"
            class="clause-item"
            :class="{ anchored: anchoredIndex === i }"
            @click="selectClause(i)"
          >
            <div class="clause-title">{{ clause.title }}</div>
            <div class="clause-body">{{ clause.body }}</div>
          </div>
          <n-empty v-if="clauses.length === 0" description="无法解析合同条款" />
        </div>
      </div>

      <!-- 右侧：聊天面板 -->
      <div class="chat-area">
        <DraftChatPanel
          :anchored-clause="anchoredClause"
          :clause-titles="clauseTitles"
          @clause-revised="onClauseRevised"
        />
      </div>
    </div>

    <div class="step-actions">
      <n-button @click="draft.currentStep = 2">上一步</n-button>
      <n-button type="primary" @click="draft.currentStep = 4">保存合同</n-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { NButton, NEmpty } from 'naive-ui'
import { useDraftStore } from '@/stores/draft'
import DraftChatPanel from './DraftChatPanel.vue'

const draft = useDraftStore()

interface ClauseItem {
  title: string
  body: string
}

const clauses = ref<ClauseItem[]>([])
const anchoredIndex = ref<number | null>(null)

const anchoredClause = computed(() => {
  if (anchoredIndex.value === null || !clauses.value[anchoredIndex.value]) return null
  const c = clauses.value[anchoredIndex.value]
  return c.title + '\n' + c.body
})

const clauseTitles = computed(() => clauses.value.map(c => c.title))

function parseClauses(text: string): ClauseItem[] {
  // 按「第X条」切分
  const parts = text.split(/(?=第[一二三四五六七八九十百千]+条\s)/)
  const result: ClauseItem[] = []
  for (const part of parts) {
    const trimmed = part.trim()
    if (!trimmed) continue
    const newlineIdx = trimmed.indexOf('\n')
    if (newlineIdx > 0) {
      result.push({
        title: trimmed.slice(0, newlineIdx).trim(),
        body: trimmed.slice(newlineIdx + 1).trim(),
      })
    } else {
      // 降级：整个作为一条
      result.push({ title: trimmed.slice(0, 30), body: trimmed })
    }
  }
  return result.length > 0 ? result : [{ title: '全文', body: text }]
}

function selectClause(index: number) {
  anchoredIndex.value = anchoredIndex.value === index ? null : index
}

function onClauseRevised(revisedClause: string) {
  if (anchoredIndex.value !== null && clauses.value[anchoredIndex.value]) {
    // 替换该条款
    clauses.value[anchoredIndex.value] = {
      title: clauses.value[anchoredIndex.value].title,
      body: revisedClause.replace(clauses.value[anchoredIndex.value].title + '\n', '').replace(clauses.value[anchoredIndex.value].title, ''),
    }
    // 更新完整合同文本
    draft.setGeneratedText(clauses.value.map(c => c.title + '\n' + c.body).join('\n\n'))
  }
}

onMounted(() => {
  clauses.value = parseClauses(draft.generatedText)
})
</script>

<style scoped>
.edit-view { display: flex; flex-direction: column; }
.edit-layout {
  display: flex;
  gap: 16px;
  height: 500px;
}
.clause-preview {
  flex: 1;
  overflow-y: auto;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  padding: 12px;
}
.clause-preview h4 { margin: 0 0 8px; }
.clause-item {
  padding: 10px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 6px;
  border: 1px solid transparent;
  transition: all 0.15s;
}
.clause-item:hover { background: #f5f6ff; }
.clause-item.anchored { border-color: #4C6EF5; background: #e8ebff; }
.clause-title { font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.clause-body { font-size: 13px; color: #555; line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.chat-area { width: 380px; min-width: 380px; }
.step-actions { display: flex; justify-content: space-between; margin-top: 16px; }
</style>
