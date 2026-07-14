import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Archive,
  ChevronDown,
  Copy,
  ExternalLink,
  Inbox,
  Search,
  SquareTerminal,
  X,
} from 'lucide-react'
import { api } from '@/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  copyTaskMonitorDetailInfo,
  formatTaskMonitorDateTime,
  getTaskMonitorDetailInfoRows,
} from '@/taskMonitorDetailCopy'
import { copyTaskCheckPrompt } from '@/taskMonitorPrompt'
import type {
  TaskMonitorDetail,
  TaskMonitorItem,
  TaskMonitorPage,
  TaskMonitorSearchItem,
  TaskMonitorStatus,
} from '@/types'


const statusClass: Record<TaskMonitorStatus, string> = {
  executing: 'border-blue-200 bg-blue-50 text-blue-700',
  waiting_worker: 'border-amber-200 bg-amber-50 text-amber-700',
  waiting_result: 'border-amber-200 bg-amber-50 text-amber-700',
  done: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  blocked: 'border-orange-200 bg-orange-50 text-orange-700',
  failed: 'border-red-200 bg-red-50 text-red-700',
  partial: 'border-violet-200 bg-violet-50 text-violet-700',
  sent: 'border-slate-200 bg-slate-50 text-slate-700',
  unknown: 'border-slate-200 bg-slate-50 text-slate-700',
}

interface TaskMonitorPanelProps {
  openSearchSignal?: number
}

function formatDuration(sentAt: string | null, completedAt: string | null): string {
  if (!sentAt) return '派发时间未知'
  if (completedAt) return `完成于 ${formatTaskMonitorDateTime(completedAt)}`
  const elapsed = Math.max(0, Date.now() - new Date(sentAt).getTime())
  const minutes = Math.floor(elapsed / 60_000)
  if (minutes < 60) return `已派发 ${minutes} 分钟`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `已派发 ${hours} 小时 ${minutes % 60} 分钟`
  return `已派发 ${Math.floor(hours / 24)} 天 ${hours % 24} 小时`
}

