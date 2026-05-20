import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { AppInput } from './AppInput'
import { StatusBadge } from './StatusBadge'
import { StepBadge, type StepStatus } from './StepBadge'
import type { RepoStatus } from '@/types'

interface RepoCardProps {
  repoPath: string
  status: RepoStatus | null
  loading: boolean
  busy: boolean
  onCheck: () => void
  onInstall: () => void
  onCreateWrappers: () => void
  onPathChange: (path: string) => void
}

export function RepoCard({
  repoPath,
  status,
  loading,
  busy,
  onCheck,
  onInstall,
  onCreateWrappers,
  onPathChange,
}: RepoCardProps) {
  const repoStatus = status?.status ?? 'unknown'

  let stepStatus: StepStatus = 'idle'
  if (busy || loading) {
    stepStatus = 'loading'
  } else if (status) {
    if (status.status === 'ok') stepStatus = 'ok'
    else if (status.status === 'warning') stepStatus = 'warning'
    else if (status.status === 'error') stepStatus = 'error'
  }

  let detailText = '未检查'
  if (status) {
    if (!status.exists) {
      detailText = '需要先下载 / 更新并构建'
    } else {
      const parts: string[] = []
      if (status.branch) parts.push(`分支 ${status.branch}`)
      if (status.version) parts.push(`版本：${status.version}`)
      if (status.ahead != null && status.behind != null) {
        parts.push(`ahead ${status.ahead} / behind ${status.behind}`)
      }
      const detail = parts.join(' ｜ ')
      detailText = status.message + (detail ? `  ${detail}` : '')
    }
  }

  return (
    <Card className="premium-card">
      <CardHeader className="flex flex-row items-start justify-between gap-4 pb-3">
        <div className="flex items-center gap-3">
          <StepBadge step={2} status={stepStatus} />
          <div className="flex flex-col gap-0.5">
            <span className="text-base font-bold text-foreground select-none">Trellis 工具仓库</span>
            <span className="text-xs text-muted-foreground select-none">下载更新工具源并完成编译。</span>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Button variant="outline" size="sm" onClick={onCheck} disabled={loading || busy}>
            {loading && <Loader2 className="size-3 animate-spin" data-icon="inline-start" />}
            {loading ? '检查中…' : '检查仓库'}
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={onInstall}
            disabled={busy}
          >
            {busy && <Loader2 className="size-3 animate-spin" data-icon="inline-start" />}
            {busy ? '处理中…' : '下载 / 更新并构建'}
          </Button>
          <Button variant="outline" size="sm" onClick={onCreateWrappers} disabled={busy}>
            创建命令入口
          </Button>
        </div>
      </CardHeader>

      <CardContent className="flex flex-col gap-4 pt-0">
        <div className="flex flex-col gap-1.5">
          <span className="text-xs text-muted-foreground font-medium">安装路径</span>
          <AppInput
            value={repoPath}
            onChange={(e) => onPathChange(e.target.value)}
          />
        </div>

        <div className="flex items-center gap-3">
          <StatusBadge status={repoStatus} label={loading ? '检查中…' : undefined} />
          <span className="text-sm text-muted-foreground flex-1" title={detailText}>
            {detailText}
          </span>
        </div>
      </CardContent>
    </Card>
  )
}
