import { cn } from '@/lib/utils'
import { Check, AlertTriangle, X } from 'lucide-react'

export type StepStatus = 'idle' | 'loading' | 'ok' | 'warning' | 'error'

interface StepBadgeProps {
  step: number
  status: StepStatus
  className?: string
}

export function StepBadge({ step, status, className }: StepBadgeProps) {
  return (
    <div
      className={cn(
        'relative flex size-8 items-center justify-center rounded-full text-xs font-bold transition-all duration-300 select-none shrink-0',
        status === 'idle' && 'bg-slate-100 border border-slate-200 text-slate-500 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-400',
        status === 'loading' && 'bg-blue-600 text-white animate-pulse-ring border border-blue-500',
        status === 'ok' && 'bg-emerald-500 text-white shadow-[0_2px_10px_rgba(16,185,129,0.35)]',
        status === 'warning' && 'bg-amber-500 text-white shadow-[0_2px_10px_rgba(245,158,11,0.35)]',
        status === 'error' && 'bg-rose-500 text-white shadow-[0_2px_10px_rgba(244,63,94,0.35)]',
        className
      )}
    >
      {status === 'ok' ? (
        <Check className="size-4 stroke-[3]" />
      ) : status === 'warning' ? (
        <AlertTriangle className="size-4 stroke-[3]" />
      ) : status === 'error' ? (
        <X className="size-4 stroke-[3]" />
      ) : (
        <span>{step}</span>
      )}
    </div>
  )
}
