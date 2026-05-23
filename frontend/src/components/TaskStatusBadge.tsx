import { Badge } from '@/components/ui/badge'
import type { TrellisTaskStatus } from '@/types'

const STATUS_CONFIG: Record<TrellisTaskStatus, { label: string; className: string }> = {
  planning: { label: '规划中', className: 'bg-blue-100 text-blue-800' },
  in_progress: { label: '进行中', className: 'bg-green-100 text-green-800' },
  completed: { label: '已完成', className: 'bg-gray-100 text-gray-800' },
  done: { label: '已完成', className: 'bg-gray-100 text-gray-800' },
  unknown: { label: '未知', className: 'bg-red-100 text-red-800' },
}

interface TaskStatusBadgeProps {
  status: TrellisTaskStatus
}

export function TaskStatusBadge({ status }: TaskStatusBadgeProps) {
  const config = STATUS_CONFIG[status]
  return <Badge className={config.className}>{config.label}</Badge>
}
