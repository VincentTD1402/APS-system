import { http } from './http'
import type { ApsRunResult } from '@/types/aps'

// Kept for potential future use; not called from the mock-only APS store.
interface PendingAdjustment {
  planId: string
  newStart: string
  newEnd: string
}

export async function runAps(): Promise<ApsRunResult> {
  const { data } = await http.post<ApsRunResult>('/aps/run')
  return data
}

export async function adjustAps(
  runId: string | null,
  adjustments: PendingAdjustment[]
): Promise<ApsRunResult> {
  const { data } = await http.post<ApsRunResult>('/aps/adjust', { runId, adjustments })
  return data
}
