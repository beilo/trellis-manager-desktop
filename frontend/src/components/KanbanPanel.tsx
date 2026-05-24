import { useCallback, useEffect, useMemo, useState } from 'react'
import { LayoutDashboard, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { AppInput } from './AppInput'
import { KanbanTaskCard } from './KanbanTaskCard'
import { api } from '@/api'
import type {
  AllTasksSnapshot,
  ProjectTasksBlock,
  TrellisTaskItem,
  TrellisTaskStatus,
} from '@/types'

type StatusFilter = 'all' | 'planning' | 'in_progress' | 'completed'
type SortMode = 'project' | 'status' | 'created'

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

function taskMatchesStatus(task: TrellisTaskItem, status: StatusFilter): boolean {
  if (status === 'all') return true
  if (status === 'completed') return task.status === 'completed' || task.status === 'done'
  return task.status === status
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
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [keyword, setKeyword] = useState('')
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

  const visibleProjects = useMemo(() => {
    if (!snapshot) return []
    const normalizedKeyword = keyword.trim().toLowerCase()
    const blocks = snapshot.projects
      .map((project): ProjectTasksBlock => {
        const tasks = project.tasks.filter((task) => {
          const matchesKeyword = normalizedKeyword
            ? task.title.toLowerCase().includes(normalizedKeyword)
            : true
          return matchesKeyword && taskMatchesStatus(task, statusFilter)
        })
        return { ...project, tasks: sortTasks(tasks, sortMode) }
      })
      .filter((project) => project.tasks.length > 0)

    // 项目分组是 PRD 的主展示形态；排序只调整组顺序或组内任务顺序。
    if (sortMode === 'project') {
      return [...blocks].sort((a, b) => a.project_name.localeCompare(b.project_name))
    }
    return blocks
  }, [keyword, snapshot, sortMode, statusFilter])

  const totalCounts = snapshot?.total_counts ?? {}
  const hasProjects = (snapshot?.project_count ?? 0) > 0
  const hasVisibleTasks = visibleProjects.length > 0

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-5">
      <div className="flex flex-col gap-1 px-1">
        <h2 className="flex items-center gap-2 text-base font-bold tracking-tight text-foreground select-none">
          <LayoutDashboard className="size-4 text-violet-500" />
          <span>跨项目看板</span>
        </h2>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Card size="sm">
          <CardHeader>
            <CardTitle>规划中 {totalCounts.planning ?? 0}</CardTitle>
          </CardHeader>
        </Card>
        <Card size="sm">
          <CardHeader>
            <CardTitle>进行中 {totalCounts.in_progress ?? 0}</CardTitle>
          </CardHeader>
        </Card>
        <Card size="sm">
          <CardHeader>
            <CardTitle>已完成 {countDone(totalCounts)}</CardTitle>
          </CardHeader>
        </Card>
        <Card size="sm">
          <CardHeader>
            <CardTitle>项目总数 {snapshot?.project_count ?? 0}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <Card>
        <CardContent className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <div className="flex flex-wrap gap-2">
            {STATUS_FILTERS.map((item) => (
              <Button
                key={item.value}
                type="button"
                variant={statusFilter === item.value ? 'default' : 'outline'}
                size="sm"
                onClick={() => setStatusFilter(item.value)}
              >
                {item.label}
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
              className="h-8 rounded-lg border border-border bg-background px-2 text-sm"
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

      {hasProjects && !hasVisibleTasks && !loading ? (
        <div className="rounded-lg border bg-card px-5 py-12 text-center text-sm text-muted-foreground">
          暂无匹配任务
        </div>
      ) : null}

      {hasVisibleTasks ? (
        <div className="flex flex-col gap-4">
          {visibleProjects.map((project) => (
            <section key={project.project_path} className="flex flex-col gap-2">
              <div className="flex items-center justify-between gap-3 px-1">
                <h3 className="truncate text-sm font-semibold text-foreground">
                  {project.project_name}
                </h3>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {project.tasks.length} 个任务
                </span>
              </div>
              <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
                {project.tasks.map((task) => (
                  <KanbanTaskCard
                    key={task.path}
                    task={task}
                    projectName={project.project_name}
                    onClick={() => onNavigateToTask(project.project_path, task.path)}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      ) : null}
    </div>
  )
}
