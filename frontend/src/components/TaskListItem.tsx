import { FileText, Wrench, Package, Archive } from 'lucide-react'
import { TaskStatusBadge } from './TaskStatusBadge'
import type { TrellisTaskItem } from '@/types'

interface TaskListItemProps {
  task: TrellisTaskItem
  selected: boolean
  onSelect: (task: TrellisTaskItem) => void
}

export function TaskListItem({ task, selected, onSelect }: TaskListItemProps) {
  return (
    <div
      className={`flex flex-col gap-1 p-2 rounded cursor-pointer transition-colors ${
        selected ? 'bg-muted' : 'hover:bg-muted/50'
      } ${task.error ? 'bg-red-50 border border-red-200' : ''}`}
      onClick={() => onSelect(task)}
    >
      <div className="flex items-center gap-2">
        <TaskStatusBadge status={task.status} />
        <span className="text-sm font-medium truncate flex-1">{task.title}</span>
        {/* 归档标识 */}
        {task.archived && (
          <span className="flex items-center gap-1 text-xs text-muted-foreground shrink-0">
            <Archive className="size-3" />
            已归档 {task.archive_month}
          </span>
        )}
      </div>
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span className="truncate">{task.dir_name}</span>
        {task.child_total > 0 && (
          <span className="shrink-0">
            子任务 {task.child_done}/{task.child_total}
          </span>
        )}
        <div className="flex items-center gap-1 ml-auto shrink-0">
          {task.has_prd && <FileText className="size-3 text-blue-500" aria-label="PRD" />}
          {task.has_design && <Wrench className="size-3 text-orange-500" aria-label="Design" />}
          {task.has_implement && <Package className="size-3 text-green-500" aria-label="Implement" />}
        </div>
      </div>
      {task.error && (
        <div className="text-xs text-red-600 truncate">{task.error}</div>
      )}
    </div>
  )
}
