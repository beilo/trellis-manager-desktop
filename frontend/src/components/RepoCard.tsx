import { useState } from 'react'
import { CloudDownload, ExternalLink, FileArchive, Loader2 } from 'lucide-react'
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
  onInstallFromZip: (zipPath: string, replace: boolean) => void
  onInstallFromRemoteZip: (replace: boolean) => void
  onCreateWrappers: () => void
  onPathChange: (path: string) => void
  githubBranchUrl: string | null
  githubBranchZipUrl: string | null
}

export function RepoCard({
  repoPath,
  status,
  loading,
  busy,
  onCheck,
  onInstall,
  onInstallFromZip,
  onInstallFromRemoteZip,
  onCreateWrappers,
  onPathChange,
  githubBranchUrl,
  githubBranchZipUrl,
}: RepoCardProps) {
  const [zipPath, setZipPath] = useState('')
  const [zipBusy, setZipBusy] = useState(false)
  const [remoteZipBusy, setRemoteZipBusy] = useState(false)

  const repoStatus = status?.status ?? 'unknown'
  const sourceType = status?.source_type

  let stepStatus: StepStatus = 'idle'
  if (busy || loading || zipBusy || remoteZipBusy) {
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

  const isZipSnapshot = sourceType === 'zip_snapshot'
  const needsReinstall = status?.exists && !status?.is_git

  const handleZipInstall = async () => {
    if (!zipPath.trim()) return
    const replace = status?.exists === true
    if (replace && !window.confirm('工具仓库已存在，确认用选中的 zip 替换当前源码？')) {
      return
    }
    setZipBusy(true)
    try {
      await onInstallFromZip(zipPath.trim(), replace)
    } finally {
      setZipBusy(false)
    }
  }

  const handleRemoteZipInstall = async () => {
    const replace = status?.exists === true
    if (replace && !window.confirm('工具仓库已存在，确认用远端 zip 替换当前源码？')) {
      return
    }
    setRemoteZipBusy(true)
    try {
      await onInstallFromRemoteZip(replace)
    } finally {
      setRemoteZipBusy(false)
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
        <div className="flex items-center gap-2 shrink-0 flex-wrap justify-end">
          <Button variant="outline" size="sm" onClick={onCheck} disabled={loading || busy || zipBusy || remoteZipBusy}>
            {loading && <Loader2 className="size-3 animate-spin" data-icon="inline-start" />}
            {loading ? '检查中…' : '检查仓库'}
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={onInstall}
            disabled={busy || zipBusy || remoteZipBusy || isZipSnapshot}
            title={isZipSnapshot ? '当前为 zip 快照安装，请使用下方 zip 重装更新' : undefined}
          >
            {busy && <Loader2 className="size-3 animate-spin" data-icon="inline-start" />}
            {busy ? '处理中…' : '下载 / 更新并构建'}
          </Button>
          <Button variant="outline" size="sm" onClick={onCreateWrappers} disabled={busy || zipBusy || remoteZipBusy}>
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

        {/* GitHub 分支链接 */}
        {githubBranchUrl && (
          <div className="flex items-center gap-2">
            <a
              href={githubBranchUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
            >
              <ExternalLink className="size-3" />
              打开分发分支
            </a>
            <span className="text-xs text-muted-foreground">
              → 下载 zip 后通过下方选择本地安装
            </span>
          </div>
        )}

        {/* 远端 zip 安装区域 */}
        <div className="flex flex-col gap-2 border rounded-lg p-3 bg-accent/40">
          <div className="flex items-center gap-2">
            <CloudDownload className="size-4 text-muted-foreground" />
            <span className="text-xs font-medium text-muted-foreground">远端源码 zip 安装</span>
          </div>
          {githubBranchZipUrl ? (
            <>
              <p className="text-xs text-muted-foreground">
                从当前分发分支下载源码 zip 并安装，适合 Git clone/pull 不稳定时使用。
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleRemoteZipInstall}
                  disabled={remoteZipBusy || zipBusy || busy}
                >
                  {remoteZipBusy && <Loader2 className="size-3 animate-spin" data-icon="inline-start" />}
                  {remoteZipBusy
                    ? '下载并安装中…'
                    : needsReinstall
                      ? '下载 zip 并重装'
                      : '下载 zip 并安装'}
                </Button>
              </div>
            </>
          ) : (
            <p className="text-xs text-muted-foreground">
              当前官方仓库 URL 不是 GitHub 仓库，无法使用远端 zip 安装。
            </p>
          )}
        </div>

        {/* 本地 zip 安装区域 */}
        <div className="flex flex-col gap-2 border rounded-lg p-3 bg-accent/40">
          <div className="flex items-center gap-2">
            <FileArchive className="size-4 text-muted-foreground" />
            <span className="text-xs font-medium text-muted-foreground">本地源码 zip 安装</span>
          </div>
          <div className="flex items-center gap-2">
            <AppInput
              value={zipPath}
              onChange={(e) => setZipPath(e.target.value)}
              placeholder="输入 zip 文件路径或点击选择…"
              className="flex-1"
            />
            <Button
              variant="secondary"
              size="sm"
              onClick={handleZipInstall}
              disabled={!zipPath.trim() || zipBusy || busy || remoteZipBusy}
            >
              {zipBusy && <Loader2 className="size-3 animate-spin" data-icon="inline-start" />}
              {zipBusy ? '安装中…' : needsReinstall ? '重装' : '安装'}
            </Button>
          </div>
          {isZipSnapshot && (
            <p className="text-xs text-muted-foreground">
              当前为本地源码快照，不能在线 pull；如需更新请选择新的 zip 并点击重装。
            </p>
          )}
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
