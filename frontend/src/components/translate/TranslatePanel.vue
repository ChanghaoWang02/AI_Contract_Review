<template>
  <div class="translate-panel">
    <!-- 顶部工具栏 -->
    <div class="translate-header">
      <div class="header-left">
        <n-icon size="18"><language-outline /></n-icon>
        <span>合同翻译</span>
      </div>
      <div class="header-right">
        <!-- Ready 状态：目标语言 + 开始按钮 -->
        <template v-if="store.sessionState === 'ready'">
          <n-select
            v-model:value="selectedTargetLang"
            :options="langOptions"
            size="small"
            style="width: 120px"
          />
          <n-button type="primary" size="small" @click="startTranslate">
            <n-icon><play-outline /></n-icon> 开始翻译
          </n-button>
        </template>

        <!-- Translating 状态：进度 + 取消 -->
        <template v-if="store.sessionState === 'translating'">
          <n-progress
            type="line"
            :percentage="Math.round((store.completedCount / Math.max(store.totalCount, 1)) * 100)"
            :indicator-text="`${store.completedCount}/${store.totalCount}`"
            style="width: 160px"
          />
          <n-tag type="info" size="small">
            <span class="pulsing-dot" /> 翻译中
          </n-tag>
          <n-button size="small" @click="cancelTranslate">
            取消
          </n-button>
        </template>

        <!-- Done 状态：操作按钮 -->
        <template v-if="store.sessionState === 'done'">
          <n-button size="small" secondary @click="saveResult">
            <n-icon><save-outline /></n-icon> 保存译文
          </n-button>
          <n-button size="small" secondary @click="downloadTXT">
            <n-icon><download-outline /></n-icon> 下载 TXT
          </n-button>
          <n-button size="small" @click="startTranslate">
            <n-icon><refresh-outline /></n-icon> 重新翻译
          </n-button>
        </template>
      </div>
    </div>

    
    <!-- 错误提示 -->
    <n-alert
      v-if="store.error && store.sessionState !== 'translating'"
      type="error"
      closable
      class="error-banner"
      @update:show="store.error = null"
    >
      {{ store.error }}
    </n-alert>

    <!-- idle 状态 -->
    <div v-if="store.sessionState === 'idle'" class="state-placeholder">
      <div class="placeholder-icon">🌐</div>
      <h3>合同翻译</h3>
      <p>上传合同后自动检测源语言，选择目标语言后开始翻译。<br/>支持任意语言对：中文、英文、日文、韩文、法文、德文等。</p>
    </div>

    <!-- ready 状态 -->
    <div v-else-if="store.sessionState === 'ready'" class="state-placeholder">
      <div class="placeholder-icon">📄</div>
      <h3>准备翻译</h3>
      <p v-if="sourceLangName">
        检测到源语言：<strong>{{ sourceLangName }}</strong>（Tier {{ store.tier }}）
      </p>
      <p>目标语言：<strong>{{ targetLangName }}</strong></p>
      <p class="hint">点击"开始翻译"按钮开始逐条流式翻译。</p>
    </div>

    <!-- translating / done 状态：显示条款列表 -->
    <div v-else class="clauses-container">
      <TranslateClauseRow
        v-for="clause in store.clauses"
        :key="clause.clauseId"
        :index="clause.index"
        :original="clause.original"
        :translated="clause.translated"
        :status="clause.status"
        :error-msg="clause.errorMsg"
        :retranslating="retranslatingIndex === clause.index"
        @edit="onEditClause"
        @retranslate="onRetranslateClause"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { NButton, NIcon, NTag, NSelect, NProgress, NAlert } from 'naive-ui'
import {
  LanguageOutline,
  PlayOutline,
  SaveOutline,
  DownloadOutline,
  RefreshOutline,
} from '@vicons/ionicons5'
import { useTranslateStore } from '@/stores/translate'
import { useTranslate } from '@/composables/useTranslate'
import TranslateClauseRow from './TranslateClauseRow.vue'

const props = defineProps<{
  contractId: number | null
  contractContent: string
  activeTab: string
}>()

const emit = defineEmits<{
  saved: [childContractId: number]
}>()

const store = useTranslateStore()
const { isStreaming, abort, translateContract, retranslateClause, saveTranslation } =
  useTranslate()

const retranslatingIndex = ref<number | null>(null)

const LANG_NAMES: Record<string, string> = {
  zh: '中文', en: '英文', ja: '日文', ko: '韩文',
  fr: '法文', de: '德文', es: '西班牙文', ru: '俄文',
  ar: '阿拉伯文', th: '泰文', vi: '越南文',
}

