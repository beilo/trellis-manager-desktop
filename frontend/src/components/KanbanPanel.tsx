import { useCallback, useEffect, useMemo, useState } from 'react'
import { LayoutDashboard, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { AppInput } from './AppInput'
import { KanbanTaskCard } from './KanbanTaskCard'
import { api } from '@/api'
import { useRefreshSubscription } from '@/refreshCoordinator'
import type { AllTasksSnapshot, TrellisTaskItem, TrellisTaskStatus } from '@/types'

type BoardColumn = 'planning' | 'in_progress' | 'completed'
type StatusFilter = 'all' | BoardColumn
type SortMode = 'project' | 'status' | 'created'

const COLUMN_TITLES: Record<BoardColumn, string> = {
  planning: '规划中',
  in_progress: '进行中',
  completed: '已完成',
}

const STATUS_FILTERS: Array<{ value: StatusFilter; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'planning', label: '规划中' },
  { value: 'in_progress', label: '进行中' },
  { value: 'completed', label: '已完成' },
]

const STATUS_ORDER: Record<TrellisTaskStatus, number> = {
  planning: 0,
  in_progress: 1,
  completed: 2,
  done: 2,
  unknown: 3,
}

interface KanbanPanelProps {
  onNavigateToTask: (projectPath: string, taskPath: string) => void
}

function countDone(counts: Record<string, number>): number {
  return (counts.completed ?? 0) + (counts.done ?? 0)
}

function normalizeColumn(task: TrellisTaskItem): BoardColumn | null {
  if (task.status === 'planning') return 'planning'
  if (task.status === 'in_progress') return 'in_progress'
  if (task.status === 'completed' || task.status === 'done') return 'completed'
  return null
}

function taskMatchesStatus(task: TrellisTaskItem, filter: StatusFilter): boolean {
  // 三列看板保留旧状态筛选语义：已完成筛选同时包含 completed 与 done。
  const column = normalizeColumn(task)
  return filter === 'all' || column === filter
}

function sortTasks(tasks: TrellisTaskItem[], mode: SortMode): TrellisTaskItem[] {
  return [...tasks].sort((a, b) => {
    if (mode === 'status') {
      const statusDiff = STATUS_ORDER[a.status] - STATUS_ORDER[b.status]
      if (statusDiff !== 0) return statusDiff
    }
    if (mode === 'created') {
      const aTime = a.created_at ? Date.parse(a.created_at) : 0
      const bTime = b.created_at ? Date.parse(b.created_at) : 0
      if (aTime !== bTime) return bTime - aTime
    }
    return a.title.localeCompare(b.title)
  })
}

