import { cn } from '@/lib/utils'
import type { TrellisTaskItem, TrellisTaskStatus } from '@/types'

const STATUS_DOT_CLASS: Record<TrellisTaskStatus, string> = {
  planning: 'bg-blue-500 shadow-[0_0_6px_rgba(59,130,246,0.6)]',
  in_progress: 'bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.6)] animate-pulse',
  completed: 'bg-slate-400',
  done: 'bg-slate-400',
  unknown: 'bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.6)]',
}

// 看板卡片只做概览入口，完整操作继续交给项目 Tab 的 TaskDetail。
interface KanbanTaskCardProps {
  task: TrellisTaskItem
  projectName: string
  onClick: () => void
}

export function KanbanTaskCard({ task, projectName, onClick }: KanbanTaskCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex w-full items-center gap-3 rounded-xl border border-border/40 bg-card px-3.5 py-2.5 text-left text-card-foreground',
        'transition-all duration-200 hover:border-border/80 hover:bg-accent/60 hover:shadow-md hover:-translate-y-[0.5px]',
        'focus:outline-none focus:ring-2 focus:ring-ring/20',
      )}
      aria-label={`打开任务 ${task.title}`}
    >
      <span className={cn('size-2 shrink-0 rounded-full', STATUS_DOT_CLASS[task.status])} />
      <span className="min-w-0 flex-1 truncate text-xs font-semibold text-foreground/90">{task.title}</span>
      <span className="max-w-32 shrink-0 truncate text-[10px] font-semibold font-mono bg-background text-muted px-1.5 py-0.5 rounded border border-border/40">
        {projectName}
      </span>
    </button>
  )
}
