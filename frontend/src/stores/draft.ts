import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface DraftChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
}

export interface ContractType {
  key: string
  label: string
  icon: string
}

export const CONTRACT_TYPES: ContractType[] = [
  { key: '房屋租赁合同', label: '房屋租赁合同', icon: '🏠' },
  { key: '买卖合同', label: '买卖合同', icon: '🤝' },
  { key: '劳动合同', label: '劳动合同', icon: '💼' },
  { key: '服务合同', label: '服务合同', icon: '📋' },
  { key: '保密协议', label: '保密协议', icon: '🔒' },
  { key: '自定义', label: '自定义', icon: '✏️' },
]

// 表单字段定义（附录 A）
export const FORM_FIELDS: Record<string, { key: string; label: string; type: 'text' | 'number' | 'textarea' | 'select'; options?: string[] }[]> = {
  '房屋租赁合同': [
    { key: 'lessor', label: '甲方（出租方）', type: 'text' },
    { key: 'lessee', label: '乙方（承租方）', type: 'text' },
    { key: 'address', label: '房屋地址', type: 'text' },
    { key: 'monthly_rent', label: '月租金（元）', type: 'number' },
    { key: 'deposit', label: '押金（元）', type: 'number' },
    { key: 'lease_term_months', label: '租期（月）', type: 'number' },
    { key: 'payment_method', label: '支付方式', type: 'text' },
    { key: 'special_terms', label: '特殊约定', type: 'textarea' },
  ],
  '买卖合同': [
    { key: 'seller', label: '出卖方', type: 'text' },
    { key: 'buyer', label: '买受方', type: 'text' },
    { key: 'goods_description', label: '标的物描述', type: 'textarea' },
    { key: 'price', label: '价款（元）', type: 'number' },
    { key: 'payment_method', label: '支付方式', type: 'text' },
    { key: 'delivery_place', label: '交付地点', type: 'text' },
    { key: 'delivery_deadline', label: '交付期限', type: 'text' },
    { key: 'warranty', label: '质保说明', type: 'textarea' },
  ],
  '劳动合同': [
    { key: 'employer', label: '用人单位', type: 'text' },
    { key: 'employee', label: '劳动者', type: 'text' },
    { key: 'job_title', label: '工作岗位', type: 'text' },
    { key: 'work_location', label: '工作地点', type: 'text' },
    { key: 'monthly_salary', label: '月薪（元）', type: 'number' },
    { key: 'work_hours', label: '工时制度', type: 'select', options: ['标准工时', '综合计算工时', '不定时'] },
    { key: 'contract_term', label: '合同期限', type: 'text' },
    { key: 'probation', label: '试用期', type: 'text' },
    { key: 'benefits', label: '福利待遇', type: 'textarea' },
  ],
  '服务合同': [
    { key: 'client', label: '委托方', type: 'text' },
    { key: 'provider', label: '服务方', type: 'text' },
    { key: 'service_description', label: '服务内容', type: 'textarea' },
    { key: 'service_fee', label: '服务费用（元）', type: 'number' },
    { key: 'payment_schedule', label: '付款节点', type: 'text' },
    { key: 'service_period', label: '服务期限', type: 'text' },
    { key: 'acceptance_criteria', label: '验收标准', type: 'textarea' },
    { key: 'confidentiality', label: '保密要求', type: 'textarea' },
  ],
  '保密协议': [
    { key: 'disclosing_party', label: '信息披露方', type: 'text' },
    { key: 'receiving_party', label: '信息接收方', type: 'text' },
    { key: 'purpose', label: '信息使用目的', type: 'textarea' },
    { key: 'scope', label: '保密信息范围', type: 'textarea' },
    { key: 'duration_years', label: '保密期限（年）', type: 'number' },
    { key: 'exceptions', label: '例外情形', type: 'textarea' },
  ],
}

export const useDraftStore = defineStore('draft', () => {
  // 步骤状态（0-based: 0=选类型, 1=填信息, 2=生成, 3=编辑, 4=保存）
  const currentStep = ref(0)

  // Step 1 数据
  const contractType = ref<string | null>(null)

  // Step 2 数据
  const formData = ref<Record<string, string>>({})

  // Step 3 数据
  const generatedText = ref('')
  const isGenerating = ref(false)
  const generateError = ref<string | null>(null)

  // Step 4 数据
  const chatMessages = ref<DraftChatMessage[]>([])
  const isEditing = ref(false)

  // 辅助
  const hasDraft = computed(() => !!contractType.value)

  function setContractType(type: string) {
    contractType.value = type
    formData.value = {}  // 切换类型时重置表单
    generatedText.value = ''
    chatMessages.value = []
  }

  function setFormData(data: Record<string, string>) {
    formData.value = { ...data }
  }

  function setGeneratedText(text: string) {
    generatedText.value = text
  }

  function addChatMessage(msg: DraftChatMessage) {
    chatMessages.value.push(msg)
  }

  function clearDraft() {
    currentStep.value = 0
    contractType.value = null
    formData.value = {}
    generatedText.value = ''
    chatMessages.value = []
    isGenerating.value = false
    generateError.value = null
    isEditing.value = false
  }

  // localStorage 草稿持久化
  function saveToLocalStorage() {
    const draft = {
      step: currentStep.value,
      contractType: contractType.value,
      formData: formData.value,
      generatedText: generatedText.value,
      chatMessages: chatMessages.value,
    }
    localStorage.setItem('atcr_draft', JSON.stringify(draft))
  }

  function loadFromLocalStorage(): boolean {
    const raw = localStorage.getItem('atcr_draft')
    if (!raw) return false
    try {
      const draft = JSON.parse(raw)
      currentStep.value = draft.step ?? 0
      contractType.value = draft.contractType
      formData.value = draft.formData ?? {}
      generatedText.value = draft.generatedText ?? ''
      chatMessages.value = draft.chatMessages ?? []
      return true
    } catch {
      localStorage.removeItem('atcr_draft')
      return false
    }
  }

  function clearLocalStorage() {
    localStorage.removeItem('atcr_draft')
  }

  return {
    currentStep,
    contractType,
    formData,
    generatedText,
    isGenerating,
    generateError,
    chatMessages,
    isEditing,
    hasDraft,
    setContractType,
    setFormData,
    setGeneratedText,
    addChatMessage,
    clearDraft,
    saveToLocalStorage,
    loadFromLocalStorage,
    clearLocalStorage,
  }
})
