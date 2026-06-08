<template>
  <div class="rules-page">
    <div class="rules-header">
      <n-button text @click="$router.push('/')">
        <n-icon><arrow-back-outline /></n-icon>
        返回
      </n-button>
      <h2>审核规则管理</h2>
    </div>

    <div class="rules-content">
      <div class="rules-toolbar">
        <n-button type="primary" @click="showEditor = true; editingRule = null">
          <template #icon><n-icon><add-outline /></n-icon></template>
          新建规则
        </n-button>
      </div>

      <!-- 规则列表 -->
      <RuleList
        :rules="rules"
        :loading="loading"
        @edit="onEdit"
        @toggle="onToggle"
        @delete="onDelete"
      />

      <!-- 规则编辑弹窗 -->
      <RuleEditor
        v-model:show="showEditor"
        :rule="editingRule"
        @saved="onSaved"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NButton, NIcon, useMessage } from 'naive-ui'
import { ArrowBackOutline, AddOutline } from '@vicons/ionicons5'
import { useRouter } from 'vue-router'
import RuleList from '@/components/rules/RuleList.vue'
import RuleEditor from '@/components/rules/RuleEditor.vue'

const router = useRouter()
const message = useMessage()

interface Rule {
  id: number
  name: string
  prompt_template: string
  category: string
  is_active: boolean
  created_at: string
}

const rules = ref<Rule[]>([])
const loading = ref(false)
const showEditor = ref(false)
const editingRule = ref<Rule | null>(null)

onMounted(() => fetchRules())

async function fetchRules() {
  loading.value = true
  try {
    const res = await fetch('/api/rules')
    rules.value = await res.json()
  } finally {
    loading.value = false
  }
}

function onEdit(rule: Rule) {
  editingRule.value = rule
  showEditor.value = true
}

async function onToggle(rule: Rule) {
  try {
    const res = await fetch(`/api/rules/${rule.id}/toggle`, { method: 'PATCH' })
    if (res.ok) {
      const updated = await res.json()
      const idx = rules.value.findIndex((r) => r.id === rule.id)
      if (idx >= 0) rules.value[idx] = updated
      message.success(`规则已${updated.is_active ? '启用' : '停用'}`)
    } else {
      const err = await res.json().catch(() => ({ detail: '请求失败' }))
      message.error(err.detail || '操作失败')
    }
  } catch (e: any) {
    message.error('网络错误，请重试')
  }
}

async function onDelete(rule: Rule) {
  try {
    const res = await fetch(`/api/rules/${rule.id}`, { method: 'DELETE' })
    if (res.ok) {
      rules.value = rules.value.filter((r) => r.id !== rule.id)
      message.success('规则已删除')
    } else {
      const err = await res.json().catch(() => ({ detail: '请求失败' }))
      message.error(err.detail || '删除失败')
    }
  } catch (e: any) {
    message.error('网络错误，请重试')
  }
}

function onSaved() {
  showEditor.value = false
  fetchRules()
}
</script>

<style scoped>
.rules-page {
  max-width: 800px;
  margin: 0 auto;
  padding: 24px;
}

.rules-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.rules-header h2 {
  margin: 0;
}

.rules-toolbar {
  margin-bottom: 16px;
}
</style>
