<template>
  <div class="draft-chat-panel">
    <div class="chat-messages" ref="chatEl">
      <div
        v-for="(msg, i) in draft.chatMessages"
        :key="i"
        class="chat-msg"
        :class="msg.role"
      >
        <div class="msg-content">{{ msg.content }}</div>
      </div>
      <div v-if="draft.isEditing && streamingText" class="chat-msg assistant streaming">
        <div class="msg-content">{{ streamingText }}</div>
      </div>
    </div>
    <div class="chat-input-row">
      <n-input
        v-model:value="inputText"
        type="textarea"
        :autosize="{ minRows: 1, maxRows: 3 }"
        placeholder="输入修改指令，如：把违约金改成一个月租金"
        :disabled="!anchoredClause || draft.isEditing"
        @keydown.enter.exact.prevent="sendInstruction"
      />
      <n-button
        type="primary"
        size="small"
        :disabled="!anchoredClause || !inputText.trim() || draft.isEditing"
        :loading="draft.isEditing"
        @click="sendInstruction"
      >
        发送
      </n-button>
    </div>
    <div v-if="!anchoredClause" class="no-anchor-hint">
      👈 请先点击左侧某条条款，再输入修改指令
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { NButton, NInput } from 'naive-ui'
import { useDraftStore } from '@/stores/draft'
import { useSSE } from '@/composables/useSSE'

const props = defineProps<{
  anchoredClause: string | null
  clauseTitles: string[]
}>()

const emit = defineEmits<{
  clauseRevised: [revisedClause: string]
}>()

const draft = useDraftStore()
const inputText = ref('')
const streamingText = ref('')
const chatEl = ref<HTMLElement>()
const sse = useSSE()

async function sendInstruction() {
  if (!props.anchoredClause || !inputText.value.trim() || draft.isEditing) return

  const instruction = inputText.value.trim()
  inputText.value = ''

  draft.addChatMessage({ role: 'user', content: instruction })
  draft.isEditing = true
  streamingText.value = ''

  try {
    await sse.connect('/api/draft/chat', {
      onToken: (token) => { streamingText.value += token },
      onDone: (data) => {
        const revised = data?.revised_clause || streamingText.value
        draft.addChatMessage({ role: 'assistant', content: revised })
        emit('clauseRevised', revised)
        streamingText.value = ''
      },
      onError: (msg) => {
        draft.addChatMessage({
          role: 'system',
          content: `❌ ${msg || '编辑失败'}`,
        })
        streamingText.value = ''
      },
    }, {
      method: 'POST',
      body: {
        anchored_clause: props.anchoredClause,
        clause_titles: props.clauseTitles,
        instruction,
      },
    })
  } catch (e: any) {
    if (e.name !== 'AbortError') {
      draft.addChatMessage({ role: 'system', content: `❌ ${e.message}` })
    }
    streamingText.value = ''
  } finally {
    draft.isEditing = false
    scrollToBottom()
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (chatEl.value) chatEl.value.scrollTop = chatEl.value.scrollHeight
  })
}

watch(() => [draft.chatMessages.length, streamingText.value], scrollToBottom)
</script>

<style scoped>
.draft-chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  overflow: hidden;
}
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}
.chat-msg {
  margin-bottom: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  max-width: 90%;
}
.chat-msg.user {
  background: #e8ebff;
  margin-left: auto;
  text-align: right;
}
.chat-msg.assistant {
  background: #f5f5f5;
}
.chat-msg.system {
  background: #fff3f3;
  color: #d32f2f;
}
.msg-content { font-size: 13px; line-height: 1.5; white-space: pre-wrap; }
.chat-input-row {
  display: flex;
  gap: 8px;
  padding: 8px;
  border-top: 1px solid #eee;
  align-items: flex-end;
}
.no-anchor-hint {
  padding: 8px 12px;
  font-size: 12px;
  color: #999;
  text-align: center;
  background: #fafafa;
  border-top: 1px solid #eee;
}
</style>
