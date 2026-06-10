<template>
  <div class="clause-row" :class="`status-${status}`">
    <div class="clause-header">
      <span class="clause-index">条款 {{ index + 1 }}</span>
      <span class="status-icon">
        <n-spin v-if="status === 'streaming'" :size="14" />
        <n-icon v-else-if="status === 'done'" color="#2f9e44"><checkmark-circle-outline /></n-icon>
        <n-icon v-else-if="status === 'error'" color="#e03131"><alert-circle-outline /></n-icon>
        <n-icon v-else color="#ccc"><ellipse-outline /></n-icon>
      </span>
    </div>

    <div class="clause-columns">
      <!-- 原文 -->
      <div class="column original">
        <div class="column-label">原文</div>
        <div class="column-text">{{ original }}</div>
      </div>

      <!-- 译文 -->
      <div class="column translated">
        <div class="column-label">译文</div>
        <div v-if="!editing" class="column-text" @dblclick="startEdit">
          {{ translated || (status === 'pending' ? '等待翻译...' : '') }}
        </div>
        <n-input
          v-else
          v-model:value="editText"
          type="textarea"
          :autosize="{ minRows: 3, maxRows: 10 }"
          @blur="finishEdit"
          @keyup.enter.ctrl="finishEdit"
          @keyup.escape="cancelEdit"
        />
        <div v-if="status === 'error' && errorMsg" class="error-msg">
          {{ errorMsg }}
        </div>
      </div>
    </div>

    <!-- 操作按钮 -->
    <div class="clause-actions" v-if="status === 'done' || status === 'error'">
      <n-button size="tiny" secondary @click="startEdit" v-if="!editing">
        <n-icon><create-outline /></n-icon> 编辑
      </n-button>
      <n-button size="tiny" secondary @click="$emit('retranslate', index)" :loading="retranslating">
        <n-icon><refresh-outline /></n-icon> 重翻
      </n-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { NButton, NIcon, NSpin, NInput } from 'naive-ui'
import {
  CheckmarkCircleOutline,
  AlertCircleOutline,
  EllipseOutline,
  CreateOutline,
  RefreshOutline,
} from '@vicons/ionicons5'

const props = defineProps<{
  index: number
  original: string
  translated: string
  status: 'pending' | 'streaming' | 'done' | 'error'
  errorMsg?: string
  retranslating?: boolean
}>()

const emit = defineEmits<{
  edit: [index: number, newText: string]
  retranslate: [index: number]
}>()

const editing = ref(false)
const editText = ref('')

function startEdit() {
  editText.value = props.translated
  editing.value = true
}

function finishEdit() {
  if (editText.value !== props.translated) {
    emit('edit', props.index, editText.value)
  }
  editing.value = false
}

function cancelEdit() {
  editText.value = props.translated
  editing.value = false
}

// streaming 完成后自动退出编辑模式
watch(() => props.status, (val) => {
  if (val === 'streaming') {
    editing.value = false
  }
})
</script>

<style scoped>
.clause-row {
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
  background: #fff;
  border: 1px solid #eee;
  transition: border-color 0.2s;
}
.clause-row.status-streaming {
  border-color: #c4ccff;
  background: #fafbff;
}
.clause-row.status-error {
  border-color: #ffd4d4;
  background: #fffafa;
}

.clause-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.clause-index {
  font-weight: 600;
  font-size: 14px;
  color: #333;
}

.clause-columns {
  display: flex;
  gap: 16px;
}
.column {
  flex: 1;
  min-width: 0;
}
.column-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 6px;
  font-weight: 500;
}
.column-text {
  font-size: 13px;
  line-height: 1.7;
  color: #555;
  padding: 10px;
  border-radius: 6px;
  min-height: 48px;
  white-space: pre-wrap;
  word-break: break-word;
}
.original .column-text {
  background: #f5f5f5;
  color: #555;
}
.translated .column-text {
  background: #f0faf0;
  color: #2f5c2f;
  cursor: text;
}

.error-msg {
  font-size: 12px;
  color: #e03131;
  margin-top: 6px;
}

.clause-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  justify-content: flex-end;
}
</style>
