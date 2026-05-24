import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, Loader2, RefreshCw, Rows3, XCircle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { api } from '@/api'
import type { BatchUpdateReport, ProjectStatus, ProjectUpdateResult } from '@/types'

interface BatchUpdateDialogProps {
  open: boolean
  projects: ProjectStatus[]
  loading: boolean
  onClose: () => void
  onRefresh: () => Promise<void>
  onCompleted: () => Promise<void> | void
  onOpenLog: () => void
}

function projectName(path: string): string {
  const normalized = path.replace(/[\\/]+$/, '')
  return normalized.split(/[\\/]/).pop() || normalized
}

function statusBadge(result: ProjectUpdateResult) {
  if (result.skipped) {
    return { label: '跳过', className: 'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300' }
  }
  if (result.ok) {
    return { label: '成功', className: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300' }
  }
  return { label: '失败', className: 'border-destructive/30 bg-destructive/10 text-destructive' }
}

export function BatchUpdateDialog({
  open,
  projects,
  loading,
  onClose,
  onRefresh,
  onCompleted,
  onOpenLog,
}: BatchUpdateDialogProps) {
  const rows = useMemo(() => projects.filter((project) => Boolean(project.path)), [projects])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [allowDirty, setAllowDirty] = useState(false)
  const [running, setRunning] = useState(false)
  const [report, setReport] = useState<BatchUpdateReport | null>(null)
  const [error, setError] = useState<string | null>(null)

  const rowPaths = useMemo(() => rows.map((project) => project.path as string), [rows])
  const selectedPaths = useMemo(() => rowPaths.filter((path) => selected.has(path)), [rowPaths, selected])
  const allSelected = rowPaths.length > 0 && selectedPaths.length === rowPaths.length

  useEffect(() => {
    if (!open) return
    let cancelled = false
    void Promise.resolve().then(() => {
      if (cancelled) return
      setReport(null)
      setError(null)
      setAllowDirty(false)
      void onRefresh()
    })
    return () => {
      cancelled = true
    }
  }, [open, onRefresh])

  useEffect(() => {
    if (!open) return
    let cancelled = false
    void Promise.resolve().then(() => {
      if (cancelled) return
      // 对话框每次打开或刷新后默认全选，dirty 项目是否真实执行交给 allowDirty 控制。
      setSelected(new Set(rowPaths))
    })
    return () => {
      cancelled = true
    }
  }, [open, rowPaths])

  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !running) onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, running, onClose])

  if (!open) return null

  const toggleAll = () => {
    setSelected(allSelected ? new Set() : new Set(rowPaths))
  }

  const run = async () => {
    setRunning(true)
    setReport(null)
    setError(null)
    try {
      const result = await api.batchUpdateProjects(selectedPaths, allowDirty)
      setReport(result)
      await onCompleted()
      onOpenLog()
    } catch (err) {
      setError(`批量 Update 执行失败：${err}`)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-6 backdrop-blur-sm">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="batch-update-title"
        className="flex max-h-[88vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border bg-card shadow-2xl"
      >
        <header className="flex items-start justify-between gap-4 border-b px-5 py-4">
          <div className="min-w-0 space-y-1">
            <div className="flex items-center gap-2">
              <Rows3 className="size-4 text-cyan-500" />
              <h3 id="batch-update-title" className="text-base font-bold text-foreground">
                批量 Update 过期项目
              </h3>
              <Badge variant="secondary">{rows.length} 个待更新</Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              单项失败不会阻断后续项目；dirty 项目默认在后端跳过。
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose} disabled={running}>
            关闭
          </Button>
        </header>

        <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-auto px-5 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-3">
              <label className="flex cursor-pointer select-none items-center gap-2 text-sm text-muted-foreground">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={toggleAll}
                  className="size-4 accent-primary"
                  disabled={running || rows.length === 0}
                />
                全选过期项目
              </label>
              <label className="flex cursor-pointer select-none items-center gap-2 text-sm text-muted-foreground">
                <input
                  type="checkbox"
                  checked={allowDirty}
                  onChange={(event) => setAllowDirty(event.target.checked)}
                  className="size-4 accent-primary"
                  disabled={running}
                />
                允许 dirty 项目更新
              </label>
            </div>
            <Button variant="outline" size="sm" onClick={() => void onRefresh()} disabled={loading || running}>
              {loading ? <Loader2 className="size-3 animate-spin" data-icon="inline-start" /> : <RefreshCw className="size-3" data-icon="inline-start" />}
              刷新列表
            </Button>
          </div>

          <ScrollArea className="max-h-72 rounded-xl border">
            {rows.length === 0 ? (
              <div className="px-4 py-10 text-center text-sm text-muted-foreground">
                {loading ? '正在加载过期项目…' : '暂无版本过期项目。'}
              </div>
            ) : (
              <div className="divide-y">
                {rows.map((project) => {
                  const path = project.path as string
                  const checked = selected.has(path)
                  return (
                    <label key={path} className="flex cursor-pointer items-start gap-3 px-4 py-3 text-sm hover:bg-muted/35">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(event) => {
                          setSelected((current) => {
                            const next = new Set(current)
                            if (event.target.checked) next.add(path)
                            else next.delete(path)
                            return next
                          })
                        }}
                        className="mt-1 size-4 accent-primary"
                        disabled={running}
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium text-foreground">{projectName(path)}</span>
                          <span className="font-mono text-xs text-muted-foreground">
                            {project.trellis_version ?? '-'} → {project.latest_version ?? '-'}
                          </span>
                          {project.dirty && (
                            <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[11px] text-amber-700 dark:text-amber-300">
                              {allowDirty ? 'dirty 允许更新' : 'dirty 默认跳过'}
                            </span>
                          )}
                        </div>
                        <div className="mt-1 truncate text-xs text-muted-foreground" title={path}>
                          {path}
                        </div>
                      </div>
                    </label>
                  )
                })}
              </div>
            )}
          </ScrollArea>

          {error && (
            <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </div>
          )}

          {running && (
            <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 text-sm text-cyan-700 dark:text-cyan-300">
              <div className="flex items-center gap-2">
                <Loader2 className="size-4 animate-spin" />
                <span>
                  正在执行批量 Update：0/{selectedPaths.length} 完成，等待后端返回逐项目结果。
                </span>
              </div>
            </div>
          )}

          {report && (
            <div className="rounded-xl border">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b px-3 py-2">
                <div className="font-medium text-foreground">{report.message}</div>
                <div className="text-xs text-muted-foreground">
                  成功 {report.updated_count}，失败 {report.failed_count}，跳过 {report.skipped_count}
                </div>
              </div>
              <ScrollArea className="max-h-64">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>结果</TableHead>
                      <TableHead>项目</TableHead>
                      <TableHead>消息</TableHead>
                      <TableHead className="text-right">日志</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {report.results.map((result) => {
                      const badge = statusBadge(result)
                      const icon = result.skipped ? (
                        <AlertTriangle className="size-3" />
                      ) : result.ok ? (
                        <CheckCircle2 className="size-3" />
                      ) : (
                        <XCircle className="size-3" />
                      )
                      return (
                        <TableRow key={result.path}>
                          <TableCell>
                            <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs ${badge.className}`}>
                              {icon}
                              {badge.label}
                            </span>
                          </TableCell>
                          <TableCell>
                            <div className="min-w-0">
                              <div className="font-medium text-foreground">{projectName(result.path)}</div>
                              <div className="max-w-[18rem] truncate font-mono text-xs text-muted-foreground" title={result.path}>
                                {result.path}
                              </div>
                            </div>
                          </TableCell>
                          <TableCell className="max-w-[24rem] whitespace-normal text-muted-foreground">
                            {result.reason ?? result.message}
                          </TableCell>
                          <TableCell className="text-right">
                            <Button variant="ghost" size="sm" onClick={onOpenLog}>
                              查看日志
                            </Button>
                          </TableCell>
                        </TableRow>
                      )
                    })}
                  </TableBody>
                </Table>
              </ScrollArea>
            </div>
          )}
        </div>

        <footer className="flex flex-wrap items-center justify-between gap-3 border-t px-5 py-4">
          <span className="text-xs text-muted-foreground">
            已选 {selectedPaths.length} / {rowPaths.length}
          </span>
          <div className="flex items-center gap-2">
            {report && (
              <Button variant="outline" onClick={onClose} disabled={running}>
                确认关闭
              </Button>
            )}
            <Button onClick={() => void run()} disabled={running || loading || selectedPaths.length === 0}>
              {running && <Loader2 className="size-3 animate-spin" data-icon="inline-start" />}
              开始更新
            </Button>
          </div>
        </footer>
      </section>
    </div>
  )
}
