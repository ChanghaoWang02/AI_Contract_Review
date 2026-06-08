<template>
  <div class="save-view">
    <h3>保存合同</h3>

    <!-- 保存前：表单 -->
    <template v-if="!savedContractId">
      <n-form label-placement="top">
        <n-form-item label="文件名">
          <n-input v-model:value="filename" placeholder="输入文件名" />
        </n-form-item>

        <n-form-item label="文件格式">
          <n-radio-group v-model:value="fileFormat" :disabled="saving">
            <n-radio value="txt">TXT — 纯文本（可用记事本打开）</n-radio>
            <n-radio value="pdf">PDF — 排版文档（适合打印签署）</n-radio>
          </n-radio-group>
        </n-form-item>
      </n-form>

      <n-alert v-if="saveError" type="error" class="save-error" closable @update:show="saveError = ''">
        {{ saveError }}
      </n-alert>

      <div class="save-hint">
        保存后合同将存入合同列表，同时文件会下载到浏览器默认下载目录。
      </div>

      <div class="step-actions">
        <n-button :disabled="saving" @click="draft.currentStep = 3">上一步</n-button>
        <div class="right-actions">
          <n-button :loading="saving && saveMode === 'only'" :disabled="!filename.trim() || saving" @click="handleSave(false)">
            保存合同
          </n-button>
          <n-button type="primary" :loading="saving && saveMode === 'review'" :disabled="!filename.trim() || saving" @click="handleSave(true)">
            保存并送审
          </n-button>
        </div>
      </div>
    </template>

    <!-- 保存后：成功状态 + 送审引导 -->
    <template v-else>
      <n-alert type="success" class="success-box">
        <p>合同已保存（#{{ savedContractId }}），{{ savedFormat }} 文件已下载。</p>
        <p class="success-hint">可在左侧合同列表中查看。要现在发起 AI 审核吗？</p>
      </n-alert>

      <div class="step-actions">
        <n-button @click="goBackToEdit">返回编辑</n-button>
        <div class="right-actions">
          <n-button @click="backToDraftList">完成，返回列表</n-button>
          <n-button type="primary" @click="goToReview">
            立即送审
          </n-button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NForm, NFormItem, NInput, NAlert, NRadioGroup, NRadio, useMessage } from 'naive-ui'
import { useDraftStore } from '@/stores/draft'

const router = useRouter()
const message = useMessage()
const draft = useDraftStore()

const filename = ref('')
const fileFormat = ref<'txt' | 'pdf'>('txt')
const saving = ref(false)
const saveMode = ref<'only' | 'review'>('only')
const saveError = ref('')
const savedContractId = ref<number | null>(null)
const savedFormat = ref('')

onMounted(() => {
  const today = new Date()
  const dateStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
  filename.value = `${draft.contractType || '合同'}_${dateStr}`
})

function triggerDownload(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

async function downloadFile(): Promise<boolean> {
  const finalName = fileFormat.value === 'pdf'
    ? (filename.value.endsWith('.pdf') ? filename.value : `${filename.value}.pdf`)
    : (filename.value.endsWith('.txt') ? filename.value : `${filename.value}.txt`)

  if (fileFormat.value === 'txt') {
    const blob = new Blob([draft.generatedText], { type: 'text/plain; charset=utf-8' })
    triggerDownload(blob, finalName)
    return true
  }

  try {
    const res = await fetch('/api/draft/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        content: draft.generatedText,
        filename: finalName,
        format: 'pdf',
      }),
    })

    if (!res.ok) throw new Error(`导出失败 (HTTP ${res.status})`)

    const blob = await res.blob()
    triggerDownload(blob, finalName)
    return true
  } catch (e: any) {
    console.error('PDF export failed:', e)
    const fallbackName = finalName.replace('.pdf', '.txt')
    const blob = new Blob([draft.generatedText], { type: 'text/plain; charset=utf-8' })
    triggerDownload(blob, fallbackName)
    message.warning('PDF 生成失败，已下载 TXT 格式')
    return false
  }
}

async function saveToDb(): Promise<{ id: number } | null> {
  const res = await fetch('/api/contracts/save-draft', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      filename: filename.value.trim(),
      content: draft.generatedText,
      content_type: fileFormat.value === 'pdf' ? 'txt' : 'txt',
    }),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '保存失败' }))
    throw new Error(err.detail || `保存失败 (HTTP ${res.status})`)
  }

  return res.json()
}

async function handleSave(andReview: boolean) {
  saving.value = true
  saveMode.value = andReview ? 'review' : 'only'
  saveError.value = ''

  try {
    const contract = await saveToDb()
    if (!contract) return

    await downloadFile()
    draft.clearLocalStorage()
    savedFormat.value = fileFormat.value.toUpperCase()
    savedContractId.value = contract.id

    if (andReview) {
      // 保存并送审：立即跳转
      draft.clearDraft()
      message.success(`合同已保存（#${contract.id}），${savedFormat.value} 文件已下载，正在跳转送审...`)
      setTimeout(() => {
        router.push({ path: '/', query: { review_contract: String(contract.id) } })
      }, 800)
    } else {
      // 保存合同：留在当前页面，展示完成状态
      message.success(`合同已保存（#${contract.id}），${savedFormat.value} 文件已下载`)
    }
  } catch (e: any) {
    saveError.value = e.message || '保存失败，请重试'
  } finally {
    saving.value = false
  }
}

function goToReview() {
  draft.clearDraft()
  router.push({ path: '/', query: { review_contract: String(savedContractId.value) } })
}

function backToDraftList() {
  draft.clearDraft()
  router.push('/')
}

function goBackToEdit() {
  savedContractId.value = null
  draft.currentStep = 3
}
</script>

<style scoped>
.save-view h3 { margin: 0 0 16px; }
.save-error { margin-bottom: 12px; }
.save-hint { color: #999; font-size: 13px; margin-bottom: 16px; }
.step-actions { display: flex; justify-content: space-between; align-items: center; }
.right-actions { display: flex; gap: 8px; }
.success-box { margin-bottom: 16px; }
.success-box p { margin: 4px 0; }
.success-hint { color: #666; font-size: 13px; margin-top: 8px; }
</style>
