import { useRef, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import type { LogEntry, LogLevel } from '@/types'

const LEVEL_STYLES: Record<LogLevel, { color: string; prefix: string }> = {
  task: { color: 'text-blue-400', prefix: '[任务]' },
  success: { color: 'text-green-400', prefix: '[成功]' },
  error: { color: 'text-red-400', prefix: '[失败]' },
  command: { color: 'text-yellow-400', prefix: '[命令]' },
  stdout: { color: 'text-slate-300', prefix: '' },
  stderr: { color: 'text-red-300', prefix: '' },
  info: { color: 'text-slate-400', prefix: '[信息]' },
}

interface LogPanelProps {
  entries: LogEntry[]
  onCopy: () => void
  onClear: () => void
}

export function LogPanel({ entries, onCopy, onClear }: LogPanelProps) {
  const scrollRootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const viewport = scrollRootRef.current?.querySelector<HTMLElement>(
      '[data-slot="scroll-area-viewport"]',
    )
    if (!viewport) return

    requestAnimationFrame(() => {
      viewport.scrollTo({ top: viewport.scrollHeight, behavior: 'smooth' })
    })
  }, [entries])

  return (
    <div className="rounded-xl bg-slate-900 border border-slate-800 shadow-md">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-bold text-slate-100">命令日志</span>
          <span className="text-xs text-slate-500">
            按任务、成功、命令、错误分色，方便复制给排障人员。
          </span>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onCopy}
            className="border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-slate-100"
          >
            复制日志
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={onClear}
            className="border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-slate-100"
          >
            清空显示
          </Button>
        </div>
      </div>

      <div ref={scrollRootRef}>
        <ScrollArea className="h-52">
        <div className="px-4 py-3 font-mono text-xs leading-relaxed">
          {entries.length === 0 ? (
            <span className="text-slate-600 italic">日志为空…</span>
          ) : (
            entries.map((entry) => {
              const style = LEVEL_STYLES[entry.level] ?? LEVEL_STYLES.info
              const text = style.prefix ? `${style.prefix} ${entry.text}` : entry.text
              return (
                <div
                  key={entry.id}
                  className={cn(
                    'whitespace-pre-wrap break-all px-1 -mx-1 rounded',
                    'transition-colors duration-100 hover:bg-slate-800/70',
                    'animate-in fade-in slide-in-from-bottom-1 duration-200',
                    style.color,
                  )}
                >
                  {text}
                </div>
              )
            })
          )}
        </div>
        </ScrollArea>
      </div>
    </div>
  )
}
