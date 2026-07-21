import { http } from './http'
import type { ApsRunResult } from '@/types/aps'
import type { PendingAdjustment } from '@/stores/aps-store'

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
