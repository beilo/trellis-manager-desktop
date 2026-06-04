import { FolderGit2, Loader2, Plus, Rows3, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import { StatusBadge } from './StatusBadge'
import type { ProjectStatus, ProjectTaskCounts, Status } from '@/types'



function getProjectDisplayStatus(status: ProjectStatus | undefined): Status {
  if (!status) return 'unknown'
  if (!status.exists) return 'error'
  if (!status.is_git) return 'error'
  if (!status.has_trellis) return 'info' // 未初始化用 info (蓝色)
  if (status.version_outdated) return 'warning' // 版本过期用 warning (黄色)
  if (status.dirty) return 'dirty' // dirty 用 dirty (橙色)
  return 'ok' // 正常用 ok (绿色)
}

function TaskCountPill({ count, loading }: { count: number; loading: boolean }) {
  // 项目列表只展示 active 进行中任务数，避免把归档任务混进左侧导航。
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full border border-primary/20 bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary"
      title="进行中任务数"
    >
      {loading && <Loader2 className="size-2.5 animate-spin" />}
      进行中 {count}
    </span>
  )
}

interface ProjectListProps {
  projects: string[]
  selectedProject: string | null
  statuses: Record<string, ProjectStatus>
  taskCounts: ProjectTaskCounts
  taskCountsLoading: boolean
  busy: boolean
  batchUpdateCount: number
  batchUpdateLoading: boolean
  onAdd: () => void
  onOpenBatchUpdate: () => void
  onSelect: (path: string) => void
  onRemove: (path: string) => void
}

function projectName(path: string): string {
  const normalized = path.replace(/[\\/]+$/, '')
  return normalized.split(/[\\/]/).pop() || normalized
}

export function ProjectList({
  projects,
  selectedProject,
  statuses,
  taskCounts,
  taskCountsLoading,
  busy,
  batchUpdateCount,
  batchUpdateLoading,
  onAdd,
  onOpenBatchUpdate,
  onSelect,
  onRemove,
}: ProjectListProps) {
  return (
    <aside className="rounded-xl border border-border/40 bg-card/80 dark:bg-card/75 backdrop-blur-md text-card-foreground overflow-hidden shadow-sm">
      <div className="flex items-center justify-between gap-3 border-b px-4 py-3">
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="text-sm font-semibold text-foreground">项目列表</span>
          <span className="text-xs text-muted-foreground">
            {projects.length} 个本地项目
            · {batchUpdateLoading ? '正在检查过期项目…' : batchUpdateCount > 0 ? `${batchUpdateCount} 个待更新` : '暂无待更新'}
            {taskCountsLoading ? ' · 正在刷新任务数…' : ''}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={onOpenBatchUpdate} disabled={busy || batchUpdateLoading || batchUpdateCount === 0}>
            <Rows3 data-icon="inline-start" />
            批量更新
          </Button>
          <Button variant="outline" size="sm" onClick={onAdd} disabled={busy}>
            <Plus data-icon="inline-start" />
            添加
          </Button>
        </div>
      </div>

      <ScrollArea className="h-[26rem]">
        {projects.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 px-5 py-16 text-center">
            <div className="flex size-10 items-center justify-center rounded-full border bg-muted text-muted-foreground">
              <FolderGit2 className="size-5" />
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-sm font-semibold text-foreground">尚未添加项目</span>
              <span className="text-xs text-muted-foreground">
                点击添加后选择本地 Git 项目目录。
              </span>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-1 p-2">
            {projects.map((path) => {
              const selected = path === selectedProject
              const projectStatus = statuses[path]
              const displayStatus = getProjectDisplayStatus(projectStatus)
              const counts = taskCounts[path]
              const showCounts = Boolean(counts) || Boolean(projectStatus?.has_trellis)
              const inProgressCount = counts?.in_progress ?? 0
              return (
                <div
                  key={path}
                  role="button"
                  tabIndex={0}
                  onClick={() => onSelect(path)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') onSelect(path)
                  }}
                  className={cn(
                    'group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-left cursor-pointer',
                    'transition-all duration-150 border border-transparent border-l-[3px]',
                    selected
                      ? 'bg-primary/5 dark:bg-primary/10 border-primary/5 dark:border-primary/10 border-l-primary shadow-[0_2px_8px_rgba(204,120,92,0.03)]'
                      : 'border-l-transparent hover:bg-muted/65 hover:border-border/10',
                  )}
                >
                  <div className="flex min-w-0 flex-1 flex-col gap-1.5 pr-6">
                    {/* 第一行：状态点 + 项目名 + 活跃任务数 */}
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0 flex-1">
                        <StatusBadge status={displayStatus} variant="dot" className="mt-0.5" />
                        <span className={cn(
                          'truncate text-sm font-semibold transition-colors duration-150',
                          selected ? 'text-primary' : 'text-foreground'
                        )}>
                          {projectName(path)}
                        </span>
                      </div>
                      {showCounts && inProgressCount > 0 && (
                        <div className="shrink-0">
                          <TaskCountPill count={inProgressCount} loading={taskCountsLoading && !counts} />
                        </div>
                      )}
                    </div>
                    {/* 第二行：项目路径 */}
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-xs text-muted-foreground flex-1" title={`${path}\n${projectStatus?.message ?? '状态尚未加载'}`}>
                        {path}
                      </span>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="absolute right-2 top-1/2 -translate-y-1/2 size-7 shrink-0 opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity duration-150 rounded-full"
                    onClick={(event) => {
                      event.stopPropagation()
                      onRemove(path)
                    }}
                    disabled={busy}
                    title="移除项目"
                  >
                    <X />
                  </Button>
                </div>
              )
            })}
          </div>
        )}
      </ScrollArea>
    </aside>
  )
}
