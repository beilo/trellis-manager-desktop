import { cn } from '@/lib/utils'
import type { Status } from '@/types'

const STATUS_CONFIG: Record<
  Status,
  { bg: string; border: string; text: string; dot: string; label: string }
> = {
  ok: {
    bg: 'bg-emerald-500/8 dark:bg-emerald-500/10',
    border: 'border-emerald-500/20 dark:border-emerald-500/30',
    text: 'text-emerald-600 dark:text-emerald-400',
    dot: 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]',
    label: '就绪',
  },
  warning: {
    bg: 'bg-amber-500/8 dark:bg-amber-500/10',
    border: 'border-amber-500/20 dark:border-amber-500/30',
    text: 'text-amber-600 dark:text-amber-400',
    dot: 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.6)]',
    label: '警告',
  },
  error: {
    bg: 'bg-rose-500/8 dark:bg-rose-500/10',
    border: 'border-rose-500/20 dark:border-rose-500/30',
    text: 'text-rose-600 dark:text-rose-400',
    dot: 'bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.6)] animate-pulse',
    label: '异常',
  },
  unknown: {
    bg: 'bg-slate-500/5 dark:bg-slate-500/8',
    border: 'border-slate-500/15 dark:border-slate-500/20',
    text: 'text-slate-500 dark:text-slate-400',
    dot: 'bg-slate-400 dark:bg-slate-500',
    label: '等待',
  },
  info: {
    bg: 'bg-sky-500/8 dark:bg-sky-500/10',
    border: 'border-sky-500/20 dark:border-sky-500/30',
    text: 'text-sky-600 dark:text-sky-400',
    dot: 'bg-sky-500 shadow-[0_0_8px_rgba(14,165,233,0.45)]',
    label: '提示',
  },
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
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold tabular-nums shrink-0',
        'transition-all duration-300 ease-in-out select-none',
        config.bg,
        config.border,
        config.text,
        className,
      )}
    >
      <span className={cn('size-1.5 rounded-full shrink-0', config.dot)} />
      <span className="truncate max-w-24">{text}</span>
    </span>
  )
}
