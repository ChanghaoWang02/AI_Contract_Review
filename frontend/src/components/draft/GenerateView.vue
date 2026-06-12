<template>
  <div class="generate-view">
    <h3>AI 正在生成合同...</h3>

    <!-- 错误 -->
    <n-alert v-if="draft.generateError" type="error" class="error-box">
      {{ draft.generateError }}
    </n-alert>

    <!-- 生成中 / 完成 -->
    <div class="text-preview">
      <n-input
        v-model:value="displayText"
        type="textarea"
        :autosize="{ minRows: 12, maxRows: 20 }"
        readonly
        :placeholder="draft.isGenerating ? '生成中...' : '生成完成后合同将显示在这里'"
        class="contract-textarea"
      />
    </div>

    <div class="step-actions">
      <n-button :disabled="draft.isGenerating" @click="goBack">上一步</n-button>
      <div class="right-actions">
        <n-button
          v-if="!draft.isGenerating && draft.generatedText"
          :loading="draft.isGenerating"
          @click="regenerate"
        >
          重新生成
        </n-button>
        <n-button
          v-if="draft.generateError"
          type="warning"
          @click="regenerate"
        >
          重试
        </n-button>
        <n-button
          type="primary"
          :disabled="draft.isGenerating || !draft.generatedText"
          @click="draft.currentStep = 3"
        >
          下一步
        </n-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NButton, NInput, NAlert } from 'naive-ui'
import { useDraftStore } from '@/stores/draft'
import { useSSE } from '@/composables/useSSE'

const draft = useDraftStore()
const displayText = ref('')
const sse = useSSE()

onMounted(() => {
  displayText.value = draft.generatedText
  if (!draft.generatedText) {
    startGeneration()
  }
})

function goBack() {
  draft.currentStep = 1
}

async function startGeneration() {
  draft.isGenerating = true
  draft.generateError = null
  displayText.value = ''

  try {
    await sse.connect('/api/draft/generate', {
      onToken: (token) => { displayText.value += token },
      onDone: (data) => {
        draft.setGeneratedText(data?.content || displayText.value)
      },
      onError: (msg) => {
        draft.generateError = msg || '生成失败'
      },
    }, {
      method: 'POST',
      body: {
        contract_type: draft.contractType,
        form_data: draft.formData,
      },
    })
  } catch (e: any) {
    if (e.name !== 'AbortError') {
      draft.generateError = e.message || '生成失败，请重试'
    }
  } finally {
    draft.isGenerating = false
  }
}

function regenerate() {
  draft.setGeneratedText('')
  displayText.value = ''
  startGeneration()
}
</script>

<style scoped>
.generate-view h3 { margin: 0 0 12px; }
.error-box { margin-bottom: 12px; }
.text-preview { margin-bottom: 16px; }
.contract-textarea :deep(textarea) {
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.6;
}
.step-actions { display: flex; justify-content: space-between; align-items: center; }
.right-actions { display: flex; gap: 8px; }
</style>
