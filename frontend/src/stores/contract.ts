import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Contract {
  id: number
  original_filename: string
  content_type: string
  source: string
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

  async function fetchContracts() {
    loading.value = true
    try {
      const res = await fetch('/api/contracts')
      if (!res.ok) throw new Error('获取合同列表失败')
      contracts.value = await res.json()
    } finally {
      loading.value = false
    }
  }

  async function fetchContract(id: number) {
    loading.value = true
    try {
      const res = await fetch(`/api/contracts/${id}`)
      if (!res.ok) throw new Error('合同不存在')
      currentContract.value = await res.json()
    } finally {
      loading.value = false
    }
  }

  async function uploadContract(file: File) {
    loading.value = true
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch('/api/contracts/upload', {
        method: 'POST',
        body: form,
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || '上传失败')
      }
      const contract = await res.json()
      contracts.value.unshift(contract)
      return contract as Contract
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
    const res = await fetch(`/api/contracts/${id}`, { method: 'DELETE' })
    if (!res.ok) throw new Error('删除失败')
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
