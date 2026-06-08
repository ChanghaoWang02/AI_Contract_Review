<template>
  <div class="info-form">
    <h3>{{ draft.contractType }} — 填写关键信息</h3>
    <p class="form-hint">所有字段可选填，未填的将由 AI 自动补充。</p>

    <!-- 自定义模式：自由文本 -->
    <div v-if="draft.contractType === '自定义'">
      <n-input
        v-model:value="customDescription"
        type="textarea"
        :autosize="{ minRows: 5, maxRows: 10 }"
        placeholder="请描述您需要的合同：合同双方关系、核心交易内容、特殊要求等"
      />
    </div>

    <!-- 预设类型：动态表单 -->
    <n-form v-else label-placement="top">
      <n-grid :cols="2" :x-gap="16">
        <n-form-item-gi
          v-for="field in currentFields"
          :key="field.key"
          :label="field.label"
        >
          <n-input
            v-if="field.type === 'text'"
            v-model:value="formValues[field.key]"
            :placeholder="'请输入' + field.label"
          />
          <n-input-number
            v-else-if="field.type === 'number'"
            v-model:value="formValues[field.key]"
            :placeholder="'请输入' + field.label"
          />
          <n-select
            v-else-if="field.type === 'select'"
            v-model:value="formValues[field.key]"
            :options="(field.options || []).map(o => ({ label: o, value: o }))"
          />
          <n-input
            v-else-if="field.type === 'textarea'"
            v-model:value="formValues[field.key]"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 4 }"
            :placeholder="'请输入' + field.label"
          />
        </n-form-item-gi>
      </n-grid>
    </n-form>

    <div class="step-actions">
      <n-button @click="draft.currentStep = 0">上一步</n-button>
      <n-button type="primary" @click="onNext">下一步</n-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { NButton, NForm, NFormItemGi, NGrid, NInput, NInputNumber, NSelect } from 'naive-ui'
import { useDraftStore, FORM_FIELDS } from '@/stores/draft'

const draft = useDraftStore()

const currentFields = computed(() => FORM_FIELDS[draft.contractType || ''] || [])
const customDescription = ref('')

// Initialize form values from draft store or defaults
const formValues = ref<Record<string, any>>({})

watch(() => draft.contractType, () => {
  // Reset form when type changes
  const defaults: Record<string, any> = {}
  for (const f of currentFields.value) {
    defaults[f.key] = draft.formData[f.key] ?? (f.type === 'number' ? null : '')
  }
  formValues.value = defaults
  customDescription.value = draft.contractType === '自定义' ? (draft.formData['description'] || '') : ''
}, { immediate: true })

function onNext() {
  if (draft.contractType === '自定义') {
    draft.setFormData({ description: customDescription.value })
  } else {
    const data: Record<string, string> = {}
    for (const [k, v] of Object.entries(formValues.value)) {
      if (v !== null && v !== '' && v !== undefined) {
        data[k] = String(v)
      }
    }
    draft.setFormData(data)
  }
  draft.currentStep = 2
}
</script>

<style scoped>
.info-form h3 { margin: 0 0 4px; }
.form-hint { color: #999; font-size: 13px; margin: 0 0 16px; }
.step-actions { margin-top: 24px; display: flex; justify-content: space-between; }
</style>
