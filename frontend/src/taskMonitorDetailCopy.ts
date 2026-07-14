import type { TaskMonitorDetail } from '@/types'

type ClipboardWriter = (text: string) => Promise<void>

export type TaskMonitorDetailInfoRow = readonly [label: string, value: string]

export function formatTaskMonitorDateTime(value: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

export function getTaskMonitorDetailInfoRows(detail: TaskMonitorDetail): readonly TaskMonitorDetailInfoRow[] {
  return [
    ['Channel', detail.channel],
    ['Worker', `${detail.worker} / ${detail.provider}`],
    ['项目', detail.project_path],
    ['Task', detail.task_path],
    ['派发时间', formatTaskMonitorDateTime(detail.sent_at)],
    ['最近更新', formatTaskMonitorDateTime(detail.updated_at)],
    ['Handoff', detail.handoff_path ?? '尚无'],
  ]
}

export function buildTaskMonitorDetailCopyText(detail: TaskMonitorDetail): string {
  return getTaskMonitorDetailInfoRows(detail)
    .map(([label, value]) => `${label}：${value}`)
    .join('\n')
}

export async function copyTaskMonitorDetailInfo(
  detail: TaskMonitorDetail,
  writeText: ClipboardWriter,
): Promise<string> {
  const text = buildTaskMonitorDetailCopyText(detail)
  await writeText(text)
  return text
}
