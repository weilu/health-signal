// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest'
import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ResourceBoundary } from './ResourceBoundary.jsx'

afterEach(cleanup)

const failure = (status) => Object.assign(new Error(`HTTP ${status}`), { status })

// queryFn answers each fetch in turn, so a test can succeed first and fail on the refetch.
function setup(...answers) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  let call = 0
  const queryFn = () => {
    const answer = answers[Math.min(call++, answers.length - 1)]
    return answer instanceof Error ? Promise.reject(answer) : answer
  }
  function Probe() {
    const query = useQuery({ queryKey: ['probe'], queryFn })
    // Rendered status lets a test wait until the UI has seen the refetch fail, not just the cache.
    return (
      <>
        <output>{query.status}</output>
        <ResourceBoundary query={query}>{(data) => <p>data: {data}</p>}</ResourceBoundary>
      </>
    )
  }
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Routes>
          <Route path="/" element={<Probe />} />
          <Route path="/login" element={<p>login page</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return { refetch: () => act(() => client.refetchQueries({ queryKey: ['probe'] })) }
}

describe('ResourceBoundary', () => {
  it('shows a spinner until the data arrives, then the data', async () => {
    setup(Promise.resolve('ok'))
    expect(screen.getByRole('progressbar')).toBeTruthy()
    expect(await screen.findByText('data: ok')).toBeTruthy()
  })
  it('shows an error when the fetch fails with nothing cached', async () => {
    setup(failure(500))
    expect(await screen.findByRole('alert')).toBeTruthy()
  })
  it('redirects to login on a 401', async () => {
    setup(failure(401))
    expect(await screen.findByText('login page')).toBeTruthy()
  })
  it('keeps the cached view when a background refetch fails', async () => {
    const { refetch } = setup('ok', failure(503))
    await screen.findByText('data: ok')
    await refetch()
    await waitFor(() => expect(screen.getByRole('status').textContent).toBe('error'))
    expect(screen.getByText('data: ok')).toBeTruthy()
    expect(screen.queryByRole('alert')).toBeNull()
  })
  it('redirects to login when a refetch finds the session gone, even with cached data', async () => {
    const { refetch } = setup('ok', failure(401))
    await screen.findByText('data: ok')
    await refetch()
    expect(await screen.findByText('login page')).toBeTruthy()
  })
})
