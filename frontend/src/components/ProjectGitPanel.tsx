import { useCallback, useEffect, useState } from 'react'
import { ChevronDown, GitBranch, Loader2, RefreshCw } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { api } from '@/api'
import { cn } from '@/lib/utils'
import type { GitSummary, ProjectStatus } from '@/types'

interface ProjectGitPanelProps {
  projectPath: string | null
  projectStatus: ProjectStatus | null
}

export function ProjectGitPanel({ projectPath, projectStatus }: ProjectGitPanelProps) {
  const [summary, setSummary] = useState<GitSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState(true)

  const loadSummary = useCallback(async () => {
    if (!projectPath || !projectStatus?.is_git) return
    setLoading(true)
    setSummary(null)
    setError(null)
    try {
      const result = await api.getProjectGitSummary(projectPath)
      setSummary(result)
    } catch (err) {
      setError(`Git 摘要加载失败：${err}`)
    } finally {
      setLoading(false)
    }
  }, [projectPath, projectStatus?.is_git])

  useEffect(() => {
    void Promise.resolve().then(loadSummary)
  }, [loadSummary])

  if (!projectPath || !projectStatus?.is_git) return null

  return (
    <Card className="premium-card">
      <CardHeader className="flex flex-row items-center justify-between gap-3 pb-3">
        <button
          type="button"
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
          aria-expanded={expanded}
          aria-controls="project-git-panel-content"
          onClick={() => setExpanded((value) => !value)}
        >
          {/* Git 面板默认可折叠，避免项目页右侧内容继续变长。 */}
          <ChevronDown
            className={cn(
              'size-4 shrink-0 text-muted-foreground transition-transform',
              expanded ? 'rotate-0' : '-rotate-90',
            )}
          />
          <GitBranch className="size-4 text-emerald-500" />
          <div className="flex min-w-0 flex-col">
            <span className="text-sm font-semibold text-foreground">Git 快捷面板</span>
            <span className="text-xs text-muted-foreground">只读，不替代 git 客户端。</span>
          </div>
        </button>
        <Button variant="outline" size="sm" onClick={loadSummary} disabled={loading}>
          {loading ? <Loader2 className="size-3 animate-spin" data-icon="inline-start" /> : <RefreshCw className="size-3" data-icon="inline-start" />}
          刷新
        </Button>
      </CardHeader>
      {expanded && (
        <CardContent id="project-git-panel-content" className="flex flex-col gap-3 pt-0">
          {error && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </div>
          )}
          {!summary && !error ? (
            <div className="text-sm text-muted-foreground">{loading ? '正在加载 Git 摘要…' : '暂无 Git 摘要'}</div>
          ) : summary ? (
            <>
              <div className="grid gap-2 md:grid-cols-4">
                <div className="rounded-xl border border-border/30 bg-muted/30 p-3 select-none">
                  <div className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">分支</div>
                  <div className="mt-1 font-mono text-sm text-foreground truncate" title={summary.branch ?? undefined}>{summary.branch ?? '-'}</div>
                </div>
                <div className="rounded-xl border border-border/30 bg-muted/30 p-3 flex items-start justify-between select-none">
                  <div className="min-w-0 flex-1">
                    <div className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">Dirty</div>
                    <div className="mt-1 text-sm font-bold text-foreground truncate">{summary.dirty ? `${summary.dirty_files.length} 个文件` : '干净'}</div>
                  </div>
                  <span className={cn(
                    "size-2 rounded-full mt-1.5 shrink-0 transition-all duration-300",
                    summary.dirty
                      ? "bg-orange-500 shadow-[0_0_8px_rgba(249,115,22,0.6)] animate-pulse"
                      : "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]"
                  )} />
                </div>
                <div className="rounded-xl border border-border/30 bg-muted/30 p-3 select-none">
                  <div className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">Ahead</div>
                  <div className="mt-1 text-sm font-bold text-foreground">{summary.ahead ?? '0'}</div>
                </div>
                <div className="rounded-xl border border-border/30 bg-muted/30 p-3 select-none">
                  <div className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">Behind</div>
                  <div className="mt-1 text-sm font-bold text-foreground">{summary.behind ?? '0'}</div>
                </div>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-xl border border-border/30 overflow-hidden bg-background/35 shadow-sm">
                  <div className="border-b border-border/30 px-3 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground bg-muted/20">Dirty 文件</div>
                  <ScrollArea className="max-h-36">
                    {summary.dirty_files.length > 0 ? (
                      <ul className="space-y-1 p-3 font-mono text-xs text-muted-foreground">
                        {summary.dirty_files.map((file) => <li key={file}>{file}</li>)}
                      </ul>
                    ) : (
                      <div className="px-3 py-4 text-xs text-muted-foreground italic">无 dirty 文件。</div>
                    )}
                  </ScrollArea>
                </div>
                <div className="rounded-xl border border-border/30 overflow-hidden bg-background/35 shadow-sm">
                  <div className="border-b border-border/30 px-3 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground bg-muted/20">最近提交</div>
                  <ScrollArea className="max-h-36">
                    {summary.recent_commits.length > 0 ? (
                      <div className="flex flex-col gap-2 p-3">
                        {summary.recent_commits.map((commit) => (
                          <div key={commit.short_hash} className="flex items-start gap-2 text-xs">
                            <Badge variant="secondary" className="font-mono scale-90 -ml-1 text-[10px]">{commit.short_hash}</Badge>
                            <span className="min-w-0 flex-1 truncate text-xs text-foreground/90" title={commit.oneline}>{commit.title}</span>
                            <span className="shrink-0 font-mono text-[10px] text-muted-foreground">{commit.date ?? '日期未知'}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="px-3 py-4 text-xs text-muted-foreground italic">暂无提交记录。</div>
                    )}
                  </ScrollArea>
                </div>
              </div>
            </>
          ) : null}
        </CardContent>
      )}
    </Card>
  )
}
