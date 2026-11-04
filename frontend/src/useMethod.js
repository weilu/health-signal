import { useQuery } from '@tanstack/react-query'
import { useLocation } from 'react-router-dom'
import { fetchConfig } from './api.js'
import { selectedMethod } from './filters.js'

// The method the reader selected in the header (spec §6.3), or the deployment's default.
export function useMethod() {
  const { data } = useQuery({ queryKey: ['config'], queryFn: fetchConfig })
  const { search } = useLocation()
  const methods = data?.methods ?? {}
  const name = selectedMethod(Object.keys(methods), search)
  return name ? { name, ...methods[name] } : null
}
