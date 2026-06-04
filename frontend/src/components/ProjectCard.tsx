import { Loader2, FolderOpen, SquareArrowOutUpRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { StatusBadge } from './StatusBadge'
import { cn } from '@/lib/utils'
import { StepBadge, type StepStatus } from './StepBadge'
import type { EnvironmentItem, ProjectStatus } from '@/types'

interface ProjectCardProps {
  projectPath: string | null
  status: ProjectStatus | null
  loading: boolean
  busy: boolean
  allowDirty: boolean
  onCheck: () => void
  onInit: () => void
  onUpdate: () => void
  onOpenDir: () => void
  onOpenCursor: () => Promise<void>
  cursorStatus: EnvironmentItem | null
  cursorLoading: boolean
  onAllowDirtyChange: (v: boolean) => void
}

export function ProjectCard({
  projectPath,
  status,
  loading,
  busy,
  allowDirty,
  onCheck,
  onInit,
  onUpdate,
  onOpenDir,
  onOpenCursor,
  cursorStatus,
  cursorLoading,
  onAllowDirtyChange,
}: ProjectCardProps) {
  const projectStatus = status?.status ?? 'unknown'
  const recommendInit = Boolean(projectPath && status && status.exists && status.is_git && !status.has_trellis)
  const recommendUpdate = Boolean(projectPath && status && status.exists && status.is_git && status.has_trellis && status.version_outdated)

  const cursorDisabledReason = cursorLoading
    ? '正在检查 Cursor'
    : cursorStatus && !cursorStatus.ok
      ? cursorStatus.message
      : null

  let stepStatus: StepStatus = 'idle'
  if (busy || loading) {
    stepStatus = 'loading'
  } else if (projectPath && status) {
    if (status.status === 'ok') stepStatus = 'ok'
    else if (status.status === 'warning') stepStatus = 'warning'
    else if (status.status === 'error') stepStatus = 'error'
  }

  let detailText = '请先在左侧添加或选择业务项目'
  let badgeLabel: string | undefined
  if (status?.path) {
    detailText = status.message
  }
  if (loading) badgeLabel = '检查中…'
  else if (!projectPath) badgeLabel = '未选择'

  return (
    <Card className="premium-card">
      <CardHeader className="flex flex-row items-start justify-between gap-4 pb-3">
        <div className="flex items-center gap-3">
          <StepBadge step={4} status={stepStatus} />
          <div className="flex flex-col gap-0.5">
            <span className="text-base font-bold text-foreground select-none">业务项目操作</span>
            <span className="text-xs text-muted-foreground select-none">
              对当前选中项目执行检查、Init 或 Update。
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Button variant="outline" size="sm" onClick={onCheck} disabled={loading || busy || !projectPath}>
            {loading && <Loader2 className="size-3 animate-spin" data-icon="inline-start" />}
            {loading ? '检查中…' : '检查项目'}
          </Button>
          <Button
            size="sm"
            onClick={onInit}
            disabled={busy || !projectPath}
            className={cn(
              "transition-all duration-200 font-semibold",
              recommendInit
                ? "bg-primary hover:bg-primary/90 text-primary-foreground border-transparent shadow-sm active:scale-95"
                : "border border-border bg-background hover:bg-muted"
            )}
          >
            {busy && <Loader2 className="size-3 animate-spin" data-icon="inline-start" />}
            {busy ? '处理中…' : 'Init'}
          </Button>
          <Button
            size="sm"
            onClick={onUpdate}
            disabled={busy || !projectPath}
            className={cn(
              "transition-all duration-200 font-semibold",
              recommendUpdate
                ? "bg-primary hover:bg-primary/90 text-primary-foreground border-transparent shadow-sm active:scale-95"
                : "border border-border bg-background hover:bg-muted"
            )}
          >
            {busy && <Loader2 className="size-3 animate-spin" data-icon="inline-start" />}
            {busy ? '处理中…' : 'Update'}
          </Button>
          <Button variant="outline" size="sm" onClick={onOpenDir} disabled={!projectPath}>
            <FolderOpen className="size-3" data-icon="inline-start" />
            打开目录
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void onOpenCursor()}
            disabled={!projectPath || cursorLoading || !cursorStatus?.ok}
            title={!projectPath ? '请先选择项目' : cursorDisabledReason ?? '在 Cursor 中打开当前项目'}
          >
            {cursorLoading ? (
              <Loader2 className="size-3 animate-spin" data-icon="inline-start" />
            ) : (
              <SquareArrowOutUpRight className="size-3" data-icon="inline-start" />
            )}
            在 Cursor 中打开
          </Button>
        </div>
      </CardHeader>

      <CardContent className="flex flex-col gap-4 pt-0">
        <div className="flex flex-col gap-1.5">
          <span className="text-xs text-muted-foreground font-medium">项目路径</span>
          <div
            className="min-h-10 rounded-lg border bg-muted/35 px-3 py-2 font-mono text-sm text-foreground"
            title={projectPath ?? undefined}
          >
            <span className="block truncate">
              {projectPath ?? '未选择项目'}
            </span>
          </div>
        </div>

        {projectPath && status && (status.status === 'warning' || status.status === 'error') ? (
          <div className={cn(
            "rounded-xl border p-3 flex items-start gap-2.5 text-sm transition-all duration-200 shadow-sm",
            status.status === 'warning'
              ? "bg-amber-500/10 border-amber-500/20 text-amber-800 dark:text-amber-300"
              : "bg-rose-500/10 border-rose-500/20 text-rose-800 dark:text-rose-300"
          )}>
            <span className={cn(
              "size-2 rounded-full mt-1.5 shrink-0 animate-pulse",
              status.status === 'warning' ? "bg-amber-500" : "bg-rose-500"
            )} />
            <div className="flex-1 min-w-0">
              <span className="font-bold text-[10px] uppercase tracking-wider block mb-0.5 opacity-80">
                {status.status === 'warning' ? '项目配置警告' : '项目配置异常'}
              </span>
              <span className="text-xs leading-relaxed block font-medium">{detailText}</span>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-3">
            <StatusBadge
              status={projectPath ? projectStatus : 'unknown'}
              label={badgeLabel}
            />
            <span className="text-sm text-muted-foreground flex-1 min-w-0 truncate" title={detailText}>
              {detailText}
            </span>
          </div>
        )}

        <Separator />

        <label className="group flex items-center gap-2.5 cursor-pointer select-none">
          <span
            className={`relative flex size-4 shrink-0 items-center justify-center rounded border transition-all duration-150
              ${allowDirty
                ? 'bg-primary border-primary'
                : 'bg-background border-border group-hover:border-foreground/40'
              }`}
          >
            <input
              type="checkbox"
              checked={allowDirty}
              onChange={(e) => onAllowDirtyChange(e.target.checked)}
              className="sr-only"
            />
            {allowDirty && (
              <svg viewBox="0 0 10 8" className="size-2.5 text-primary-foreground fill-none stroke-current stroke-[1.5]">
                <path d="M1 4l3 3 5-6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
          </span>
          <span className="text-sm text-muted-foreground group-hover:text-foreground transition-colors duration-150">
            dirty 时确认后继续 update
          </span>
        </label>
      </CardContent>
    </Card>
  )
}
