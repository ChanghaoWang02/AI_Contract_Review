<template>
  <div class="chat-input-area">
    <!-- 锚定条款提示 -->
    <div v-if="anchor" class="anchor-bar">
      <n-icon size="14"><pin-outline /></n-icon>
      <span class="anchor-text">已引用: {{ truncate(anchor.text, 50) }}</span>
      <n-button text size="tiny" @click="$emit('clearAnchor')">
        <n-icon><close-outline /></n-icon>
      </n-button>
    </div>

    <div class="input-row">
      <n-input
        v-model:value="inputText"
        type="textarea"
        placeholder="输入你的问题..."
        :autosize="{ minRows: 1, maxRows: 4 }"
        :disabled="disabled"
        :clearable="false"
        @keydown.enter.exact.prevent="doSend"
      />
      <n-button
        type="primary"
        :disabled="!inputText.trim() || disabled"
        @click="doSend"
      >
        <template #icon>
          <n-icon><send-outline /></n-icon>
        </template>
      </n-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { NInput, NButton, NIcon } from 'naive-ui'
import { SendOutline, PinOutline, CloseOutline } from '@vicons/ionicons5'

const props = defineProps<{
  anchor: { id: string; text: string } | null
  disabled: boolean
}>()

const emit = defineEmits<{
  send: [content: string]
  clearAnchor: []
}>()

const inputText = ref('')

function doSend() {
  const text = inputText.value.trim()
  if (!text || props.disabled) return
  emit('send', text)
  inputText.value = ''
}

function truncate(text: string, max: number): string {
  return text.length > max ? text.slice(0, max) + '...' : text
}
</script>

<style scoped>
.chat-input-area {
  border-top: 1px solid #eee;
  padding: 12px 16px;
  background: #fff;
}

.anchor-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: #e8ebff;
  border-radius: 6px;
  margin-bottom: 8px;
  font-size: 12px;
  color: #4C6EF5;
}

.anchor-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.input-row {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}
</style>
