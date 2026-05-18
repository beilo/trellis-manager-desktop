import { StatusBadge } from './StatusBadge'
import type { PlatformInfo, Status } from '@/types'

interface HeaderProps {
  platformInfo: PlatformInfo | null
  readyStatus: Status
}

export function Header({ platformInfo, readyStatus }: HeaderProps) {
  const platformLabel = platformInfo?.is_macos ? 'macOS' : '非 macOS'
  const platformStatus: Status = platformInfo?.is_macos ? 'ok' : 'error'
  const pythonLabel = platformInfo ? `Python ${platformInfo.python_version}` : 'Python 3'

  return (
    <div className="flex items-start justify-between gap-4 pb-4">
      <div className="flex flex-col gap-1.5">
        <h1 className="text-3xl font-extrabold tracking-tight text-foreground">
          团队 Trellis 工具链管理
        </h1>
        <p className="text-sm text-muted-foreground">
          检查、下载、构建、创建 tl / trellis，再把 Trellis 安装到业务项目。
        </p>
      </div>

      <div className="flex items-center gap-2 pt-1 shrink-0">
        <StatusBadge status={platformStatus} label={platformLabel} />
        <StatusBadge status="ok" label={pythonLabel} />
        <StatusBadge
          status={readyStatus}
          label={readyStatus === 'ok' ? '可用' : '待处理'}
        />
      </div>
    </div>
  )
}