export function KanbanPanel({ onNavigateToTask }: KanbanPanelProps) {
  const [snapshot, setSnapshot] = useState<AllTasksSnapshot | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [keyword, setKeyword] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [sortMode, setSortMode] = useState<SortMode>('project')

  const loadSnapshot = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.listAllTasks()
      setSnapshot(result)
    } catch (err) {
      setError(`加载看板失败：${err}`)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    void Promise.resolve().then(() => {
      if (cancelled) return
      void loadSnapshot()
    })
    return () => {
      cancelled = true
    }
  }, [loadSnapshot])

  useRefreshSubscription('kanban', ({ event }) => {
    if (event.type !== 'tasks') return

    void loadSnapshot().catch((err: unknown) => {
      console.error('自动刷新看板失败:', err)
    })
  })

  const boardColumns = useMemo(() => {
    const columns: Record<BoardColumn, Array<{ project_path: string; project_name: string; task: TrellisTaskItem }>> = {
      planning: [],
      in_progress: [],
      completed: [],
    }

    if (!snapshot) return columns

    const normalizedKeyword = keyword.trim().toLowerCase()
    const projects = [...snapshot.projects]
    if (sortMode === 'project') {
      projects.sort((a, b) => a.project_name.localeCompare(b.project_name))
    }

    for (const project of projects) {
      const tasks = sortTasks(
        project.tasks.filter((task) => {
          return normalizedKeyword ? task.title.toLowerCase().includes(normalizedKeyword) : true
        }),
        sortMode,
      )

      for (const task of tasks) {
        if (!taskMatchesStatus(task, statusFilter)) continue
        const column = normalizeColumn(task)
        if (!column) continue
        columns[column].push({ project_path: project.project_path, project_name: project.project_name, task })
      }
    }

    return columns
  }, [keyword, snapshot, sortMode, statusFilter])

  const totalCounts = snapshot?.total_counts ?? {}
  const hasProjects = (snapshot?.project_count ?? 0) > 0

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-5">
      <div className="flex flex-col gap-1 px-1">
        <h2 className="flex items-center gap-2 text-base font-bold tracking-tight text-foreground select-none">
          <LayoutDashboard className="size-4 text-violet-500" />
          <span>跨项目看板</span>
        </h2>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {/* 规划中 */}
        <Card className="premium-card overflow-hidden border-l-[3.5px] border-l-slate-400">
          <CardContent className="flex flex-col gap-1 px-4 py-3 select-none">
            <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider">规划中</span>
            <span className="text-2xl font-extrabold tracking-tight text-foreground">{totalCounts.planning ?? 0}</span>
          </CardContent>
        </Card>
        {/* 进行中 */}
        <Card className="premium-card overflow-hidden border-l-[3.5px] border-l-blue-500">
          <CardContent className="flex flex-col gap-1 px-4 py-3 select-none">
            <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider">进行中</span>
            <span className="text-2xl font-extrabold tracking-tight text-foreground">{totalCounts.in_progress ?? 0}</span>
          </CardContent>
        </Card>
        {/* 已完成 */}
        <Card className="premium-card overflow-hidden border-l-[3.5px] border-l-emerald-500">
          <CardContent className="flex flex-col gap-1 px-4 py-3 select-none">
            <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider">已完成</span>
            <span className="text-2xl font-extrabold tracking-tight text-foreground">{countDone(totalCounts)}</span>
          </CardContent>
        </Card>
        {/* 项目总数 */}
        <Card className="premium-card overflow-hidden border-l-[3.5px] border-l-violet-500">
          <CardContent className="flex flex-col gap-1 px-4 py-3 select-none">
            <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider">项目总数</span>
            <span className="text-2xl font-extrabold tracking-tight text-foreground">{snapshot?.project_count ?? 0}</span>
          </CardContent>
        </Card>
      </div>

      <Card className="premium-card border-border/30 bg-card/65">
        <CardContent className="flex flex-col gap-3 p-4">
          <div className="flex flex-wrap gap-2">
            {STATUS_FILTERS.map((filter) => (
              <Button
                key={filter.value}
                type="button"
                variant={statusFilter === filter.value ? 'default' : 'outline'}
                size="sm"
                className="transition-all duration-200"
                onClick={() => setStatusFilter(filter.value)}
              >
                {filter.label}
              </Button>
            ))}
          </div>
          <div className="grid min-w-0 flex-1 grid-cols-1 gap-2 sm:grid-cols-[minmax(0,1fr)_9rem_auto]">
            <AppInput
              className="min-w-0"
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder="搜索任务标题"
            />
            <select
              className="h-8 rounded-lg border border-border bg-background px-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/25 transition-all duration-150"
              value={sortMode}
              onChange={(event) => setSortMode(event.target.value as SortMode)}
              aria-label="排序"
            >
              <option value="project">按项目名</option>
              <option value="status">按状态</option>
              <option value="created">按创建时间</option>
            </select>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={loadSnapshot}
              disabled={loading}
              title="刷新"
            >
              <RefreshCw data-icon="inline-start" className={loading ? 'animate-spin' : undefined} />
              刷新
            </Button>
          </div>
        </CardContent>
      </Card>

      {error ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      ) : null}

      {!hasProjects && !loading ? (
        <div className="rounded-lg border bg-card px-5 py-12 text-center text-sm text-muted-foreground">
          暂无项目
        </div>
      ) : null}

      {hasProjects ? (
        <div className="overflow-x-auto pb-1">
          {/* 三列始终保留，空筛选结果也展示列占位，避免看板结构跳变。 */}
          <div className="grid min-w-[52rem] grid-cols-[repeat(3,minmax(0,1fr))] gap-4">
            {(Object.keys(COLUMN_TITLES) as BoardColumn[]).map((column) => {
              const tasks = boardColumns[column]
              return (
                <section key={column} className="flex min-h-0 flex-col gap-3 rounded-2xl border border-border/40 bg-card/65 p-3 shadow-sm">
                  <div className="flex items-center justify-between gap-3 select-none">
                    <h3 className="text-sm font-semibold text-foreground">{COLUMN_TITLES[column]}</h3>
                    <span className="shrink-0 text-xs text-muted-foreground bg-muted/60 px-2 py-0.5 rounded-full">{tasks.length} 个任务</span>
                  </div>
                  <ScrollArea className="h-[28rem]">
                    <div className="flex min-h-full flex-col gap-2 pr-2">
                      {tasks.length > 0 ? (
                        tasks.map(({ project_path, project_name, task }) => (
                          <KanbanTaskCard
                            key={task.path}
                            task={task}
                            projectName={project_name}
                            onClick={() => onNavigateToTask(project_path, task.path)}
                          />
                        ))
                      ) : (
                        <div className="flex min-h-[8rem] flex-col items-center justify-center rounded-xl border border-dashed border-border/30 bg-muted/5 px-4 py-8 text-center text-xs text-muted-foreground italic select-none">
                          <span>暂无任务</span>
                        </div>
                      )}
                    </div>
                  </ScrollArea>
                </section>
              )
            })}
          </div>
        </div>
      ) : null}
    </div>
  )
}
