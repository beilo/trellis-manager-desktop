import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Copy,
  FolderOpen,
  FileText,
  Wrench,
  Package,
  Calendar,
  User,
  GitBranch,
  Archive,
  Terminal,
  Send,
  Loader2,
  RefreshCw,
  SquareArrowOutUpRight,
} from 'lucide-react'
import { api } from '@/api'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { FileTreePanel } from './FileTreePanel'
import { flattenPreviewableFiles } from './fileTreeUtils'
import { JsonlViewer } from './JsonlViewer'
import { MarkdownViewer } from './MarkdownViewer'
import { TaskStatusBadge } from './TaskStatusBadge'
import type {
  EnvironmentItem,
  FileTreeItem,
  JsonlFileResult,
  OperationReport,
  TaskDocumentKind,
  TextFileResult,
  TrellisTaskItem,
} from '@/types'

export type TaskDetailTab = 'detail' | 'prd' | 'design' | 'implement' | 'context'

interface TaskDetailProps {
  task: TrellisTaskItem
  projectPath: string
  helmStatus: EnvironmentItem | null
  helmLoading: boolean
  cursorStatus: EnvironmentItem | null
  cursorLoading: boolean
  onOpenDir: (path: string) => void
  onOpenIterm: (path: string) => void
  onOpenCursor: (path?: string) => Promise<void>
  onPushHelm: (projectPath: string, taskPath: string) => Promise<OperationReport>
  initialTab?: TaskDetailTab
}

function copyCommand(cmd: string) {
  navigator.clipboard.writeText(cmd)
}

function getTaskCommands(task: TrellisTaskItem): string[] {
  const base = `python3 ./.trellis/scripts/task.py`
  return [
    `${base} current --source`,
    `${base} start ${task.dir_name}`,
    `${base} archive ${task.dir_name}`,
  ]
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString('zh-CN')
  } catch {
    return dateStr
  }
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

function helmDisabledReason(task: TrellisTaskItem, helmStatus: EnvironmentItem | null, helmLoading: boolean): string | null {
  if (!task.has_prd) return '需要 PRD 文档'
  if (helmLoading) return '正在检查 Helm'
  if (!helmStatus?.ok) return '未安装 Helm'
  return null
}

function isJsonlResult(result: TextFileResult | JsonlFileResult | null): result is JsonlFileResult {
  return Boolean(result && 'items' in result)
}

function taskLocalPath(task: TrellisTaskItem, item: FileTreeItem): string {
  const prefix = `tasks/${task.dir_name}/`
  return item.path.startsWith(prefix) ? item.path.slice(prefix.length) : item.path
}

function preferredContextFile(files: FileTreeItem[]): FileTreeItem | null {
  const orderedNames = ['implement.jsonl', 'research.jsonl', 'check.jsonl', 'debug.jsonl']
  for (const name of orderedNames) {
    const found = files.find((file) => file.path.endsWith(`/${name}`) || file.path === name)
    if (found) return found
  }
  return files.find((file) => file.path.includes('/research/') && file.name.endsWith('.md')) ?? files[0] ?? null
}

function DocumentPane({ task, doc, label }: { task: TrellisTaskItem; doc: TaskDocumentKind; label: string }) {
  const [result, setResult] = useState<TextFileResult | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let cancelled = false
    void Promise.resolve().then(() => {
      if (cancelled) return
      setLoading(true)
      setResult(null)
      void api.readTaskDocument(task.path, doc)
        .then((next) => {
          if (!cancelled) setResult(next)
        })
        .catch((error: unknown) => {
          if (!cancelled) {
            setResult({
              ok: false,
              path: null,
              content: null,
              size: null,
              truncated: false,
              error: { code: 'bridge_error', message: errorMessage(error) },
            })
          }
        })
        .finally(() => {
          if (!cancelled) setLoading(false)
          })
    })
    return () => {
      cancelled = true
    }
  }, [doc, task.path])

  const content = result?.content ?? ''

  return (
    <div className="flex min-h-[26rem] flex-col gap-3 rounded-lg border bg-background p-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-semibold">{label}</span>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => navigator.clipboard.writeText(content)}
          disabled={!result?.ok || !content}
        >
          <Copy className="size-3" data-icon="inline-start" />
          复制全文
        </Button>
      </div>
      {loading ? (
        <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          正在读取文档…
        </div>
      ) : result?.ok ? (
        <ScrollArea className="h-[24rem] pr-3">
          <MarkdownViewer content={content} />
        </ScrollArea>
      ) : (
        <div className="rounded border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {result?.error?.message ?? '文件不存在。'}
        </div>
      )}
    </div>
  )
}

