import { FolderGit2, Plus, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import { StatusBadge } from './StatusBadge'
import type { ProjectStatus } from '@/types'

interface ProjectListProps {
  projects: string[]
  selectedProject: string | null
  statuses: Record<string, ProjectStatus>
  busy: boolean
  onAdd: () => void
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
  onAdd,
  onSelect,
  onRemove,
}: ProjectListProps) {
  return (
    <aside className="rounded-xl border bg-card text-card-foreground overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b px-4 py-3">
        <div className="flex flex-col gap-0.5 min-w-0">
          <span className="text-sm font-bold text-foreground">项目列表</span>
          <span className="text-xs text-muted-foreground">{projects.length} 个本地项目</span>
        </div>
        <Button variant="outline" size="sm" onClick={onAdd} disabled={busy}>
          <Plus data-icon="inline-start" />
          添加
        </Button>
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
              const status = statuses[path]?.status ?? 'unknown'
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
                    'transition-all duration-150 hover:bg-muted',
                    selected
                      ? 'bg-blue-100 dark:bg-blue-900/40 border-2 border-blue-500 shadow-sm'
                      : 'border-2 border-transparent hover:border-border',
                  )}
                >
                  <StatusBadge status={status} className="px-2" />
                  <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <span className="truncate text-sm font-semibold text-foreground">
                      {projectName(path)}
                    </span>
                    <span className="truncate text-xs text-muted-foreground" title={path}>
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
