import { FolderGit2, Plus, Rows3, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import { StatusBadge } from './StatusBadge'
import type { ProjectStatus } from '@/types'

type HealthTone = 'ok' | 'warning' | 'error' | 'unknown'

interface HealthPillProps {
  tone: HealthTone
  label: string
  title: string
}

function HealthPill({ tone, label, title }: HealthPillProps) {
  const classes: Record<HealthTone, string> = {
    ok: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    warning: 'border-amber-200 bg-amber-50 text-amber-700',
    error: 'border-rose-200 bg-rose-50 text-rose-700',
    unknown: 'border-slate-200 bg-slate-50 text-slate-600',
  }

  return (
    <span className={cn('inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold', classes[tone])} title={title}>
      {label}
    </span>
  )
}

function projectHealth(status: ProjectStatus | undefined): Array<{ tone: HealthTone; label: string; title: string }> {
  if (!status) {
    return [{ tone: 'unknown', label: '未检查', title: '项目状态尚未加载' }]
  }

  const items: Array<{ tone: HealthTone; label: string; title: string }> = []
  if (!status.has_trellis) {
    items.push({ tone: 'warning', label: '未初始化', title: status.message })
  } else if (status.version_outdated) {
    items.push({ tone: 'warning', label: '版本过期', title: status.latest_version ? `当前 ${status.trellis_version ?? '-'}，最新 ${status.latest_version}` : status.message })
  }

  if (status.dirty) {
    items.push({ tone: 'error', label: 'Dirty', title: '项目工作区存在未提交修改' })
  }

  if (items.length === 0) {
    items.push({ tone: 'ok', label: '正常', title: status.message })
  }

  return items
}

function projectLabel(status: ProjectStatus | undefined): { label: string } {
  if (!status) return { label: '未检查' }
  if (!status.exists) return { label: '不存在' }
  if (!status.is_git) return { label: '非 Git' }
  if (!status.has_trellis) return { label: '未初始化' }
  if (status.version_outdated) return { label: '版本过期' }
  if (status.dirty) return { label: 'Dirty' }
  return { label: '正常' }
}

interface ProjectListProps {
  projects: string[]
  selectedProject: string | null
  statuses: Record<string, ProjectStatus>
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
  busy,
  batchUpdateCount,
  batchUpdateLoading,
  onAdd,
  onOpenBatchUpdate,
  onSelect,
  onRemove,
}: ProjectListProps) {
  return (
    <aside className="rounded-2xl border border-border/40 bg-card/80 dark:bg-card/75 backdrop-blur-md text-card-foreground overflow-hidden shadow-sm">
      <div className="flex items-center justify-between gap-3 border-b px-4 py-3">
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="text-sm font-bold text-foreground">项目列表</span>
          <span className="text-xs text-muted-foreground">
            {projects.length} 个本地项目 · {batchUpdateLoading ? '正在检查过期项目…' : batchUpdateCount > 0 ? `${batchUpdateCount} 个待更新` : '暂无待更新'}
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
              const status = projectStatus?.status ?? 'unknown'
              const health = projectHealth(projectStatus)
              const summary = projectLabel(projectStatus)
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
                    'group flex items-center gap-3 rounded-lg px-3 py-2.5 text-left cursor-pointer',
                    'transition-all duration-150 border border-transparent border-l-[3px]',
                    selected
                      ? 'bg-blue-50/70 dark:bg-blue-950/25 border-blue-500/5 dark:border-blue-500/10 border-l-blue-500 shadow-[0_2px_8px_rgba(59,130,246,0.04)]'
                      : 'border-l-transparent hover:bg-muted/65 hover:border-border/10',
                  )}
                >
                  <StatusBadge status={status} label={summary.label} className="px-2" />
                  <div className="flex min-w-0 flex-1 flex-col gap-1">
                    <div className="flex min-w-0 items-center gap-2">
                      <span className={cn(
                        'truncate text-sm font-semibold transition-colors duration-150',
                        selected ? 'text-blue-600 dark:text-blue-400' : 'text-foreground'
                      )}>
                        {projectName(path)}
                      </span>
                      <div className="flex min-w-0 shrink-0 flex-wrap gap-1">
                        {health.map((item) => (
                          <HealthPill key={`${path}-${item.label}`} tone={item.tone} label={item.label} title={item.title} />
                        ))}
                      </div>
                    </div>
                    <span className="truncate text-xs text-muted-foreground" title={`${path}\n${projectStatus?.message ?? '状态尚未加载'}`}>
                      {path}
                    </span>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-7 shrink-0 opacity-0 group-hover:opacity-100 focus:opacity-100"
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
