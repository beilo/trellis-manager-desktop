import { useCallback, useEffect, useMemo, useState } from 'react'
import { Loader2, RefreshCw, Rows3 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { api } from '@/api'
import type { BatchUpdateReport, ProjectStatus } from '@/types'

interface BatchUpdateCardProps {
  onCompleted?: () => void
}

function projectName(path: string): string {
  const normalized = path.replace(/[\\/]+$/, '')
  return normalized.split(/[\\/]/).pop() || normalized
}

export function BatchUpdateCard({ onCompleted }: BatchUpdateCardProps) {
  const [projects, setProjects] = useState<ProjectStatus[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [allowDirty, setAllowDirty] = useState(false)
  const [loading, setLoading] = useState(false)
  const [running, setRunning] = useState(false)
  const [report, setReport] = useState<BatchUpdateReport | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.listOutdatedProjects()
      setProjects(result)
      // dirty 项目默认不选中，除非用户显式允许 dirty。
      setSelected(new Set(result.filter((project) => !project.dirty && project.path).map((project) => project.path as string)))
    } catch (err) {
      setError(`批量 Update 列表加载失败：${err}`)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void Promise.resolve().then(load)
  }, [load])

  const selectableProjects = useMemo(() => {
    return projects.filter((project) => Boolean(project.path) && (allowDirty || !project.dirty))
  }, [allowDirty, projects])

  const run = async () => {
    setRunning(true)
    setError(null)
    setReport(null)
    try {
      const paths = Array.from(selected)
      const result = await api.batchUpdateProjects(paths, allowDirty)
      setReport(result)
      onCompleted?.()
      await load()
    } catch (err) {
      setError(`批量 Update 执行失败：${err}`)
    } finally {
      setRunning(false)
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-4 pb-3">
        <div className="flex items-center gap-3">
          <Rows3 className="size-4 text-cyan-500" />
          <div className="flex flex-col gap-0.5">
            <span className="text-base font-bold text-foreground">批量 Update</span>
            <span className="text-xs text-muted-foreground">只处理版本过期项目，单项失败不阻断后续结果。</span>
          </div>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={load} disabled={loading || running}>
          {loading ? <Loader2 className="size-3 animate-spin" data-icon="inline-start" /> : <RefreshCw className="size-3" data-icon="inline-start" />}
          刷新
        </Button>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 pt-0">
        <label className="flex cursor-pointer select-none items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={allowDirty}
            onChange={(event) => {
              const nextAllowDirty = event.target.checked
              setAllowDirty(nextAllowDirty)
              setSelected(new Set(projects.filter((project) => (nextAllowDirty || !project.dirty) && project.path).map((project) => project.path as string)))
            }}
            className="size-4 accent-primary"
          />
          允许 dirty 项目参与批量更新
        </label>

        <ScrollArea className="max-h-64 rounded-lg border">
          {projects.length === 0 ? (
            <div className="px-3 py-8 text-center text-sm text-muted-foreground">
              {loading ? '正在加载过期项目…' : '暂无版本过期项目。'}
            </div>
          ) : (
            <div className="divide-y">
              {projects.map((project) => {
                const path = project.path ?? ''
                const disabled = project.dirty && !allowDirty
                const checked = selected.has(path)
                return (
                  <label key={path} className="flex cursor-pointer items-start gap-3 px-3 py-2 text-sm hover:bg-muted/35">
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={disabled}
                      onChange={(event) => {
                        setSelected((current) => {
                          const next = new Set(current)
                          if (event.target.checked) next.add(path)
                          else next.delete(path)
                          return next
                        })
                      }}
                      className="mt-1 size-4 accent-primary"
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium text-foreground">{projectName(path)}</span>
                        {project.dirty && <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[11px] text-amber-700">dirty</span>}
                      </div>
                      <div className="truncate text-xs text-muted-foreground" title={path}>{path}</div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {project.trellis_version ?? '-'} → {project.latest_version ?? '-'}
                      </div>
                    </div>
                  </label>
                )
              })}
            </div>
          )}
        </ScrollArea>

        {error && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}

        {report && (
          <div className="rounded-lg border bg-muted/20 p-3 text-sm">
            <div className="font-medium text-foreground">{report.message}</div>
            <div className="mt-1 text-xs text-muted-foreground">
              成功 {report.updated_count}，失败 {report.failed_count}，跳过 {report.skipped_count}
            </div>
            <div className="mt-3 flex max-h-40 flex-col gap-1 overflow-auto text-xs">
              {report.results.map((result) => (
                <div key={result.path} className={result.ok ? 'text-emerald-700 dark:text-emerald-300' : 'text-destructive'}>
                  {projectName(result.path)}：{result.message}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex items-center justify-between gap-3">
          <span className="text-xs text-muted-foreground">
            已选 {selected.size} / 可选 {selectableProjects.length}
          </span>
          <Button type="button" onClick={() => void run()} disabled={running || selected.size === 0}>
            {running && <Loader2 className="size-3 animate-spin" data-icon="inline-start" />}
            开始批量 Update
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
