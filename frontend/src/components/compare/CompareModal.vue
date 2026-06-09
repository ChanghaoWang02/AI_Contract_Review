<template>
  <n-modal
    :show="show"
    @update:show="$emit('update:show', $event)"
    :mask-closable="false"
    style="width: 96vw; max-width: 1400px"
    :closable="false"
  >
    <div class="compare-container">
      <!-- 顶部栏 -->
      <div class="compare-toolbar">
        <div class="toolbar-left">
          <n-icon size="20"><git-compare-outline /></n-icon>
          <span class="toolbar-title">合同对比审核</span>
          <span v-if="phase" class="phase-badge">{{ phaseLabel }}</span>
        </div>
        <n-button text @click="$emit('update:show', false)">
          <n-icon size="20"><close-outline /></n-icon>
        </n-button>
      </div>

      <!-- 加载中 -->
      <div v-if="loading" class="loading-state">
        <n-spin size="large" />
        <p>{{ loadingText }}</p>
      </div>

      <!-- 无变更 -->
      <div v-else-if="noChanges" class="no-changes-state">
        <n-icon size="48" color="#52c41a"><checkmark-circle-outline /></n-icon>
        <h3>两份合同条款内容完全一致，未检测到变更</h3>
      </div>

      <!-- 错误 -->
      <div v-else-if="errorMsg" class="error-state">
        <n-icon size="48" color="#ff4d4f"><close-circle-outline /></n-icon>
        <h3>对比失败</h3>
        <p>{{ errorMsg }}</p>
        <n-button @click="$emit('update:show', false)">关闭</n-button>
      </div>

      <!-- 对比结果 -->
      <div v-else class="compare-body">
        <div class="panels-row">
          <ComparePanel
            ref="leftPanel"
            label="原合同"
            :clauses="leftClauses"
            :active-id="activeClauseId"
            :highlight-map="highlightMap"
            @clause-click="onClauseClick"
          />
          <ComparePanel
            ref="rightPanel"
            label="新版合同"
            :clauses="rightClauses"
            :active-id="activeClauseId"
            :highlight-map="highlightMap"
            @clause-click="onClauseClick"
          />
          <ChangeList
            :changes="changeItems"
            :active-id="activeClauseId"
            @select="onClauseClick"
          />
        </div>

        <CompareSummary
          v-if="summaryStats"
          :stats="summaryStats"
          :perspective="perspective"
        />
      </div>
    </div>
  </n-modal>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { NModal, NButton, NIcon, NSpin } from 'naive-ui'
import { GitCompareOutline, CloseOutline, CheckmarkCircleOutline, CloseCircleOutline } from '@vicons/ionicons5'
import ComparePanel from './ComparePanel.vue'
import type { ClauseDisplay } from './ComparePanel.vue'
import ChangeList from './ChangeList.vue'
import type { ChangeItem } from './ChangeList.vue'
import CompareSummary from './CompareSummary.vue'
import type { CompareStats } from './CompareSummary.vue'
import { ContractChunkerClient } from '@/core/chunker'
import type { ContractDetail } from '@/stores/contract'

const props = defineProps<{
  show: boolean
  contract: ContractDetail | null
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
}>()

// 由父组件（HomeView）在 confirm 时调用
const compareFile = ref<File | null>(null)
const perspective = ref('neutral')
const abortController = ref<AbortController | null>(null)

const loading = ref(false)
const loadingText = ref('正在上传文件...')
const phase = ref('')
const noChanges = ref(false)
const errorMsg = ref('')
const activeClauseId = ref<string | null>(null)

// 左右两侧的条款显示
const leftClauses = ref<ClauseDisplay[]>([])
const rightClauses = ref<ClauseDisplay[]>([])
const changeItems = ref<ChangeItem[]>([])
const highlightMap = ref<Record<string, string>>({})
const summaryStats = ref<CompareStats | null>(null)

const leftPanel = ref<InstanceType<typeof ComparePanel> | null>(null)
const rightPanel = ref<InstanceType<typeof ComparePanel> | null>(null)

const phaseLabel = ref('')

const phaseLabels: Record<string, string> = {
  parsing: '解析中...',
  matching: '匹配条款...',
  analyzing: 'AI 分析中...',
}

function resetState() {
  loading.value = false
  loadingText.value = '正在上传文件...'
  phase.value = ''
  noChanges.value = false
  errorMsg.value = ''
  activeClauseId.value = null
  leftClauses.value = []
  rightClauses.value = []
  changeItems.value = []
  highlightMap.value = {}
  summaryStats.value = null
  abortController.value = null
}

