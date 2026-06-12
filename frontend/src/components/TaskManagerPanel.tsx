import { useCallback, useEffect, useState } from 'react'
import { Loader2, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { TaskList } from './TaskList'
import { TaskDetail, type TaskDetailTab } from './TaskDetail'
import { api } from '@/api'
import { useRefreshSubscription } from '@/refreshCoordinator'
import type { EnvironmentItem, TrellisTaskSnapshot, TrellisTaskItem, ProjectStatus } from '@/types'

interface TaskManagerPanelProps {
  projectPath: string | null
  projectStatus: ProjectStatus | null
  highlightTaskPath?: string | null
  cursorStatus: EnvironmentItem | null
  cursorLoading: boolean
  onOpenCursor: (path?: string) => Promise<void>
  onHighlightConsumed?: () => void
  highlightedTaskInitialTab?: TaskDetailTab
}

function EmptyState({ message, action }: { message: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-8 text-muted-foreground">
      <span>{message}</span>
      {action}
    </div>
  )
}

export function TaskManagerPanel({
  projectPath,
  projectStatus,
  highlightTaskPath = null,
  cursorStatus,
  cursorLoading,
  onOpenCursor,
  onHighlightConsumed,
  highlightedTaskInitialTab = 'detail',
}: TaskManagerPanelProps) {
  const [snapshot, setSnapshot] = useState<TrellisTaskSnapshot | null>(null)
  const [loading, setLoading] = useState(false)
  const [selectedTask, setSelectedTask] = useState<TrellisTaskItem | null>(null)
  const [includeArchive, setIncludeArchive] = useState(false)
  const [helmStatus, setHelmStatus] = useState<EnvironmentItem | null>(null)
  const [helmLoading, setHelmLoading] = useState(false)
  const [detailInitialTab, setDetailInitialTab] = useState<TaskDetailTab>('detail')

  const loadTasks = useCallback(async () => {
    if (!projectPath) return
    setLoading(true)
    setHelmLoading(true)
    try {
      const snap = await api.listProjectTasks(projectPath, includeArchive)
      setSnapshot(snap)
      // 刷新后保持选中，或在 active 任务中选第一个。
      const activeTasks = snap.tasks.filter(t => !t.archived)
      const highlightedTask = highlightTaskPath
        ? snap.tasks.find(t => t.path === highlightTaskPath) ?? null
        : null
      setSelectedTask((current) => {
        if (highlightedTask) {
          setDetailInitialTab(highlightedTaskInitialTab)
          return highlightedTask
        }
        if (activeTasks.length > 0 && !current) {
          return activeTasks[0]
        }
        if (current) {
          // 优先从 active 找，再从归档找。
          const stillExists = snap.tasks.find(t => t.path === current.path)
          if (!stillExists) {
            return activeTasks[0] ?? snap.tasks[0] ?? null
          }
          return stillExists
        }
        return null
      })
      if (highlightTaskPath) {
        // 外部高亮只消费一次，避免后续刷新反复抢占用户当前选中任务。
        onHighlightConsumed?.()
      }
      // Helm 状态跟随任务刷新一起更新，用于详情按钮禁用原因。
      const status = await api.checkHelmStatus()
      setHelmStatus(status)
    } catch (err) {
      console.error('加载任务失败:', err)
    } finally {
      setLoading(false)
      setHelmLoading(false)
    }
  }, [projectPath, includeArchive, highlightTaskPath, highlightedTaskInitialTab, onHighlightConsumed])

  useEffect(() => {
    let cancelled = false
    void Promise.resolve().then(() => {
      if (cancelled) return
      if (projectStatus?.has_trellis) {
        void loadTasks()
      } else {
        setSnapshot(null)
        setSelectedTask(null)
        setHelmStatus(null)
      }
    })
    return () => {
      cancelled = true
    }
  }, [projectStatus?.has_trellis, loadTasks])

  useRefreshSubscription('tasks', ({ event }) => {
    if (event.type !== 'tasks') return
    if (!projectPath || !projectStatus?.has_trellis) return
    if (event.projectPath !== projectPath) return

    void loadTasks().catch((err: unknown) => {
      console.error('自动刷新任务失败:', err)
    })
  })

  if (!projectPath) {
    return <EmptyState message="请先选择项目" />
  }

  if (!projectStatus?.has_trellis) {
    return (
      <EmptyState
        message="该项目尚未初始化 Trellis"
        action={
          <span className="text-xs mt-2">在项目中心执行 Init 初始化</span>
        }
      />
    )
  }

  if (loading && !snapshot) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="animate-spin" />
      </div>
    )
  }

  const activeTasks = snapshot?.tasks.filter((t: TrellisTaskItem) => !t.archived) ?? []

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <span className="font-medium">任务管理</span>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={includeArchive}
              onChange={(e) => setIncludeArchive(e.target.checked)}
            />
            显示归档
          </label>
          <Button size="sm" variant="ghost" onClick={loadTasks} disabled={loading} title="刷新">
            <RefreshCw className={`size-3 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* Active 统计 */}
      {snapshot && (
        <div className="flex gap-3 text-xs text-muted-foreground">
          <span>规划中: {snapshot.counts.planning ?? 0}</span>
          <span>进行中: {snapshot.counts.in_progress ?? 0}</span>
          <span>已完成: {(snapshot.counts.completed ?? 0) + (snapshot.counts.done ?? 0)}</span>
          {snapshot.counts.unknown > 0 && (
            <span className="text-red-500">未知: {snapshot.counts.unknown}</span>
          )}
          {includeArchive && snapshot.archive_counts.total > 0 && (
            <span className="ml-2 border-l border-muted pl-2">
              归档: {snapshot.archive_counts.total}
            </span>
          )}
        </div>
      )}

      {snapshot && activeTasks.length === 0 && !includeArchive && (
        <EmptyState message="暂无任务" />
      )}

      {snapshot && (activeTasks.length > 0 || includeArchive) && (
        // Markdown 文档可能包含长表格或长代码，grid 轨道必须允许子项收缩，否则右侧详情会把两栏布局撑宽。
        <div className="grid grid-cols-1 gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="min-w-0">
            <TaskList
              tasks={activeTasks}
              archivedGroups={snapshot.archived_groups}
              archiveCounts={snapshot.archive_counts}
              showArchive={includeArchive}
              selectedTask={selectedTask}
              onSelect={setSelectedTask}
            />
          </div>
          {selectedTask && (
            <div className="min-w-0">
              <TaskDetail
                task={selectedTask}
                projectPath={projectPath}
                initialTab={detailInitialTab}
                helmStatus={helmStatus}
                helmLoading={helmLoading}
                cursorStatus={cursorStatus}
                cursorLoading={cursorLoading}
                onOpenDir={(path) => api.openTaskDirectory(path)}
                onOpenIterm={(path) => api.openInIterm(path)}
                onOpenCursor={onOpenCursor}
                onPushHelm={(currentProjectPath, taskPath) => api.pushTaskToHelm(currentProjectPath, taskPath)}
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
