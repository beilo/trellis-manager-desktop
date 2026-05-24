import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, Loader2, XCircle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import type { UpdatePreview } from '@/types'

interface UpdatePreviewDialogProps {
  projectPath: string
  preview: UpdatePreview
  allowDirty: boolean
  confirming: boolean
  onCancel: () => void
  onConfirm: (allowDirty: boolean) => void
}

function formatVersion(value: string | null): string {
  return value?.trim() || '未知'
}

export function UpdatePreviewDialog({
  projectPath,
  preview,
  allowDirty,
  confirming,
  onCancel,
  onConfirm,
}: UpdatePreviewDialogProps) {
  const [dirtyAccepted, setDirtyAccepted] = useState(false)
  const dirtyFiles = preview.dirty_files_before ?? []
  const requiresDirtyConfirmation = dirtyFiles.length > 0 && !allowDirty
  const confirmDisabled = !preview.ok || confirming || (requiresDirtyConfirmation && !dirtyAccepted)

  const output = useMemo(() => {
    const trimmed = preview.dry_run_output?.trim()
    return trimmed || 'dry-run 未返回输出。'
  }, [preview.dry_run_output])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !confirming) onCancel()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [confirming, onCancel])

  const confirmAllowDirty = allowDirty || dirtyAccepted

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-6 backdrop-blur-sm">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="update-preview-title"
        className="flex max-h-[86vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border bg-card shadow-2xl"
      >
        <header className="flex items-start justify-between gap-4 border-b px-5 py-4">
          <div className="min-w-0 space-y-1">
            <div className="flex items-center gap-2">
              <h3 id="update-preview-title" className="text-base font-bold text-foreground">
                Update dry-run 预览
              </h3>
              <Badge variant={preview.ok ? 'secondary' : 'destructive'}>
                {preview.ok ? '可确认' : '预览失败'}
              </Badge>
            </div>
            <p className="truncate text-xs text-muted-foreground" title={projectPath}>
              {projectPath}
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={onCancel} disabled={confirming}>
            取消
          </Button>
        </header>

        <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-auto px-5 py-4">
          <div className={`rounded-xl border px-3 py-2 text-sm ${preview.ok ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300' : 'border-destructive/30 bg-destructive/10 text-destructive'}`}>
            <div className="flex items-start gap-2">
              {preview.ok ? <CheckCircle2 className="mt-0.5 size-4 shrink-0" /> : <XCircle className="mt-0.5 size-4 shrink-0" />}
              <span>{preview.message}</span>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-xl border bg-muted/20 p-3">
              <div className="text-xs text-muted-foreground">当前版本</div>
              <div className="mt-1 font-mono text-sm text-foreground">{formatVersion(preview.trellis_version_before)}</div>
            </div>
            <div className="rounded-xl border bg-muted/20 p-3">
              <div className="text-xs text-muted-foreground">最新版本</div>
              <div className="mt-1 font-mono text-sm text-foreground">{formatVersion(preview.latest_version)}</div>
            </div>
            <div className="rounded-xl border bg-muted/20 p-3">
              <div className="text-xs text-muted-foreground">Migration 风险</div>
              <div className="mt-1 text-sm font-medium text-foreground">
                {preview.would_run_migrations ? '可能运行 migrations' : '未检测到 migrations'}
              </div>
            </div>
          </div>

          {preview.would_run_migrations && (
            <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-700 dark:text-amber-300">
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 size-4 shrink-0" />
                <span>dry-run 输出包含 migration 信号，请确认业务项目当前状态后再执行真实 Update。</span>
              </div>
            </div>
          )}

          <div className="rounded-xl border">
            <div className="border-b px-3 py-2 text-sm font-medium text-foreground">Dirty 文件 baseline</div>
            {dirtyFiles.length > 0 ? (
              <ScrollArea className="max-h-32">
                <ul className="space-y-1 p-3 font-mono text-xs text-muted-foreground">
                  {dirtyFiles.map((file) => (
                    <li key={file}>{file}</li>
                  ))}
                </ul>
              </ScrollArea>
            ) : (
              <div className="px-3 py-3 text-sm text-muted-foreground">预览前工作区无 dirty 文件。</div>
            )}
          </div>

          <div className="rounded-xl border">
            <div className="border-b px-3 py-2 text-sm font-medium text-foreground">dry-run 输出</div>
            <ScrollArea className="max-h-56">
              <pre className="whitespace-pre-wrap break-words p-3 font-mono text-xs leading-5 text-muted-foreground">{output}</pre>
            </ScrollArea>
          </div>

          {requiresDirtyConfirmation && (
            <label className="flex cursor-pointer select-none items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm">
              <input
                type="checkbox"
                checked={dirtyAccepted}
                onChange={(event) => setDirtyAccepted(event.target.checked)}
                className="mt-1 size-4 accent-primary"
                disabled={confirming}
              />
              <span className="text-amber-800 dark:text-amber-200">
                我确认该项目存在未提交变更，仍要执行 <span className="font-mono">tl update --force</span>。
              </span>
            </label>
          )}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t px-5 py-4">
          <Button variant="outline" onClick={onCancel} disabled={confirming}>
            取消
          </Button>
          <Button onClick={() => onConfirm(confirmAllowDirty)} disabled={confirmDisabled}>
            {confirming && <Loader2 className="size-3 animate-spin" data-icon="inline-start" />}
            {confirming ? '执行中…' : '确认 Update'}
          </Button>
        </footer>
      </section>
    </div>
  )
}
