import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { fetchLocale } from './api.js'
import { addDeploymentText } from './i18n.js'

// The deployment's own text for the current language (its tab, panel and location names), merged over the
// library's catalogue once signed in; switching language loads that language's file.
export function useDeploymentText(enabled) {
  const { i18n } = useTranslation()
  const lng = i18n.resolvedLanguage
  const query = useQuery({ queryKey: ['locales', lng], queryFn: () => fetchLocale(lng), enabled: enabled && !!lng,
                           staleTime: Infinity })
  useEffect(() => {
    if (query.data) addDeploymentText(lng, query.data)
  }, [lng, query.data])
}