function StatusPill({ item }: { item: TaskMonitorItem }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${statusClass[item.status]}`}>
      {item.status_label}
    </span>
  )
}

function TaskCard({ item, onClick }: { item: TaskMonitorItem; onClick: () => void }) {
  return (
    <button
      type="button"
      id={`task-monitor-${item.channel}`}
      onClick={onClick}
      className="w-full rounded-xl border border-border bg-card p-4 text-left shadow-sm transition-colors hover:bg-accent/45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate text-sm font-semibold text-foreground">{item.task_name}</h3>
            <StatusPill item={item} />
            {item.record_conflict && (
              <span className="rounded-full border border-orange-200 bg-orange-50 px-2 py-0.5 text-[11px] text-orange-700">
                记录冲突
              </span>
            )}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">{item.project_name}</p>
        </div>
        <ChevronDown className="size-4 -rotate-90 shrink-0 text-muted-foreground" />
      </div>

      <div className="mt-3 grid gap-2 text-xs text-muted-foreground md:grid-cols-2 xl:grid-cols-4">
        <span className="truncate">Worker：{item.worker || '未知'}</span>
        <span className="truncate" title={item.channel}>Channel：{item.channel}</span>
        <span>{formatDuration(item.sent_at, item.status === 'done' ? item.completed_at : null)}</span>
        <span>更新：{formatTaskMonitorDateTime(item.updated_at)}</span>
      </div>
      {item.archive_days_remaining !== null && (
        <p className="mt-2 text-xs text-muted-foreground">自动归档还剩 {item.archive_days_remaining} 天</p>
      )}
      {item.event_summary && (
        <p className="mt-3 line-clamp-2 rounded-lg bg-accent/40 px-3 py-2 text-xs leading-5 text-foreground/80">
          {item.event_summary}
        </p>
      )}
      {item.errors.length > 0 && (
        <p className="mt-2 line-clamp-1 text-xs text-orange-700">{item.errors.join('；')}</p>
      )}
    </button>
  )
}

function TaskSection({
  title,
  items,
  total,
  open,
  emptyText,
  nextOffset,
  onLoadMore,
  onOpenChange,
  onSelect,
}: {
  title: string
  items: TaskMonitorItem[]
  total: number
  open: boolean
  emptyText: string
  nextOffset: number | null
  onLoadMore?: () => void
  onOpenChange?: (open: boolean) => void
  onSelect: (item: TaskMonitorItem) => void
}) {
  return (
    <details open={open} onToggle={(event) => onOpenChange?.(event.currentTarget.open)} className="group rounded-xl border border-border/70 bg-card/40">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 select-none">
        <div className="flex items-center gap-2">
          <ChevronDown className="size-4 transition-transform group-open:rotate-0 -rotate-90" />
          <h2 className="text-sm font-semibold">{title}</h2>
          <span className="rounded-full bg-accent px-2 py-0.5 text-[11px] text-muted-foreground">{total}</span>
        </div>
      </summary>
      <div className="grid gap-3 border-t border-border/60 p-3">
        {items.length === 0 ? (
          <div className="flex min-h-24 items-center justify-center rounded-lg bg-muted/10 text-sm text-muted-foreground">
            {emptyText}
          </div>
        ) : (
          items.map((item) => <TaskCard key={item.channel} item={item} onClick={() => onSelect(item)} />)
        )}
        {nextOffset !== null && onLoadMore && (
          <Button variant="outline" className="justify-center" onClick={onLoadMore}>加载更多</Button>
        )}
      </div>
    </details>
  )
}

function DetailDrawer({
  detail,
  loading,
  onClose,
  onArchive,
  onRefollow,
  onOpenRecord,
}: {
  detail: TaskMonitorDetail | null
  loading: boolean
  onClose: () => void
  onArchive: () => void
  onRefollow: () => void
  onOpenRecord: () => void
}) {
  const [copySucceeded, setCopySucceeded] = useState(false)
  const [copyError, setCopyError] = useState<string | null>(null)
  const copyResetTimer = useRef<ReturnType<typeof window.setTimeout> | null>(null)

  useEffect(() => () => {
    if (copyResetTimer.current !== null) window.clearTimeout(copyResetTimer.current)
  }, [])

  const handleCopy = useCallback(async () => {
    if (!detail) return
    if (copyResetTimer.current !== null) {
      window.clearTimeout(copyResetTimer.current)
      copyResetTimer.current = null
    }
    setCopySucceeded(false)
    setCopyError(null)
    try {
      await copyTaskMonitorDetailInfo(detail, (text) => navigator.clipboard.writeText(text))
      setCopySucceeded(true)
      copyResetTimer.current = window.setTimeout(() => {
        setCopySucceeded(false)
        copyResetTimer.current = null
      }, 2_000)
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : String(caught)
      setCopyError(`复制基础信息失败：${message}`)
    }
  }, [detail])

  if (!detail && !loading) return null
  return (
    <div className="fixed inset-0 z-40 bg-black/20" onMouseDown={onClose}>
      <aside
        className="ml-auto flex h-full w-full max-w-[560px] flex-col border-l border-border bg-background shadow-2xl"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
          <div className="min-w-0">
            <h2 className="truncate text-lg font-semibold">{detail?.task_name ?? '加载中…'}</h2>
            {detail && <p className="mt-1 text-xs text-muted-foreground">{detail.project_name}</p>}
          </div>
          <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="关闭详情"><X /></Button>
        </div>
        {loading || !detail ? (
          <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">读取详情中…</div>
        ) : (
          <>
            <div className="flex-1 overflow-y-auto px-5 py-4">
              <div className="flex flex-wrap items-center gap-2"><StatusPill item={detail} /></div>
              <div className="mt-4 rounded-xl bg-accent/35 p-4 text-xs">
                <dl className="grid gap-3">
                  {getTaskMonitorDetailInfoRows(detail).map(([label, value]) => (
                    <div key={label} className="grid grid-cols-[5rem_minmax(0,1fr)] gap-2">
                      <dt className="text-muted-foreground">{label}</dt>
                      <dd className="min-w-0 break-all text-foreground">{value}</dd>
                    </div>
                  ))}
                </dl>
                <div className="mt-3 flex flex-col items-end gap-1 border-t border-border/60 pt-3">
                  <Button variant="outline" size="sm" onClick={() => void handleCopy()}>
                    <Copy data-icon="inline-start" />{copySucceeded ? '已复制' : '复制'}
                  </Button>
                  {copyError && <p role="alert" className="max-w-full text-right text-red-700">{copyError}</p>}
                </div>
              </div>
              {detail.errors.length > 0 && (
                <div className="mt-4 rounded-xl border border-orange-200 bg-orange-50 p-3 text-xs leading-5 text-orange-800">
                  {detail.errors.map((error) => <p key={error}>{error}</p>)}
                </div>
              )}
              <h3 className="mt-5 text-sm font-semibold">最近 20 条 channel 事件</h3>
              <div className="mt-2 grid gap-2">
                {detail.recent_events.length === 0 ? (
                  <p className="rounded-lg bg-muted/10 p-4 text-xs text-muted-foreground">暂无可读事件。</p>
                ) : detail.recent_events.map((event, index) => (
                  <div key={`${event.seq ?? index}-${event.kind}`} className="rounded-lg border border-border/60 p-3 text-xs">
                    <div className="flex items-center justify-between gap-2 text-muted-foreground">
                      <span>{event.kind} · {event.by}</span>
                      <span>{formatTaskMonitorDateTime(event.ts)}</span>
                    </div>
                    {event.text && <p className="mt-2 whitespace-pre-wrap break-words leading-5">{event.text}</p>}
                  </div>
                ))}
              </div>
            </div>
            <div className="flex flex-wrap justify-end gap-2 border-t border-border px-5 py-4">
              <Button variant="outline" disabled={!detail.channel_available} onClick={onOpenRecord}>
                <SquareTerminal data-icon="inline-start" />查看完整记录
              </Button>
              {detail.archived_at ? (
                <Button onClick={onRefollow}><ExternalLink data-icon="inline-start" />重新关注</Button>
              ) : (
                <Button variant="outline" onClick={onArchive}><Archive data-icon="inline-start" />归档</Button>
              )}
            </div>
          </>
        )}
      </aside>
    </div>
  )
}

function SearchDialog({
  open,
  query,
  page,
  loading,
  onQueryChange,
  onClose,
  onLoadMore,
  onSelect,
}: {
  open: boolean
  query: string
  page: TaskMonitorPage<TaskMonitorSearchItem>
  loading: boolean
  onQueryChange: (value: string) => void
  onClose: () => void
  onLoadMore: () => void
  onSelect: (item: TaskMonitorSearchItem) => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  useEffect(() => {
    if (open) window.setTimeout(() => inputRef.current?.focus(), 0)
  }, [open])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/30 px-4 pt-[10vh]" onMouseDown={onClose}>
      <div className="flex max-h-[76vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-border bg-background shadow-2xl" onMouseDown={(event) => event.stopPropagation()}>
        <div className="flex items-center gap-3 border-b border-border px-4 py-3">
          <Search className="size-4 text-muted-foreground" />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="搜索任务、项目、PRD、handoff 或 worker 消息…"
            className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
          <kbd className="rounded border border-border bg-accent px-2 py-0.5 text-[10px] text-muted-foreground">ESC</kbd>
        </div>
        <div
          className="overflow-y-auto p-3"
          onScroll={(event) => {
            const target = event.currentTarget
            if (page.next_offset !== null && target.scrollHeight - target.scrollTop - target.clientHeight < 80) onLoadMore()
          }}
        >
          {loading && page.items.length === 0 ? (
            <p className="py-12 text-center text-sm text-muted-foreground">搜索中…</p>
          ) : page.items.length === 0 ? (
            <p className="py-12 text-center text-sm text-muted-foreground">没有匹配结果。</p>
          ) : (
            <div className="grid gap-2">
              {page.items.map((item) => (
                <button key={item.channel} type="button" onClick={() => onSelect(item)} className="rounded-xl border border-border p-3 text-left hover:bg-accent/45">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold">{item.task_name}</p>
                      <p className="mt-0.5 text-xs text-muted-foreground">{item.project_name} · {item.hit_source}</p>
                    </div>
                    <StatusPill item={item} />
                  </div>
                  <p className="mt-2 line-clamp-2 text-xs leading-5 text-foreground/75">{item.snippet}</p>
                </button>
              ))}
              {loading && <p className="py-2 text-center text-xs text-muted-foreground">加载更多…</p>}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function ArchiveConfirmDialog({ open, busy, onCancel, onConfirm }: { open: boolean; busy: boolean; onCancel: () => void; onConfirm: () => void }) {
  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !busy) onCancel()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [busy, onCancel, open])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-6 backdrop-blur-sm">
      <section role="dialog" aria-modal="true" aria-labelledby="archive-monitor-title" className="w-full max-w-md rounded-2xl border bg-card shadow-2xl">
        <header className="border-b px-5 py-4">
          <h3 id="archive-monitor-title" className="text-base font-bold">归档任务监听记录</h3>
        </header>
        <div className="px-5 py-4 text-sm leading-6 text-muted-foreground">
          归档只改变桌面端的关注状态，不会停止 worker，也不会修改 Trellis task 或 Loop run。归档后仍会更新缓存和搜索索引。
        </div>
        <footer className="flex justify-end gap-2 border-t px-5 py-4">
          <Button variant="outline" onClick={onCancel} disabled={busy}>取消</Button>
          <Button onClick={onConfirm} disabled={busy}>{busy ? '归档中…' : '确认归档'}</Button>
        </footer>
      </section>
    </div>
  )
}

const emptyPage = <T extends TaskMonitorItem>(): TaskMonitorPage<T> => ({ items: [], total: 0, next_offset: null })

export function TaskMonitorPanel({ openSearchSignal = 0 }: TaskMonitorPanelProps) {
  const [ongoing, setOngoing] = useState<TaskMonitorPage>(emptyPage)
  const [ended, setEnded] = useState<TaskMonitorPage>(emptyPage)
  const [archived, setArchived] = useState<TaskMonitorPage>(emptyPage)
  const [endedLimit, setEndedLimit] = useState(20)
  const [archivedLimit, setArchivedLimit] = useState(20)
  const [ongoingOpen, setOngoingOpen] = useState(true)
  const [endedOpen, setEndedOpen] = useState(true)
  const [archivedOpen, setArchivedOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [detail, setDetail] = useState<TaskMonitorDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [searchPage, setSearchPage] = useState<TaskMonitorPage<TaskMonitorSearchItem>>(emptyPage)
  const [searchLoading, setSearchLoading] = useState(false)
  const [archiveConfirmOpen, setArchiveConfirmOpen] = useState(false)
  const [archiveBusy, setArchiveBusy] = useState(false)
  const [copySucceeded, setCopySucceeded] = useState(false)
  const [copyError, setCopyError] = useState<string | null>(null)
  const searchRequest = useRef(0)
  const copyResetTimer = useRef<ReturnType<typeof window.setTimeout> | null>(null)

  const loadLists = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const [ongoingPage, endedPage, archivedPage] = await Promise.all([
        api.listTaskMonitorRuns('ongoing', 10_000, 0),
        api.listTaskMonitorRuns('ended', endedLimit, 0),
        api.listTaskMonitorRuns('archived', archivedLimit, 0),
      ])
      setOngoing(ongoingPage)
      setEnded(endedPage)
      setArchived(archivedPage)
      setError(null)
    } catch (caught) {
      setError(`读取任务监听数据失败：${caught}`)
    } finally {
      if (!silent) setLoading(false)
    }
  }, [archivedLimit, endedLimit])

  useEffect(() => {
    const initial = window.setTimeout(() => void loadLists(), 0)
    const timer = window.setInterval(() => void loadLists(true), 5_000)
    return () => {
      window.clearTimeout(initial)
      window.clearInterval(timer)
    }
  }, [loadLists])

  useEffect(() => {
    if (openSearchSignal <= 0) return
    const timer = window.setTimeout(() => setSearchOpen(true), 0)
    return () => window.clearTimeout(timer)
  }, [openSearchSignal])

  useEffect(() => () => {
    if (copyResetTimer.current !== null) window.clearTimeout(copyResetTimer.current)
  }, [])

  useEffect(() => {
    if (!searchOpen) return
    const request = ++searchRequest.current
    const timer = window.setTimeout(async () => {
      setSearchLoading(true)
      try {
        const result = await api.searchTaskMonitor(query, 20, 0)
        if (request === searchRequest.current) setSearchPage(result)
      } finally {
        if (request === searchRequest.current) setSearchLoading(false)
      }
    }, 200)
    return () => window.clearTimeout(timer)
  }, [query, searchOpen])

  useEffect(() => {
    if (!searchOpen) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setSearchOpen(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [searchOpen])

  const selectTask = useCallback(async (item: TaskMonitorItem) => {
    setDetailLoading(true)
    setDetail(null)
    try {
      setDetail(await api.getTaskMonitorDetail(item.channel))
    } finally {
      setDetailLoading(false)
    }
  }, [])

  const refreshDetailAndLists = useCallback(async (channel: string) => {
    await loadLists(true)
    setDetail(await api.getTaskMonitorDetail(channel))
  }, [loadLists])

  const handleArchive = useCallback(async () => {
    if (!detail) return
    setArchiveBusy(true)
    try {
      await api.archiveTaskMonitorRun(detail.channel)
      setArchiveConfirmOpen(false)
      await refreshDetailAndLists(detail.channel)
    } finally {
      setArchiveBusy(false)
    }
  }, [detail, refreshDetailAndLists])

  const handleRefollow = useCallback(async () => {
    if (!detail) return
    await api.refollowTaskMonitorRun(detail.channel)
    await refreshDetailAndLists(detail.channel)
  }, [detail, refreshDetailAndLists])

  const handleOpenRecord = useCallback(async () => {
    if (!detail) return
    const result = await api.openTaskMonitorRecord(detail.channel)
    if (!result.ok) window.alert(result.message)
  }, [detail])

  const loadMoreSearch = useCallback(async () => {
    if (searchLoading || searchPage.next_offset === null) return
    setSearchLoading(true)
    const offset = searchPage.next_offset
    try {
      const next = await api.searchTaskMonitor(query, 20, offset)
      setSearchPage((current) => ({ ...next, items: [...current.items, ...next.items] }))
    } finally {
      setSearchLoading(false)
    }
  }, [query, searchLoading, searchPage.next_offset])

  const handleSearchSelect = useCallback(async (item: TaskMonitorSearchItem) => {
    setSearchOpen(false)
    if (item.group === 'ongoing') {
      setOngoingOpen(true)
    } else if (item.group === 'archived') {
      setArchivedOpen(true)
      setArchived(await api.listTaskMonitorRuns('archived', 10_000, 0))
    } else if (item.group === 'ended') {
      setEndedOpen(true)
      setEnded(await api.listTaskMonitorRuns('ended', 10_000, 0))
    }
    await selectTask(item)
    window.setTimeout(() => {
      document.getElementById(`task-monitor-${item.channel}`)?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    }, 0)
  }, [selectTask])

  const handleCopyCheckPrompt = useCallback(async () => {
    if (copyResetTimer.current !== null) {
      window.clearTimeout(copyResetTimer.current)
      copyResetTimer.current = null
    }
    setCopySucceeded(false)
    try {
      await copyTaskCheckPrompt(ongoing.items, (text) => navigator.clipboard.writeText(text))
      setCopyError(null)
      setCopySucceeded(true)
      copyResetTimer.current = window.setTimeout(() => {
        setCopySucceeded(false)
        copyResetTimer.current = null
      }, 2_000)
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : String(caught)
      setCopyError(`复制检查提示词失败：${message}`)
    }
  }, [ongoing.items])

  return (
    <div className="my-1 flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3 px-1">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-serif font-normal tracking-tight"><Inbox className="size-4 text-primary" />任务监听</h2>
          <p className="mt-1 text-xs text-muted-foreground">仅聚合 Trellis Loop 派发记录；桌面端归档不修改源任务。</p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <div className="flex flex-wrap justify-end gap-2">
            <Button
              variant="outline"
              disabled={loading || ongoing.items.length === 0}
              title={ongoing.items.length === 0 ? '当前页面没有已加载的进行中任务' : undefined}
              onClick={() => void handleCopyCheckPrompt()}
            >
              <Copy data-icon="inline-start" />{copySucceeded ? '已复制' : '复制检查提示词'}
            </Button>
            <Button variant="outline" onClick={() => setSearchOpen(true)}><Search data-icon="inline-start" />搜索 <kbd className="ml-1 text-[10px]">⌘K</kbd></Button>
          </div>
          {copyError && <p role="alert" className="max-w-md text-right text-xs text-red-700">{copyError}</p>}
        </div>
      </div>

      {error && <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}
      {loading ? (
        <Card><CardHeader><CardTitle className="text-sm">正在读取 Loop run…</CardTitle></CardHeader><CardContent><div className="h-24 animate-pulse rounded-lg bg-accent/40" /></CardContent></Card>
      ) : (
        <div className="grid gap-4">
          <TaskSection title="进行中" items={ongoing.items} total={ongoing.total} open={ongoingOpen} onOpenChange={setOngoingOpen} emptyText="当前没有进行中的 Loop run。" nextOffset={null} onSelect={selectTask} />
          <TaskSection title="已结束" items={ended.items} total={ended.total} open={endedOpen} onOpenChange={setEndedOpen} emptyText="尚无 done handoff。" nextOffset={ended.next_offset} onLoadMore={() => setEndedLimit((value) => value + 20)} onSelect={selectTask} />
          <TaskSection title="已归档" items={archived.items} total={archived.total} open={archivedOpen} onOpenChange={setArchivedOpen} emptyText="尚无桌面端归档记录。" nextOffset={archived.next_offset} onLoadMore={() => setArchivedLimit((value) => value + 20)} onSelect={selectTask} />
        </div>
      )}

      <DetailDrawer key={detail?.channel ?? 'loading'} detail={detail} loading={detailLoading} onClose={() => setDetail(null)} onArchive={() => setArchiveConfirmOpen(true)} onRefollow={handleRefollow} onOpenRecord={handleOpenRecord} />
      <ArchiveConfirmDialog open={archiveConfirmOpen} busy={archiveBusy} onCancel={() => setArchiveConfirmOpen(false)} onConfirm={() => void handleArchive()} />
      <SearchDialog
        open={searchOpen}
        query={query}
        page={searchPage}
        loading={searchLoading}
        onQueryChange={setQuery}
        onClose={() => setSearchOpen(false)}
        onLoadMore={loadMoreSearch}
        onSelect={(item) => void handleSearchSelect(item)}
      />
    </div>
  )
}