function TaskContextPane({ task }: { task: TrellisTaskItem }) {
  const [tree, setTree] = useState<FileTreeItem[]>([])
  const [selected, setSelected] = useState<FileTreeItem | null>(null)
  const [content, setContent] = useState<TextFileResult | JsonlFileResult | null>(null)
  const [loadingTree, setLoadingTree] = useState(false)
  const [loadingFile, setLoadingFile] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadTree = useCallback(async () => {
    if (task.archived) {
      setTree([])
      setSelected(null)
      setContent(null)
      setError('归档任务暂不支持 Context 读取。')
      return
    }
    setLoadingTree(true)
    setError(null)
    try {
      const result = await api.listTaskContextFiles(task.path)
      if (!result.ok) {
        setTree([])
        setSelected(null)
        setContent(null)
        setError(result.error?.message ?? 'Context 文件列表读取失败。')
        return
      }
      const files = flattenPreviewableFiles(result.items).filter((item) => {
        const local = taskLocalPath(task, item)
        return ['implement.jsonl', 'research.jsonl', 'check.jsonl', 'debug.jsonl'].includes(local)
          || (local.startsWith('research/') && item.name.endsWith('.md'))
      })
      setTree(result.items)
      setSelected(preferredContextFile(files))
    } catch (err) {
      setError(`Context 文件列表读取失败：${err}`)
    } finally {
      setLoadingTree(false)
    }
  }, [task])

  useEffect(() => {
    void Promise.resolve().then(loadTree)
  }, [loadTree])

  useEffect(() => {
    let cancelled = false
    void Promise.resolve().then(() => {
      if (cancelled) return
      if (!selected) {
        setContent(null)
        return
      }
      setLoadingFile(true)
      setContent(null)
      void api.readTaskContextFile(task.path, taskLocalPath(task, selected), 200, 0)
        .then((result) => {
          if (!cancelled) setContent(result)
        })
        .catch((err: unknown) => {
          if (!cancelled) {
            setContent({
              ok: false,
              path: null,
              content: null,
              size: null,
              truncated: false,
              error: { code: 'bridge_error', message: errorMessage(err) },
            })
          }
        })
        .finally(() => {
          if (!cancelled) setLoadingFile(false)
        })
    })
    return () => {
      cancelled = true
    }
  }, [selected, task])

  const loadMore = async () => {
    if (!selected || !isJsonlResult(content) || content.next_offset == null) return
    setLoadingFile(true)
    try {
      const next = await api.readTaskContextFile(task.path, taskLocalPath(task, selected), content.limit, content.next_offset)
      if (isJsonlResult(next)) {
        setContent({
          ...next,
          items: [...content.items, ...next.items],
          errors: [...content.errors, ...next.errors],
          offset: content.offset,
        })
      }
    } finally {
      setLoadingFile(false)
    }
  }

  return (
    <div className="grid min-h-[26rem] gap-3 md:grid-cols-[16rem_minmax(0,1fr)]">
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-semibold">Context 文件</span>
          <Button type="button" variant="ghost" size="sm" onClick={loadTree} disabled={loadingTree}>
            <RefreshIcon loading={loadingTree} />
          </Button>
        </div>
        <FileTreePanel items={tree} selectedPath={selected?.path ?? null} onSelect={setSelected} />
      </div>
      <div className="rounded-lg border bg-background p-3">
        {error ? (
          <div className="rounded border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div>
        ) : loadingFile && !content ? (
          <div className="flex h-full items-center justify-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            正在读取文件…
          </div>
        ) : isJsonlResult(content) ? (
          <JsonlViewer result={content} loading={loadingFile} onLoadMore={loadMore} />
        ) : content?.ok ? (
          <ScrollArea className="h-[24rem] pr-3">
            <MarkdownViewer content={content.content ?? ''} />
          </ScrollArea>
        ) : content ? (
          <div className="rounded border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {content.error?.message ?? '读取文件失败。'}
          </div>
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">请选择 Context 文件</div>
        )}
      </div>
    </div>
  )
}

function RefreshIcon({ loading }: { loading: boolean }) {
  return loading ? <Loader2 className="size-3 animate-spin" /> : <RefreshCw className="size-3" />
}

