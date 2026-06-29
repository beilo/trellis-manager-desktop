import { useState } from 'react'
import { CloudDownload, ExternalLink, FileArchive, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { AppInput } from './AppInput'
import { StatusBadge } from './StatusBadge'
import { StepBadge, type StepStatus } from './StepBadge'
import type { EmbeddedZipInfo } from '@/api'
import type { RepoStatus } from '@/types'

interface RepoCardProps {
  repoPath: string
  status: RepoStatus | null
  loading: boolean
  busy: boolean
  onCheck: () => void
  onInstall: () => void
  onInstallFromZip: (zipPath: string, replace: boolean) => void
  onInstallFromEmbeddedZip: (replace: boolean) => void
  onInstallFromRemoteZip: (replace: boolean) => void
  onCreateWrappers: () => void
  onPathChange: (path: string) => void
  githubBranchUrl: string | null
  githubBranchZipUrl: string | null
  embeddedZipInfo: EmbeddedZipInfo | null
}

export function RepoCard({
  repoPath,
  status,
  loading,
  busy,
  onCheck,
  onInstall,
  onInstallFromZip,
  onInstallFromEmbeddedZip,
  onInstallFromRemoteZip,
  onCreateWrappers,
  onPathChange,
  githubBranchUrl,
  githubBranchZipUrl,
  embeddedZipInfo,
}: RepoCardProps) {
  const [zipPath, setZipPath] = useState('')
  const [embeddedZipBusy, setEmbeddedZipBusy] = useState(false)
  const [zipBusy, setZipBusy] = useState(false)
  const [remoteZipBusy, setRemoteZipBusy] = useState(false)

  const repoStatus = status?.status ?? 'unknown'
  const sourceType = status?.source_type

  let stepStatus: StepStatus = 'idle'
  if (busy || loading || embeddedZipBusy || zipBusy || remoteZipBusy) {
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
    || sourceType === 'embedded_zip_snapshot'
    || sourceType === 'local_zip_snapshot'
    || sourceType === 'remote_zip_snapshot'
  const needsReinstall = status?.exists && !status?.is_git
  // 检查仓库期间也禁用安装入口，避免状态刷新和安装写操作并发导致按钮判断失真。
  const anyInstallBusy = loading || busy || embeddedZipBusy || zipBusy || remoteZipBusy
  const embeddedZipAvailable = embeddedZipInfo?.exists === true

  const handleEmbeddedZipInstall = async () => {
    const replace = status?.exists === true
    if (replace && !window.confirm('工具仓库已存在，确认用内置 zip 替换当前源码？')) {
      return
    }
    setEmbeddedZipBusy(true)
    try {
      await onInstallFromEmbeddedZip(replace)
    } finally {
      setEmbeddedZipBusy(false)
    }
  }

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
          <Button variant="outline" size="sm" onClick={onCheck} disabled={loading || anyInstallBusy}>
            {loading && <Loader2 className="size-3 animate-spin" data-icon="inline-start" />}
            {loading ? '检查中…' : '检查仓库'}
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={onInstall}
            disabled={anyInstallBusy || isZipSnapshot}
            title={isZipSnapshot ? '当前为 zip 快照安装，请使用下方 zip 重装更新' : undefined}
          >
            {busy && <Loader2 className="size-3 animate-spin" data-icon="inline-start" />}
            {busy ? '处理中…' : '下载 / 更新并构建'}
          </Button>
          <Button variant="outline" size="sm" onClick={onCreateWrappers} disabled={anyInstallBusy}>
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

        {/* 内置 zip 安装区域：弱网时优先走随应用发布的源码快照，避免依赖 GitHub/codeload。 */}
        <div className="flex flex-col gap-2 border rounded-lg p-3 bg-accent/40">
          <div className="flex items-center gap-2">
            <FileArchive className="size-4 text-primary" />
            <span className="text-xs font-semibold text-foreground">推荐：内置源码 zip 安装</span>
          </div>
          <p className="text-xs text-muted-foreground">
            弱网首选。内置包只包含 Trellis 源码，不含依赖和构建产物；安装时会在本机继续执行依赖安装并构建。
          </p>
          <div className="flex items-center gap-2 flex-wrap">
            <Button
              variant="secondary"
              size="sm"
              onClick={handleEmbeddedZipInstall}
              disabled={!embeddedZipAvailable || anyInstallBusy}
              title={embeddedZipAvailable ? undefined : '当前应用未打入内置源码 zip，请重新打包或使用本地/远端 zip。'}
            >
              {embeddedZipBusy && <Loader2 className="size-3 animate-spin" data-icon="inline-start" />}
              {embeddedZipBusy ? '内置安装中…' : needsReinstall ? '使用内置 zip 重装' : '使用内置 zip 安装'}
            </Button>
            {!embeddedZipAvailable && (
              <span className="text-xs text-muted-foreground">内置 zip 不可用，可改用本地或远端 zip。</span>
            )}
          </div>
        </div>

        {/* 本地 zip 安装区域 */}
        <div className="flex flex-col gap-2 border rounded-lg p-3 bg-accent/40">
          <div className="flex items-center gap-2">
            <FileArchive className="size-4 text-muted-foreground" />
            <span className="text-xs font-medium text-muted-foreground">本地源码 zip 安装</span>
          </div>
          <p className="text-xs text-muted-foreground">
            适合手动下载 zip 或使用自定义源码包；同样会在本机安装依赖并构建。
          </p>
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
              disabled={!zipPath.trim() || anyInstallBusy}
            >
              {zipBusy && <Loader2 className="size-3 animate-spin" data-icon="inline-start" />}
              {zipBusy ? '安装中…' : needsReinstall ? '重装' : '安装'}
            </Button>
          </div>
          {isZipSnapshot && (
            <p className="text-xs text-muted-foreground">
              当前为源码 zip 快照，不能在线 pull；如需更新请选择新的 zip 或使用内置/远端 zip 重装。
            </p>
          )}
        </div>

        {/* 远端 zip 安装区域 */}
        <div className="flex flex-col gap-2 border rounded-lg p-3 bg-accent/40">
          <div className="flex items-center gap-2">
            <CloudDownload className="size-4 text-muted-foreground" />
            <span className="text-xs font-medium text-muted-foreground">备用：远端源码 zip 安装</span>
          </div>
          {githubBranchZipUrl ? (
            <>
              <p className="text-xs text-muted-foreground">
                需要联网，从当前分发分支下载最新源码 zip；适合作为在线备用入口。
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleRemoteZipInstall}
                  disabled={anyInstallBusy}
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
              → 浏览器手动下载 zip 后也可通过本地安装入口使用
            </span>
          </div>
        )}

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
