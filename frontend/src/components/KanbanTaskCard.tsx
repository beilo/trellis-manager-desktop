import { cn } from '@/lib/utils'
import type { TrellisTaskItem, TrellisTaskStatus } from '@/types'

const STATUS_DOT_CLASS: Record<TrellisTaskStatus, string> = {
  planning: 'bg-blue-500',
  in_progress: 'bg-green-500',
  completed: 'bg-muted-foreground',
  done: 'bg-muted-foreground',
  unknown: 'bg-red-500',
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
        'flex w-full items-center gap-3 rounded-lg border bg-card px-3 py-2 text-left text-card-foreground',
        'transition-all duration-150 hover:border-foreground/20 hover:bg-muted/50 hover:shadow-sm',
        'focus:outline-none focus:ring-3 focus:ring-ring/30',
      )}
      aria-label={`打开任务 ${task.title}`}
    >
      <span className={cn('size-2.5 shrink-0 rounded-full', STATUS_DOT_CLASS[task.status])} />
      <span className="min-w-0 flex-1 truncate text-sm font-medium">{task.title}</span>
      <span className="max-w-40 shrink-0 truncate text-xs text-muted-foreground">
        {projectName}
      </span>
    </button>
  )
}
