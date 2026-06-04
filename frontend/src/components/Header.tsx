import { StatusBadge } from './StatusBadge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { FolderGit2, LayoutDashboard, Settings, Wrench } from 'lucide-react'
import type { ActiveTab, PlatformInfo, Status } from '@/types'

interface HeaderProps {
  platformInfo: PlatformInfo | null
  readyStatus: Status
  activeTab: ActiveTab
  onTabChange: (tab: ActiveTab) => void
  onOpenSettings?: () => void
}

export function Header({ platformInfo, readyStatus, activeTab, onTabChange, onOpenSettings }: HeaderProps) {
  const platformLabel = platformInfo?.is_macos ? 'macOS' : '非 macOS'
  const platformStatus: Status = platformInfo?.is_macos ? 'ok' : 'error'
  const pythonLabel = platformInfo ? `Python ${platformInfo.python_version}` : 'Python 3'

  return (
    <div className="flex flex-col gap-4 pb-4 lg:flex-row lg:items-start lg:justify-between">
      <div className="flex flex-col gap-1.5">
        <h1 className="text-3xl font-serif font-normal tracking-tight text-foreground">
          团队 Trellis 工具链管理
        </h1>
        <p className="text-sm text-muted-foreground">
          检查、下载、构建、创建 tl / trellis，再把 Trellis 安装到业务项目。
        </p>
      </div>

      <div className="flex flex-wrap items-center justify-start gap-2 pt-1 lg:justify-end">
        <div className="relative flex w-[240px] h-9 items-center rounded-full bg-card/60 p-1 border border-border/60 select-none">
          {/* Slider Background */}
          <div
            className="absolute top-1 bottom-1 rounded-full bg-background transition-all duration-200 ease-out shadow-[0_1px_3px_rgba(20,20,19,0.06)]"
            style={{
              left: activeTab === 'kanban' ? '4px' : activeTab === 'toolchain' ? '82px' : '160px',
              width: '76px',
            }}
          />
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onTabChange('kanban')}
            className={cn(
              'relative z-10 w-[76px] h-7 rounded-full text-xs transition-colors duration-150',
              activeTab === 'kanban'
                ? 'text-primary font-semibold'
                : 'text-muted-foreground hover:text-foreground hover:bg-transparent dark:hover:bg-transparent',
            )}
          >
            <LayoutDashboard data-icon="inline-start" />
            看板
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onTabChange('toolchain')}
            className={cn(
              'relative z-10 w-[76px] h-7 rounded-full text-xs transition-colors duration-150',
              activeTab === 'toolchain'
                ? 'text-primary font-semibold'
                : 'text-muted-foreground hover:text-foreground hover:bg-transparent dark:hover:bg-transparent',
            )}
          >
            <Wrench data-icon="inline-start" />
            工具链
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onTabChange('projects')}
            className={cn(
              'relative z-10 w-[76px] h-7 rounded-full text-xs transition-colors duration-150',
              activeTab === 'projects'
                ? 'text-primary font-semibold'
                : 'text-muted-foreground hover:text-foreground hover:bg-transparent dark:hover:bg-transparent',
            )}
          >
            <FolderGit2 data-icon="inline-start" />
            项目
          </Button>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {onOpenSettings && (
            <Button variant="ghost" size="icon-sm" className="rounded-full text-muted-foreground hover:text-foreground" onClick={onOpenSettings} title="工具链设置">
              <Settings className="size-3.5" />
            </Button>
          )}
          <StatusBadge status={platformStatus} label={platformLabel} />
          <StatusBadge status="ok" label={pythonLabel} />
          <StatusBadge
            status={readyStatus}
            label={readyStatus === 'ok' ? '可用' : '待处理'}
          />
        </div>
      </div>
    </div>
  )
}
