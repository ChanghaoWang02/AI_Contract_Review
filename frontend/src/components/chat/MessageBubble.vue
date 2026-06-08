<template>
  <div class="message-bubble" :class="message.role">
    <div class="avatar">
      <n-icon v-if="message.role === 'assistant'" size="18">
        <hardware-chip-outline />
      </n-icon>
      <n-icon v-else size="18">
        <person-outline />
      </n-icon>
    </div>
    <div class="bubble-content">
      <div class="role-label">
        {{ message.role === 'assistant' ? 'AI 助手' : '你' }}
        <n-tag
          v-if="message.anchor_clause_text"
          size="tiny"
          type="info"
          class="anchor-tag"
        >
          📌 {{ truncate(message.anchor_clause_text, 20) }}
        </n-tag>
      </div>
      <div class="message-text" v-html="renderContent(message.content)" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { NIcon, NTag } from 'naive-ui'
import { HardwareChipOutline, PersonOutline } from '@vicons/ionicons5'
import type { ChatMessage } from '@/stores/chat'

defineProps<{
  message: ChatMessage
  streaming?: boolean
}>()

function truncate(text: string, max: number): string {
  return text.length > max ? text.slice(0, max) + '...' : text
}

function renderContent(content: string): string {
  // 简单的 Markdown 渲染（粗体、代码块、换行）
  return content
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br/>')
}
</script>

<style scoped>
.message-bubble {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}

.message-bubble.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #f0f2f5;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.user .avatar {
  background: #4C6EF5;
  color: #fff;
}

.bubble-content {
  max-width: 75%;
}

.role-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.user .role-label {
  justify-content: flex-end;
}

.message-text {
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.7;
  word-break: break-word;
}

.assistant .message-text {
  background: #f0f2f5;
  border-top-left-radius: 4px;
}

.user .message-text {
  background: #4C6EF5;
  color: #fff;
  border-top-right-radius: 4px;
}

.message-text :deep(pre) {
  background: #282c34;
  color: #abb2bf;
  padding: 10px;
  border-radius: 6px;
  overflow-x: auto;
  font-size: 13px;
  margin: 8px 0;
}

.message-text :deep(code) {
  font-family: 'Fira Code', monospace;
  font-size: 13px;
}

.message-text :deep(strong) {
  font-weight: 600;
}

.anchor-tag {
  font-size: 11px;
}
</style>
