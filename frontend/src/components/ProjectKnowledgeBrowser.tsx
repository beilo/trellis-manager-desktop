import { useCallback, useEffect, useState } from 'react'
import { BookOpen, Loader2, RefreshCw } from 'lucide-react'
import { api } from '@/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { FileTreePanel } from './FileTreePanel'
import { flattenPreviewableFiles } from './fileTreeUtils'
import { JsonlViewer } from './JsonlViewer'
import { MarkdownViewer } from './MarkdownViewer'
import type { FileTreeItem, JsonlFileResult, ProjectStatus, TextFileResult } from '@/types'

interface ProjectKnowledgeBrowserProps {
  projectPath: string | null
  projectStatus: ProjectStatus | null
}

function rootItem(name: 'spec' | 'workspace', children: FileTreeItem[]): FileTreeItem {
  return {
    path: name,
    name,
    type: 'directory',
    size: 0,
    mtime: 0,
    children,
  }
}

function isJsonlResult(result: TextFileResult | JsonlFileResult | null): result is JsonlFileResult {
  return Boolean(result && 'items' in result)
}

function preferredKnowledgeFile(items: FileTreeItem[]): FileTreeItem | null {
  const files = flattenPreviewableFiles(items)
  return files.find((file) => file.path === 'spec/guides/index.md')
    ?? files.find((file) => file.path === 'workspace/index.md')
    ?? files[0]
    ?? null
}

export function ProjectKnowledgeBrowser({ projectPath, projectStatus }: ProjectKnowledgeBrowserProps) {
  const [items, setItems] = useState<FileTreeItem[]>([])
  const [selected, setSelected] = useState<FileTreeItem | null>(null)
  const [content, setContent] = useState<TextFileResult | JsonlFileResult | null>(null)
  const [loadingTree, setLoadingTree] = useState(false)
  const [loadingFile, setLoadingFile] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadTree = useCallback(async () => {
    if (!projectPath || !projectStatus?.has_trellis) return
    setLoadingTree(true)
    setError(null)
    try {
      const [spec, workspace] = await Promise.all([
        api.listProjectFiles(projectPath, 'spec'),
        api.listProjectFiles(projectPath, 'workspace'),
      ])
      const nextItems = [
        rootItem('spec', spec.ok ? spec.items : []),
        rootItem('workspace', workspace.ok ? workspace.items : []),
      ]
      setItems(nextItems)
      setSelected(preferredKnowledgeFile(nextItems))
      if (!spec.ok && !workspace.ok) {
        setError(spec.error?.message ?? workspace.error?.message ?? '知识库文件列表读取失败。')
      }
    } catch (err) {
      setItems([])
      setSelected(null)
      setError(`知识库文件列表读取失败：${err}`)
    } finally {
      setLoadingTree(false)
    }
  }, [projectPath, projectStatus?.has_trellis])

  useEffect(() => {
    void Promise.resolve().then(() => {
      setItems([])
      setSelected(null)
      setContent(null)
      setError(null)
      void loadTree()
    })
  }, [loadTree])

  useEffect(() => {
    let cancelled = false
    void Promise.resolve().then(() => {
      if (cancelled) return
      if (!projectPath || !selected || selected.type !== 'file') {
        setContent(null)
        return
      }
      setLoadingFile(true)
      setContent(null)
      const reader = selected.name.endsWith('.jsonl')
        ? api.readProjectJsonl(projectPath, selected.path, 200, 0)
        : api.readProjectFile(projectPath, selected.path)
      void reader
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
              error: { code: 'bridge_error', message: String(err) },
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
  }, [projectPath, selected])

  const loadMore = async () => {
    if (!projectPath || !selected || !isJsonlResult(content) || content.next_offset == null) return
    setLoadingFile(true)
    try {
      const next = await api.readProjectJsonl(projectPath, selected.path, content.limit, content.next_offset)
      setContent({
        ...next,
        items: [...content.items, ...next.items],
        errors: [...content.errors, ...next.errors],
        offset: content.offset,
      })
    } finally {
      setLoadingFile(false)
    }
  }

  if (!projectPath) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-sm text-muted-foreground">请先选择项目。</CardContent>
      </Card>
    )
  }

  if (!projectStatus?.has_trellis) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-sm text-muted-foreground">该项目尚未初始化 Trellis，请先执行 Init。</CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3 pb-3">
        <div className="flex min-w-0 items-center gap-2">
          <BookOpen className="size-4 text-indigo-500" />
          <div className="flex min-w-0 flex-col">
            <span className="text-sm font-semibold text-foreground">项目知识库</span>
            <span className="text-xs text-muted-foreground">只读浏览 `.trellis/spec` 与 `.trellis/workspace`。</span>
          </div>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={loadTree} disabled={loadingTree}>
          {loadingTree ? <Loader2 className="size-3 animate-spin" data-icon="inline-start" /> : <RefreshCw className="size-3" data-icon="inline-start" />}
          刷新
        </Button>
      </CardHeader>
      <CardContent className="grid min-h-[32rem] gap-3 pt-0 md:grid-cols-[18rem_minmax(0,1fr)]">
        <FileTreePanel items={items} selectedPath={selected?.path ?? null} onSelect={setSelected} />
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
            <ScrollArea className="h-[30rem] pr-3">
              <MarkdownViewer content={content.content ?? ''} />
            </ScrollArea>
          ) : content ? (
            <div className="rounded border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {content.error?.message ?? '读取文件失败。'}
            </div>
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">请选择知识库文件。</div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
