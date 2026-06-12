import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useApiClient } from '@/composables/useApiClient'

export interface Contract {
  id: number
  original_filename: string
  content_type: string
  source: string
  parent_contract_id: number | null
  source_lang: string | null
  target_lang: string | null
  file_size: number
  clause_count: number
  review_count: number
  review_status: string | null  // 'completed' | 'processing' | 'error' | null
  created_at: string
}

export interface ContractDetail extends Contract {
  content: string
}

export const useContractStore = defineStore('contract', () => {
  const contracts = ref<Contract[]>([])
  const currentContract = ref<ContractDetail | null>(null)
  const loading = ref(false)
  const api = useApiClient()

  async function fetchContracts() {
    loading.value = true
    try {
      contracts.value = await api.get<Contract[]>('/api/contracts')
    } finally {
      loading.value = false
    }
  }

  async function fetchContract(id: number) {
    loading.value = true
    try {
      currentContract.value = await api.get<ContractDetail>(`/api/contracts/${id}`)
    } finally {
      loading.value = false
    }
  }

  async function uploadContract(file: File) {
    loading.value = true
    try {
      const form = new FormData()
      form.append('file', file)
      const contract = await api.post<Contract>('/api/contracts/upload', form)
      contracts.value.unshift(contract)
      return contract
    } finally {
      loading.value = false
    }
  }

  function markReviewed(contractId: number) {
    const c = contracts.value.find((c) => c.id === contractId)
    if (c) {
      c.review_count = Math.max(c.review_count, 1)
      c.review_status = 'completed'
    }
  }

  async function deleteContract(id: number) {
    await api.delete(`/api/contracts/${id}`)
    contracts.value = contracts.value.filter((c) => c.id !== id)
    if (currentContract.value?.id === id) {
      currentContract.value = null
    }
  }

  return {
    contracts,
    currentContract,
    loading,
    fetchContracts,
    fetchContract,
    uploadContract,
    markReviewed,
    deleteContract,
  }
})
