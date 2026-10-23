import { useQuery } from '@tanstack/react-query'
import { fetchConfig } from './api.js'

// The first registered method until a method switch exists (spec §6.3).
export function useMethod() {
  const { data } = useQuery({ queryKey: ['config'], queryFn: fetchConfig })
  const [name, method] = Object.entries(data?.methods ?? {})[0] ?? []
  return name ? { name, ...method } : null
}
