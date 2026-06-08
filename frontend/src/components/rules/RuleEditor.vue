<template>
  <n-modal
    :show="show"
    @update:show="$emit('update:show', $event)"
    :title="rule ? '编辑规则' : '新建规则'"
    style="width: 560px"
  >
    <div class="rule-editor">
      <n-form ref="formRef" :model="form" :rules="formRules" label-placement="top">
        <n-form-item label="规则名称" path="name">
          <n-input v-model:value="form.name" placeholder="如：违约责任重点检查" />
        </n-form-item>
        <n-form-item label="审核提示词" path="prompt_template">
          <n-input
            v-model:value="form.prompt_template"
            type="textarea"
            :autosize="{ minRows: 3, maxRows: 8 }"
            placeholder="描述 AI 需要重点审核的内容和标准..."
          />
          <div class="form-hint">
            提示词越具体，AI 审核结果越精准。建议包含：检查范围、风险判断标准、输出格式要求。
          </div>
        </n-form-item>
      </n-form>
      <div class="modal-actions">
        <n-button @click="$emit('update:show', false)">取消</n-button>
        <n-button type="primary" :loading="saving" @click="saveRule">保存</n-button>
      </div>
    </div>
  </n-modal>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { NModal, NForm, NFormItem, NInput, NButton, useMessage } from 'naive-ui'

const props = defineProps<{
  show: boolean
  rule: any | null
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  saved: []
}>()

const message = useMessage()
const saving = ref(false)

const form = reactive({
  name: '',
  prompt_template: '',
})

const formRules = {
  name: [{ required: true, message: '请输入规则名称' }],
  prompt_template: [{ required: true, message: '请输入审核提示词' }],
}

watch(
  () => props.rule,
  (r) => {
    if (r) {
      form.name = r.name
      form.prompt_template = r.prompt_template
    } else {
      form.name = ''
      form.prompt_template = ''
    }
  },
  { immediate: true }
)

async function saveRule() {
  saving.value = true
  try {
    const url = props.rule ? `/api/rules/${props.rule.id}` : '/api/rules'
    const method = props.rule ? 'PUT' : 'POST'
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: form.name,
        prompt_template: form.prompt_template,
        category: 'custom',
        is_active: true,
      }),
    })
    if (res.ok) {
      message.success(props.rule ? '规则已更新' : '规则已创建')
      emit('saved')
    } else {
      const err = await res.json()
      message.error(err.detail || '保存失败')
    }
  } catch {
    message.error('保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.rule-editor {
  padding: 24px;
  background: #fff;
  border-radius: 8px;
}
.form-hint { font-size: 12px; color: #999; margin-top: 4px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
</style>
