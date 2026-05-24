import { useCallback, useEffect, useState } from 'react'
import { GitBranch, Loader2, RefreshCw } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { api } from '@/api'
import type { GitSummary, ProjectStatus } from '@/types'

interface ProjectGitPanelProps {
  projectPath: string | null
  projectStatus: ProjectStatus | null
}

export function ProjectGitPanel({ projectPath, projectStatus }: ProjectGitPanelProps) {
  const [summary, setSummary] = useState<GitSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3 pb-3">
        <div className="flex min-w-0 items-center gap-2">
          <GitBranch className="size-4 text-emerald-500" />
          <div className="flex min-w-0 flex-col">
            <span className="text-sm font-semibold text-foreground">Git 快捷面板</span>
            <span className="text-xs text-muted-foreground">只读，不替代 git 客户端。</span>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={loadSummary} disabled={loading}>
          {loading ? <Loader2 className="size-3 animate-spin" data-icon="inline-start" /> : <RefreshCw className="size-3" data-icon="inline-start" />}
          刷新
        </Button>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 pt-0">
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
              <div className="rounded-lg border bg-muted/20 p-3">
                <div className="text-xs text-muted-foreground">分支</div>
                <div className="mt-1 font-mono text-sm">{summary.branch ?? '-'}</div>
              </div>
              <div className="rounded-lg border bg-muted/20 p-3">
                <div className="text-xs text-muted-foreground">Dirty</div>
                <div className="mt-1 text-sm">{summary.dirty ? `${summary.dirty_files.length} 个文件` : '干净'}</div>
              </div>
              <div className="rounded-lg border bg-muted/20 p-3">
                <div className="text-xs text-muted-foreground">Ahead</div>
                <div className="mt-1 text-sm">{summary.ahead ?? '无 upstream'}</div>
              </div>
              <div className="rounded-lg border bg-muted/20 p-3">
                <div className="text-xs text-muted-foreground">Behind</div>
                <div className="mt-1 text-sm">{summary.behind ?? '无 upstream'}</div>
              </div>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-lg border">
                <div className="border-b px-3 py-2 text-sm font-medium">Dirty 文件</div>
                <ScrollArea className="max-h-36">
                  {summary.dirty_files.length > 0 ? (
                    <ul className="space-y-1 p-3 font-mono text-xs text-muted-foreground">
                      {summary.dirty_files.map((file) => <li key={file}>{file}</li>)}
                    </ul>
                  ) : (
                    <div className="px-3 py-4 text-sm text-muted-foreground">无 dirty 文件。</div>
                  )}
                </ScrollArea>
              </div>
              <div className="rounded-lg border">
                <div className="border-b px-3 py-2 text-sm font-medium">最近提交</div>
                <ScrollArea className="max-h-36">
                  {summary.recent_commits.length > 0 ? (
                    <div className="flex flex-col gap-2 p-3">
                      {summary.recent_commits.map((commit) => (
                        <div key={commit.short_hash} className="flex items-start gap-2 text-xs">
                          <Badge variant="secondary" className="font-mono">{commit.short_hash}</Badge>
                          <span className="min-w-0 flex-1 truncate" title={commit.title}>{commit.title}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="px-3 py-4 text-sm text-muted-foreground">暂无提交记录。</div>
                  )}
                </ScrollArea>
              </div>
            </div>
          </>
        ) : null}
      </CardContent>
    </Card>
  )
}
