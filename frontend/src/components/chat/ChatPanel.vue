<template>
  <div class="chat-panel">
    <!-- 顶部状态栏 -->
    <div class="chat-header">
      <div class="header-left">
        <n-icon size="18"><chatbubbles-outline /></n-icon>
        <span>AI 审核对话</span>
      </div>
      <div class="header-right">
        <n-tag v-if="reviewStatus === 'processing'" type="warning" size="small">
          审核中...
        </n-tag>
        <n-tag v-else-if="reviewStatus === 'completed'" type="success" size="small">
          审核完成
        </n-tag>
        <n-tag v-else-if="reviewStatus === 'error'" type="error" size="small">
          审核失败
        </n-tag>
        <n-tag v-if="chat.isStreaming" type="info" size="small">
          <span class="pulsing-dot" /> AI 回复中
        </n-tag>
      </div>
    </div>

    <!-- 错误提示 -->
    <n-alert
      v-if="chat.error && !chat.isStreaming"
      type="error"
      closable
      class="error-banner"
      @update:show="chat.error = null"
    >
      {{ chat.error }}
    </n-alert>

    <!-- 消息列表 -->
    <div class="messages-container" ref="messagesEl">
      <div v-if="chat.messages.length === 0 && !chat.isStreaming" class="welcome">
        <div class="welcome-icon">📋</div>
        <h3>合同审核助手</h3>
        <p>上传合同后，AI 将自动审核并给出建议。<br/>你也可以在聊天中随时追问。</p>
        <div class="quick-actions">
          <n-button
            v-for="q in quickQuestions"
            :key="q"
            size="small"
            secondary
            @click="$emit('send', q)"
          >
            {{ q }}
          </n-button>
        </div>
      </div>

      <MessageBubble
        v-for="(msg, i) in chat.messages"
        :key="i"
        :message="msg"
      />

      <!-- 流式消息 -->
      <MessageBubble
        v-if="chat.isStreaming && chat.streamingMessage"
        :message="{ role: 'assistant', content: chat.streamingMessage, review_id: 0 }"
        :streaming="true"
      />

      <div v-if="chat.isStreaming && !chat.streamingMessage" class="typing-indicator">
        <span class="dot"></span><span class="dot"></span><span class="dot"></span>
      </div>
    </div>

    <!-- 输入区 -->
    <ChatInput
      :anchor="chat.anchorClause"
      :disabled="!reviewId"
      @send="onSend"
      @clear-anchor="chat.clearAnchor()"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { NIcon, NTag, NButton, NAlert } from 'naive-ui'
import { ChatbubblesOutline } from '@vicons/ionicons5'
import { useChatStore } from '@/stores/chat'
import MessageBubble from './MessageBubble.vue'
import ChatInput from './ChatInput.vue'

const props = defineProps<{
  reviewId: number | null
  reviewStatus?: string
}>()

const emit = defineEmits<{
  send: [content: string]
}>()

const chat = useChatStore()
const messagesEl = ref<HTMLElement>()

const quickQuestions = [
  '这份合同有哪些主要风险？',
  '违约责任条款是否对等？',
  '帮我修改一下模糊条款',
  '这份合同还缺少哪些必要条款？',
]

// 自动滚动
watch(
  () => [chat.messages.length, chat.streamingMessage],
  () => {
    nextTick(() => {
      if (messagesEl.value) {
        messagesEl.value.scrollTop = messagesEl.value.scrollHeight
      }
    })
  },
  { deep: true }
)

function onSend(content: string) {
  emit('send', content)
}
</script>

<style scoped>
.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #fff;
  min-width: 0;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #eee;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 15px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.welcome {
  text-align: center;
  padding: 40px 20px;
}

.welcome-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.welcome h3 {
  margin: 0 0 8px;
  font-size: 18px;
  color: #333;
}

.welcome p {
  color: #999;
  margin: 0 0 20px;
  line-height: 1.6;
}

.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}

.error-banner {
  margin: 0;
  border-radius: 0;
}

.pulsing-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #2080f0;
  margin-right: 4px;
  animation: pulse-dot 1.4s infinite;
}

@keyframes pulse-dot {
  0%, 60%, 100% { opacity: 1; }
  30% { opacity: 0.3; }
}

.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 8px 12px;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #bbb;
  animation: bounce 1.4s infinite;
}
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes bounce {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-6px); }
}
</style>
