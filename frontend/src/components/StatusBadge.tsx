import { cn } from '@/lib/utils'
import type { Status } from '@/types'

const STATUS_CONFIG: Record<Status, { bg: string; text: string; label: string }> = {
  ok: { bg: 'bg-green-100 border-green-200', text: 'text-green-800', label: 'OK' },
  warning: { bg: 'bg-yellow-100 border-yellow-200', text: 'text-yellow-800', label: '注意' },
  error: { bg: 'bg-red-100 border-red-200', text: 'text-red-800', label: '错误' },
  unknown: { bg: 'bg-muted border-border', text: 'text-muted-foreground', label: '等待' },
}

interface StatusBadgeProps {
  status: Status
  label?: string
  className?: string
}

export function StatusBadge({ status, label, className }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.unknown
  const text = label ?? config.label

  return (
    <span
      className={cn(
        'inline-flex items-center justify-center rounded-full border px-3 py-1 text-xs font-bold tabular-nums shrink-0',
        'transition-all duration-300 ease-in-out',
        config.bg,
        config.text,
        className,
      )}
    >
      {text}
    </span>
  )
}
