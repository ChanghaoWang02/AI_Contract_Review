<template>
  <div class="translate-report-modal">
    <h3>翻译审核报告</h3>

    <div v-if="!translateResult && !translatingReport" class="translate-options">
      <p>选择翻译方向：</p>
      <n-select
        v-model:value="reportTargetLang"
        :options="reportLangOptions"
        style="width: 200px; margin-bottom: 16px"
      />
      <n-button type="primary" @click="doTranslateReport">
        开始翻译
      </n-button>
    </div>

    <div v-if="translatingReport" class="translate-progress">
      <n-spin size="small" /> 翻译中...
    </div>

    <div v-if="translateResult" class="translate-result">
      <div class="result-text">{{ translateResult }}</div>
      <div class="result-actions">
        <n-button secondary @click="downloadTranslatedReport">
          <n-icon><download-outline /></n-icon> 下载 TXT
        </n-button>
        <n-button @click="resetTranslateReport">重新翻译</n-button>
        <n-button @click="$emit('close')">关闭</n-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { NButton, NIcon, NSelect, NSpin } from 'naive-ui'
import { DownloadOutline } from '@vicons/ionicons5'
import { useTranslateText } from '@/composables/useTranslateText'
import type { Findings } from '@/types/review'

const props = defineProps<{
  reviewFindings: Findings | undefined
}>()

const emit = defineEmits<{
  close: []
}>()

const { translateText } = useTranslateText()

const reportTargetLang = ref('en')
const translatingReport = ref(false)
const translateResult = ref('')

const reportLangOptions = [
  { label: '中文 → English', value: 'en' },
  { label: 'English → 中文', value: 'zh' },
]

async function doTranslateReport() {
  if (!props.reviewFindings) return

  const summary = props.reviewFindings.summary || ''
  const clausesText =
    props.reviewFindings.clauses
      ?.map(
        (c) =>
          `【${c.risk === 'high' ? '高风险' : c.risk === 'medium' ? '中风险' : '低风险'}】${c.summary}：${c.original_text}`,
      )
      .join('\n\n') || ''

  const fullText = `审核报告摘要：\n${summary}\n\n逐条分析：\n${clausesText}`

  translatingReport.value = true
  translateResult.value = ''

  const result = await translateText(fullText, reportTargetLang.value)
  if (result) {
    translateResult.value = result.content
  }
  translatingReport.value = false
}

function resetTranslateReport() {
  translateResult.value = ''
  reportTargetLang.value = 'en'
}

function downloadTranslatedReport() {
  const blob = new Blob([translateResult.value], {
    type: 'text/plain;charset=utf-8',
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `ATCR_Review_Report_${reportTargetLang.value}.txt`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.translate-report-modal {
  background: #fff;
  border-radius: 8px;
  padding: 24px;
  max-height: 70vh;
  display: flex;
  flex-direction: column;
}
.translate-report-modal h3 {
  margin: 0 0 16px;
}
.translate-options p {
  color: #666;
  margin: 0 0 8px;
}
.translate-progress {
  padding: 24px 0;
  text-align: center;
  color: #999;
}
.translate-result {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.result-text {
  flex: 1;
  overflow-y: auto;
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.7;
  padding: 16px;
  background: #f9f9f9;
  border-radius: 6px;
  margin-bottom: 16px;
  max-height: 50vh;
}
.result-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
</style>