const langOptions = computed(() => [
  { label: '中文', value: 'zh' },
  { label: 'English', value: 'en' },
  { label: '日本語', value: 'ja' },
  { label: '한국어', value: 'ko' },
  { label: 'Français', value: 'fr' },
  { label: 'Deutsch', value: 'de' },
])

const selectedTargetLang = ref('zh')
const sourceLangName = computed(() =>
  store.sourceLang ? LANG_NAMES[store.sourceLang] || store.sourceLang : null
)
const targetLangName = computed(() =>
  LANG_NAMES[selectedTargetLang.value] || selectedTargetLang.value
)

// 当合同切换时自动检测是否为翻译候选
watch(
  () => props.contractId,
  (newId) => {
    store.reset()
    if (newId && props.contractContent) {
      checkLanguage()
    }
  },
)

// 切换到翻译 Tab 时，即使 contractId 没变也重新检测语言
watch(
  () => props.activeTab,
  (tab) => {
    if (tab === 'translate' && props.contractId && props.contractContent) {
      store.reset()
      checkLanguage()
    }
  },
)

// 初始化时检测
watch(
  () => props.contractContent,
  (content) => {
    if (props.contractId && content) {
      checkLanguage()
    }
  },
)

onMounted(() => {
  if (props.contractId && props.contractContent) {
    checkLanguage()
  }
})

function checkLanguage() {
  // 启发式快速检测源语言，支持任意语言
  const sample = props.contractContent.slice(0, 2000)
  const ascii = sample.replace(/[^\x00-\x7f]/g, '').length
  const ratio = ascii / Math.max(sample.length, 1)

  // CJK 字符检测
  const cjkCount = (sample.match(/[一-鿿぀-ゟ゠-ヿ가-힯]/g) || []).length
  const cjkRatio = cjkCount / Math.max(sample.length, 1)

  if (cjkRatio > 0.08) {
    // 包含中文 → 源语言为中文
    store.startSession(props.contractId!, 'en') // 默认译英
    store.setSourceInfo('zh', 1)
  } else if (ratio > 0.85) {
    // 高 ASCII → 英文
    store.startSession(props.contractId!, 'zh') // 默认译中
    store.setSourceInfo('en', 1)
  } else {
    // 其他语言，默认译中
    store.startSession(props.contractId!, 'zh')
    store.setSourceInfo('en', 1)
  }
}

async function startTranslate() {
  if (!props.contractId || !props.contractContent) return
  await translateContract(props.contractId, props.contractContent, selectedTargetLang.value)
}

function cancelTranslate() {
  abort()
  store.sessionState = 'done'
}

async function onEditClause(index: number, newText: string) {
  const clause = store.clauses.find((c) => c.index === index)
  if (clause) {
    clause.translated = newText
  }
}

async function onRetranslateClause(index: number) {
  if (!props.contractId) return
  const clause = store.clauses.find((c) => c.index === index)
  if (!clause) return

  retranslatingIndex.value = index
  clause.status = 'streaming'
  clause.translated = ''

  const result = await retranslateClause(
    props.contractId,
    index,
    clause.original,
    selectedTargetLang.value,
  )

  if (result) {
    clause.translated = result
    clause.status = 'done'
  } else {
    clause.status = 'error'
  }
  retranslatingIndex.value = null
}

async function saveResult() {
  if (!props.contractId) return

  // 构建文件名
  const cleanName = '翻译结果'
  const result = await saveTranslation(
    props.contractId,
    store.translatedText,
    store.sourceLang || 'en',
    selectedTargetLang.value,
    cleanName,
  )
  if (result) {
    emit('saved', result.id)
  }
}

function downloadTXT() {
  const text = store.clauses.map((c) => c.translated).join('\n\n')
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `translated_${selectedTargetLang.value}.txt`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// 组件卸载时取消 SSE
onBeforeUnmount(() => {
  abort()
})
</script>

<style scoped>
.translate-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f5f7fa;
  overflow: hidden;
}

.translate-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 20px;
  background: #fff;
  border-bottom: 1px solid #eee;
  flex-shrink: 0;
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
  gap: 10px;
}

.pulsing-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #1967d2;
  animation: pulse 1.2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.tier-banner {
  margin: 8px 16px 0;
  flex-shrink: 0;
}
.error-banner {
  margin: 8px 16px 0;
  flex-shrink: 0;
}

.state-placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #999;
}
.placeholder-icon {
  font-size: 48px;
  margin-bottom: 16px;
}
.state-placeholder h3 {
  margin: 0 0 8px;
  color: #333;
}
.state-placeholder p {
  text-align: center;
  line-height: 1.6;
}
.hint {
  font-size: 12px;
  color: #bbb;
}

.clauses-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}
</style>