export function TaskDetail({
  task,
  projectPath,
  helmStatus,
  helmLoading,
  cursorStatus,
  cursorLoading,
  onOpenDir,
  onOpenIterm,
  onOpenCursor,
  onPushHelm,
  initialTab = 'detail',
}: TaskDetailProps) {
  const commands = getTaskCommands(task)
  const [activeTab, setActiveTab] = useState<TaskDetailTab>(initialTab)
  useEffect(() => {
    void Promise.resolve().then(() => setActiveTab(initialTab))
  }, [initialTab, task.path])
  const documentTabs = useMemo(
    () => [
      { value: 'prd' as const, label: 'PRD', exists: task.has_prd, doc: 'prd' as const },
      { value: 'design' as const, label: 'Design', exists: task.has_design, doc: 'design' as const },
      { value: 'implement' as const, label: 'Implement', exists: task.has_implement, doc: 'implement' as const },
    ],
    [task.has_design, task.has_implement, task.has_prd],
  )
  // 只有活跃任务需要进入项目根目录继续工作，归档和已完成任务不展示 iTerm2 入口。
  const canOpenInIterm = !task.archived && (task.status === 'planning' || task.status === 'in_progress')
  // Cursor 入口同样只给活跃任务，避免把已完成任务误当成继续编辑入口。
  const canOpenInCursor = !task.archived && (task.status === 'planning' || task.status === 'in_progress')
  const [pushingHelm, setPushingHelm] = useState(false)
  const [helmFeedback, setHelmFeedback] = useState<{ ok: boolean; message: string } | null>(null)
  const [cursorFeedback, setCursorFeedback] = useState<{ ok: boolean; message: string } | null>(null)
  const disabledReason = helmDisabledReason(task, helmStatus, helmLoading)
  const cursorDisabledReason = cursorLoading
    ? '正在检查 Cursor'
    : cursorStatus && !cursorStatus.ok
      ? cursorStatus.message
      : null

  return (
    <div className="flex flex-col gap-4 p-4 rounded-lg border bg-card">
      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as TaskDetailTab)}>
        <TabsList className="flex w-full flex-wrap justify-start">
          <TabsTrigger value="detail">详情</TabsTrigger>
          {documentTabs.map((item) => (
            <TabsTrigger
              key={item.value}
              value={item.value}
              disabled={!item.exists}
              title={item.exists ? item.label : '文件不存在'}
            >
              {item.label}
            </TabsTrigger>
          ))}
          <TabsTrigger value="context" disabled={task.archived} title={task.archived ? '归档任务暂不支持 Context' : 'Context'}>
            Context
          </TabsTrigger>
        </TabsList>

        <TabsContent value="detail" className="flex flex-col gap-4">
          {/* 错误提示 */}
          {task.error && (
            <div className="p-2 rounded bg-red-50 border border-red-200 text-sm text-red-700">
              读取错误：{task.error}
            </div>
          )}

      {/* 元数据 */}
      <div className="flex flex-col gap-2">
        <h3 className="font-bold text-lg">{task.title}</h3>
        <div className="flex items-center gap-2 flex-wrap">
          <TaskStatusBadge status={task.status} />
          {task.archived && (
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <Archive className="size-3" />
              已归档 {task.archive_month}
            </span>
          )}
          {task.assignee && (
            <span className="flex items-center gap-1 text-sm text-muted-foreground">
              <User className="size-3" />
              {task.assignee}
            </span>
          )}
          {task.priority && (
            <span className="text-sm text-muted-foreground">优先级: {task.priority}</span>
          )}
        </div>
      </div>

      {/* 时间信息 */}
      <div className="flex items-center gap-4 text-sm text-muted-foreground">
        {task.created_at && (
          <span className="flex items-center gap-1">
            <Calendar className="size-3" />
            创建: {formatDate(task.created_at)}
          </span>
        )}
        {task.completed_at && (
          <span className="flex items-center gap-1">
            <Calendar className="size-3" />
            完成: {formatDate(task.completed_at)}
          </span>
        )}
      </div>

      {/* Branch 信息 */}
      {(task.branch || task.base_branch) && (
        <div className="flex items-center gap-2 text-sm">
          <GitBranch className="size-3 text-muted-foreground" />
          {task.branch && <span className="text-muted-foreground">分支: {task.branch}</span>}
          {task.base_branch && <span className="text-muted-foreground">基础: {task.base_branch}</span>}
        </div>
      )}

      {/* 文档完整度 */}
      <div className="flex gap-3">
        <span
          className={`flex items-center gap-1 text-sm ${task.has_prd ? 'text-green-600' : 'text-red-500'}`}
          title="PRD 文档"
        >
          <FileText className="size-3" />
          PRD {task.has_prd ? '✓' : '✗'}
        </span>
        <span
          className={`flex items-center gap-1 text-sm ${task.has_design ? 'text-green-600' : 'text-red-500'}`}
          title="Design 文档"
        >
          <Wrench className="size-3" />
          Design {task.has_design ? '✓' : '✗'}
        </span>
        <span
          className={`flex items-center gap-1 text-sm ${task.has_implement ? 'text-green-600' : 'text-red-500'}`}
          title="Implement 文档"
        >
          <Package className="size-3" />
          Impl {task.has_implement ? '✓' : '✗'}
        </span>
      </div>

      {/* 子任务进度 */}
      {task.child_total > 0 && (
        <div className="flex items-center gap-2">
          <span className="text-sm">子任务进度：</span>
          <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-green-500 transition-all"
              style={{ width: `${(task.child_done / task.child_total) * 100}%` }}
            />
          </div>
          <span className="text-sm text-muted-foreground">
            {task.child_done}/{task.child_total}
          </span>
        </div>
      )}

      {/* 复制命令 */}
      <div className="flex flex-col gap-2">
        <span className="text-sm font-medium">下一步动作：</span>
        {commands.map((cmd) => (
          <div key={cmd} className="flex items-center gap-2">
            <code className="flex-1 text-xs bg-muted px-2 py-1 rounded overflow-x-auto">
              {cmd}
            </code>
            <Button size="sm" variant="ghost" onClick={() => copyCommand(cmd)} title="复制">
              <Copy className="size-3" />
            </Button>
          </div>
        ))}
      </div>

      {/* 打开目录 */}
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={() => onOpenDir(task.path)}>
          <FolderOpen className="size-4" />
          打开任务目录
        </Button>
        {canOpenInIterm && (
          <Button variant="outline" onClick={() => onOpenIterm(projectPath)}>
            <Terminal className="size-4" />
            在 iTerm2 中打开
          </Button>
        )}
        {canOpenInCursor && (
          <Button
            variant="outline"
            onClick={async () => {
              setCursorFeedback(null)
              try {
                await onOpenCursor(projectPath)
              } catch (error) {
                setCursorFeedback({ ok: false, message: errorMessage(error) })
              }
            }}
            disabled={cursorLoading || !cursorStatus?.ok}
            title={cursorDisabledReason ?? '在 Cursor 中打开项目根目录'}
          >
            {cursorLoading ? <Loader2 className="size-4 animate-spin" /> : <SquareArrowOutUpRight className="size-4" />}
            在 Cursor 中打开
          </Button>
        )}
        <Button
          variant="outline"
          onClick={async () => {
            setPushingHelm(true)
            setHelmFeedback(null)
            try {
              const report = await onPushHelm(projectPath, task.path)
              setHelmFeedback({ ok: true, message: report.message })
            } catch (error) {
              setHelmFeedback({ ok: false, message: errorMessage(error) })
            } finally {
              setPushingHelm(false)
            }
          }}
          disabled={Boolean(disabledReason) || pushingHelm}
          title={disabledReason ?? '推送到 Helm'}
        >
          {pushingHelm ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
          {pushingHelm ? '推送中' : '推送到 Helm'}
        </Button>
      </div>

      {cursorFeedback && (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {cursorFeedback.message}
        </div>
      )}

      {helmFeedback && (
        <div
          className={`rounded border px-3 py-2 text-sm ${
            helmFeedback.ok
              ? 'border-green-200 bg-green-50 text-green-700'
              : 'border-red-200 bg-red-50 text-red-700'
          }`}
        >
          {helmFeedback.message}
        </div>
      )}
        </TabsContent>

        {documentTabs.map((item) => (
          <TabsContent key={item.value} value={item.value}>
            {item.exists ? (
              <DocumentPane task={task} doc={item.doc} label={item.label} />
            ) : (
              <div className="rounded-lg border bg-muted/20 px-3 py-8 text-center text-sm text-muted-foreground">
                {item.label} 文件不存在。
              </div>
            )}
          </TabsContent>
        ))}

        <TabsContent value="context">
          <TaskContextPane task={task} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