// 由父组件调用以启动对比
async function startCompare(file: File, persp: string) {
  if (!props.contract) return

  resetState()
  compareFile.value = file
  perspective.value = persp
  loading.value = true
  loadingText.value = '正在上传文件...'

  // 预先切分原合同（前端展示用）
  const origChunks = ContractChunkerClient.split(props.contract.content)
  leftClauses.value = origChunks.map((c) => ({
    id: c.id,
    title: c.title,
    text: c.content,
  }))

  const controller = new AbortController()
  abortController.value = controller

  try {
    const form = new FormData()
    form.append('file', file)
    form.append('perspective', persp)

    const res = await fetch(`/api/contracts/${props.contract.id}/compare`, {
      method: 'POST',
      body: form,
      signal: controller.signal,
      headers: { Accept: 'text/event-stream' },
    })

    if (!res.ok) {
      let detail = ''
      try { const err = await res.json(); detail = err.detail || '' } catch { /* */ }
      throw new Error(detail || `请求失败 (HTTP ${res.status})`)
    }

    loading.value = false
    const reader = res.body?.getReader()
    if (!reader) throw new Error('无法读取响应流')

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const payload = JSON.parse(line.slice(6))
          handleSSEEvent(payload)
        } catch { /* ignore malformed lines */ }
      }
    }
  } catch (e: any) {
    if (e.name === 'AbortError') return
    errorMsg.value = e.message || '对比失败'
    loading.value = false
  } finally {
    if (abortController.value === controller) {
      abortController.value = null
    }
  }
}

function handleSSEEvent(payload: any) {
  const event = payload.event
  const data = payload.data

  switch (event) {
    case 'progress': {
      phase.value = data.phase
      phaseLabel.value = phaseLabels[data.phase] || data.detail || ''
      break
    }
    case 'clause': {
      // 新版合同的条款（如果有 new_text）
      if (data.new_text) {
        const existingIdx = rightClauses.value.findIndex((c) => c.id === data.clause_id)
        if (existingIdx >= 0) {
          // 更新已有条款
          rightClauses.value[existingIdx] = {
            ...rightClauses.value[existingIdx],
            text: data.new_text,
            change: data.change,
            changeLabel: changeLabel(data.change),
            risk: data.risk,
          }
        } else {
          // 新增条款
          rightClauses.value.push({
            id: data.clause_id,
            title: data.new_title || `条款 ${data.clause_id}`,
            text: data.new_text,
            change: data.change,
            changeLabel: changeLabel(data.change),
            risk: data.risk,
          })
        }
      }

      // 更新高亮映射
      highlightMap.value = {
        ...highlightMap.value,
        [data.clause_id]: data.risk,
      }

      // 添加到变更列表
      changeItems.value.push({
        clause_id: data.clause_id,
        change: data.change,
        risk: data.risk,
        reason: data.reason,
        title: data.old_title || data.new_title || data.clause_id,
      })

      // 新增/删除的条款在原合同侧也标记
      if (data.change === 'deleted') {
        const idx = leftClauses.value.findIndex((c) => c.id === data.clause_id)
        if (idx >= 0) {
          leftClauses.value[idx] = {
            ...leftClauses.value[idx],
            change: 'deleted',
            changeLabel: '已删除',
          }
        }
      }

      break
    }
    case 'done': {
      phase.value = ''
      phaseLabel.value = ''
      summaryStats.value = {
        total: data.total || 0,
        modified: data.modified || 0,
        added: data.added || 0,
        deleted: data.deleted || 0,
        favorable: data.favorable || 0,
        neutral: data.neutral || 0,
        unfavorable: data.unfavorable || 0,
        unknown: data.unknown || 0,
        token_usage: data.token_usage || 0,
      }
      if (data.total === 0) {
        noChanges.value = true
      }
      break
    }
    case 'error': {
      errorMsg.value = typeof data === 'string' ? data : data?.message || '对比失败'
      break
    }
  }
}

function changeLabel(change: string): string {
  switch (change) {
    case 'modified': return '已变更'
    case 'added': return '新增'
    case 'deleted': return '已删除'
    default: return ''
  }
}

function onClauseClick(clauseId: string) {
  activeClauseId.value = clauseId
  // 左右两侧滚动定位
  leftPanel.value?.scrollTo(clauseId)
  rightPanel.value?.scrollTo(clauseId)
}

function abort() {
  abortController.value?.abort()
}

// 弹窗关闭时断开 SSE
watch(() => props.show, (val) => {
  if (!val) {
    abort()
    resetState()
  }
})

defineExpose({ startCompare })
</script>

<style scoped>
.compare-container {
  display: flex;
  flex-direction: column;
  height: 90vh;
  background: #f5f7fa;
  border-radius: 8px;
  overflow: hidden;
}
.compare-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 20px;
  background: #fff;
  border-bottom: 1px solid #eee;
  flex-shrink: 0;
}
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.toolbar-title {
  font-weight: 600;
  font-size: 15px;
}
.phase-badge {
  font-size: 12px;
  padding: 2px 8px;
  background: #e8f0fe;
  color: #1967d2;
  border-radius: 10px;
}
.compare-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 12px;
}
.panels-row {
  flex: 1;
  display: flex;
  gap: 12px;
  overflow: hidden;
}
.loading-state,
.no-changes-state,
.error-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: #fff;
  margin: 12px;
  border-radius: 8px;
}
.loading-state p { color: #999; }
.no-changes-state h3 { color: #333; margin: 0; }
.error-state h3 { color: #333; margin: 0; }
.error-state p { color: #999; margin: 0; }
</style>
