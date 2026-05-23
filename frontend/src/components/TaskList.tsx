import { ChevronRight, ChevronDown, FolderArchive } from 'lucide-react'
import { useState } from 'react'
import { TaskListItem } from './TaskListItem'
import type { TrellisTaskItem, TrellisTaskStatus, ArchiveMonthGroup } from '@/types'

const STATUS_ORDER: TrellisTaskStatus[] = [
  'in_progress', 'planning', 'unknown', 'completed', 'done'
]

/** 构建层级树：顶层为无 parent 的任务，子任务嵌套显示 */
function buildTaskTree(tasks: TrellisTaskItem[]): TrellisTaskItem[] {
  const childSet = new Set<string>()
  // 收集所有子任务 dir_name
  for (const t of tasks) {
    for (const c of t.children) {
      childSet.add(c)
    }
    if (t.parent) {
      childSet.add(t.parent) // parent 字段也标记为子任务
    }
  }
  // 顶层：既不是别人的子任务，也没有 parent
  const top = tasks.filter(t => !childSet.has(t.dir_name))
  return [...top].sort((a, b) => {
    const aIdx = STATUS_ORDER.indexOf(a.status)
    const bIdx = STATUS_ORDER.indexOf(b.status)
    if (aIdx !== bIdx) return aIdx - bIdx
    return b.dir_name.localeCompare(a.dir_name)
  })
}

interface TaskListProps {
  tasks: TrellisTaskItem[]
  archivedGroups: ArchiveMonthGroup[]
  archiveCounts: Record<string, number>
  showArchive: boolean
  selectedTask: TrellisTaskItem | null
  onSelect: (task: TrellisTaskItem) => void
}

/** 归档月份折叠组 */
function ArchiveMonthSection({
  group,
  selectedTask,
  onSelect,
}: {
  group: ArchiveMonthGroup
  selectedTask: TrellisTaskItem | null
  onSelect: (task: TrellisTaskItem) => void
}) {
  const [open, setOpen] = useState(false)

  return (
    <div>
      <div
        className="flex items-center gap-2 p-2 cursor-pointer hover:bg-muted/50 rounded text-sm"
        onClick={() => setOpen(!open)}
      >
        {open ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
        <FolderArchive className="size-3 text-muted-foreground" />
        <span className="font-medium">{group.month}</span>
        <span className="text-muted-foreground">{group.tasks.length} 个任务</span>
        {group.error_count > 0 && (
          <span className="text-red-500 text-xs">{group.error_count} 个损坏</span>
        )}
      </div>
      {open && (
        <div className="ml-4 flex flex-col gap-1">
          {group.tasks.map((task) => (
            <TaskListItem
              key={task.path}
              task={task}
              selected={selectedTask?.path === task.path}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export function TaskList({
  tasks,
  archivedGroups,
  archiveCounts,
  showArchive,
  selectedTask,
  onSelect,
}: TaskListProps) {
  // 构建子任务查找表
  const taskMap = new Map(tasks.map(t => [t.dir_name, t]))
  const topTasks = buildTaskTree(tasks)

  return (
    <div className="flex flex-col gap-1">
      {/* 当前任务分区 */}
      <div className="text-xs text-muted-foreground font-medium px-2 pb-1">当前任务</div>
      {topTasks.map((task) => {
        const childTasks = task.children
          .map(c => taskMap.get(c))
          .filter((c): c is TrellisTaskItem => c !== undefined)

        return (
          <div key={task.path}>
            <TaskListItem
              task={task}
              selected={selectedTask?.path === task.path}
              onSelect={onSelect}
            />
            {childTasks.length > 0 && (
              <div className="ml-4 border-l border-muted pl-2">
                {childTasks.map(child => (
                  <TaskListItem
                    key={child.path}
                    task={child}
                    selected={selectedTask?.path === child.path}
                    onSelect={onSelect}
                  />
                ))}
              </div>
            )}
          </div>
        )
      })}

      {/* 归档任务分区 */}
      {showArchive && archivedGroups.length > 0 && (
        <>
          <div className="text-xs text-muted-foreground font-medium px-2 pt-3 pb-1">
            归档任务（共 {archiveCounts.total ?? 0} 个）
          </div>
          {archivedGroups.map(group => (
            <ArchiveMonthSection
              key={group.month}
              group={group}
              selectedTask={selectedTask}
              onSelect={onSelect}
            />
          ))}
        </>
      )}
    </div>
  )
}
