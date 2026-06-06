import { useState } from 'react'
import { ChevronDown, ChevronRight, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { JsonlFileResult } from '@/types'

interface JsonlViewerProps {
  result: JsonlFileResult
  loading?: boolean
  onLoadMore?: () => void
}

function recordSummary(item: unknown): string {
  if (!item || typeof item !== 'object') return String(item)
  const record = item as Record<string, unknown>
  const parts = ['ts', 'timestamp', 'event', 'type', 'message', 'summary', 'step']
    .map((key) => record[key])
    .filter((value) => typeof value === 'string' || typeof value === 'number')
    .map(String)
  return parts.length > 0 ? parts.join(' · ') : JSON.stringify(item).slice(0, 140)
}

export function JsonlViewer({ result, loading = false, onLoadMore }: JsonlViewerProps) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  const toggle = (index: number) => {
    setExpanded((current) => {
      const next = new Set(current)
      if (next.has(index)) next.delete(index)
      else next.add(index)
      return next
    })
  }

  if (!result.ok) {
    return (
      <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
        {result.error?.message ?? '读取 JSONL 失败'}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      {result.errors.length > 0 && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700">
          {result.errors.length} 行解析失败：{result.errors.map((error) => `第 ${error.line} 行`).join('、')}
        </div>
      )}

      <div className="flex flex-col gap-2">
        {result.items.length === 0 ? (
          <div className="rounded-lg border bg-muted/20 px-3 py-6 text-center text-sm text-muted-foreground">
            当前页没有 JSONL 记录
          </div>
        ) : (
          result.items.map((item, index) => {
            const physicalIndex = result.offset + index
            const open = expanded.has(physicalIndex)
            return (
              <div key={physicalIndex} className="rounded-lg border bg-background">
                <button
                  type="button"
                  className="flex w-full items-start gap-2 px-3 py-2 text-left text-sm hover:bg-accent/60"
                  onClick={() => toggle(physicalIndex)}
                >
                  {open ? <ChevronDown className="mt-0.5 size-4 shrink-0" /> : <ChevronRight className="mt-0.5 size-4 shrink-0" />}
                  <span className="min-w-0 flex-1 truncate">{recordSummary(item)}</span>
                </button>
                {open && (
                  <pre className="max-h-72 overflow-auto border-t bg-muted/25 p-3 font-mono text-xs leading-5">
                    {JSON.stringify(item, null, 2)}
                  </pre>
                )}
              </div>
            )
          })
        )}
      </div>

      {result.next_offset != null && onLoadMore && (
        <Button type="button" variant="outline" size="sm" onClick={onLoadMore} disabled={loading}>
          {loading && <Loader2 className="size-3 animate-spin" data-icon="inline-start" />}
          加载更多
        </Button>
      )}
    </div>
  )
}
