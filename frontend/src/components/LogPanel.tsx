import { useRef, useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import { Terminal, ChevronUp, ChevronDown, Copy, Trash2, Maximize2, Minimize2 } from 'lucide-react'
import type { LogEntry, LogLevel } from '@/types'

const LEVEL_STYLES: Record<LogLevel, { color: string; prefix: string }> = {
  task: { color: 'text-blue-400 font-bold border-l-2 border-blue-500 pl-2 my-1', prefix: '[任务]' },
  success: { color: 'text-emerald-400 font-bold border-l-2 border-emerald-500 pl-2 my-1', prefix: '[成功]' },
  error: { color: 'text-rose-400 font-bold border-l-2 border-rose-500 pl-2 my-1', prefix: '[失败]' },
  command: { color: 'text-amber-300 font-mono opacity-90', prefix: '$' },
  stdout: { color: 'text-slate-300 font-mono opacity-80', prefix: '' },
  stderr: { color: 'text-rose-300 font-mono opacity-80', prefix: '' },
  info: { color: 'text-slate-400 font-medium', prefix: '[信息]' },
}

interface LogPanelProps {
  entries: LogEntry[]
  onCopy: () => void
  onClear: () => void
}

type PanelState = 'collapsed' | 'expanded' | 'maximized'

export function LogPanel({ entries, onCopy, onClear }: LogPanelProps) {
  const [panelState, setPanelState] = useState<PanelState>('collapsed')
  const scrollRootRef = useRef<HTMLDivElement>(null)
  const prevLengthRef = useRef(entries.length)

  // Auto-open when new task/command logs arrive
  useEffect(() => {
    if (entries.length > prevLengthRef.current) {
      const lastEntry = entries[entries.length - 1]
      if (lastEntry && (lastEntry.level === 'task' || lastEntry.level === 'command')) {
        window.requestAnimationFrame(() => setPanelState('expanded'))
      }
    }
    prevLengthRef.current = entries.length
  }, [entries])

  // Scroll to bottom on new entries
  useEffect(() => {
    if (panelState === 'collapsed') return

    const viewport = scrollRootRef.current?.querySelector<HTMLElement>(
      '[data-slot="scroll-area-viewport"]',
    )
    if (!viewport) return

    requestAnimationFrame(() => {
      viewport.scrollTo({ top: viewport.scrollHeight, behavior: 'smooth' })
    })
  }, [entries, panelState])

  const toggleExpand = () => {
    if (panelState === 'collapsed') {
      setPanelState('expanded')
    } else {
      setPanelState('collapsed')
    }
  }

  const toggleMaximize = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (panelState === 'maximized') {
      setPanelState('expanded')
    } else {
      setPanelState('maximized')
    }
  }

  // Calculate dynamic heights
  const heightClass = {
    collapsed: 'h-11',
    expanded: 'h-72',
    maximized: 'h-[75vh]',
  }[panelState]

  const activeTasksCount = entries.filter((e) => e.level === 'task').length
  const errorsCount = entries.filter((e) => e.level === 'error').length

  return (
    <div
      className={cn(
        'fixed bottom-0 left-0 right-0 z-50 px-6 pb-0 bg-background/40 backdrop-blur-md border-t border-border/10',
        'transition-all duration-300 ease-out'
      )}
    >
      <div
        className={cn(
          'mx-auto max-w-[1400px] rounded-t-xl bg-slate-950 border-t border-x border-slate-800 shadow-2xl overflow-hidden',
          'transition-all duration-300 ease-out transition-drawer',
          heightClass
        )}
      >
        {/* Header Bar */}
        <div
          onClick={toggleExpand}
          className="group flex items-center justify-between px-5 h-11 border-b border-slate-800/80 cursor-pointer select-none bg-slate-950 hover:bg-slate-900/60 transition-colors duration-150"
        >
          {/* Left info */}
          <div className="flex items-center gap-2.5">
            <div className="relative flex size-5 items-center justify-center rounded bg-slate-900 text-slate-400 border border-slate-800">
              <Terminal className="size-3" />
              {activeTasksCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 size-1.5 rounded-full bg-blue-500 animate-ping" />
              )}
            </div>
            <span className="text-xs font-bold text-slate-200 tracking-wide uppercase">命令控制台</span>
            <div className="flex items-center gap-1.5 ml-2">
              <span className="text-[10px] font-medium text-slate-500 bg-slate-900 px-2 py-0.5 rounded border border-slate-800/80 tabular-nums">
                {entries.length} 运行记录
              </span>
              {errorsCount > 0 && (
                <span className="text-[10px] font-bold text-rose-400 bg-rose-950/20 px-2 py-0.5 rounded border border-rose-950/35 tabular-nums animate-pulse">
                  {errorsCount} 错误
                </span>
              )}
            </div>
          </div>

          {/* Drag Handle Indicator */}
          <div className="hidden sm:flex flex-col gap-0.5 items-center opacity-40 group-hover:opacity-100 transition-opacity duration-200">
            <div className="w-8 h-1 rounded-full bg-slate-700" />
          </div>

          {/* Right actions */}
          <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
            {panelState !== 'collapsed' && (
              <>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onCopy}
                  className="size-7 text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent hover:border-slate-800"
                  title="复制日志"
                >
                  <Copy className="size-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onClear}
                  className="size-7 text-slate-400 hover:text-rose-400 hover:bg-rose-950/10 border border-transparent hover:border-rose-950/20"
                  title="清空显示"
                >
                  <Trash2 className="size-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={toggleMaximize}
                  className="size-7 text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent hover:border-slate-800"
                  title={panelState === 'maximized' ? '还原' : '最大化'}
                >
                  {panelState === 'maximized' ? <Minimize2 className="size-3.5" /> : <Maximize2 className="size-3.5" />}
                </Button>
              </>
            )}
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleExpand}
              className="size-7 text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent hover:border-slate-800"
            >
              {panelState === 'collapsed' ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
            </Button>
          </div>
        </div>

        {/* Scroll Content */}
        {panelState !== 'collapsed' && (
          <div ref={scrollRootRef} className="bg-slate-950/95 h-[calc(100%-44px)]">
            <ScrollArea className="h-full custom-scrollbar">
              <div className="px-6 py-4 font-mono text-xs leading-relaxed">
                {entries.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-16 gap-2 text-slate-600 italic select-none">
                    <Terminal className="size-8 stroke-[1.5] opacity-50 animate-pulse" />
                    <span>暂无命令执行记录…</span>
                  </div>
                ) : (
                  <div className="flex flex-col gap-1.5">
                    {entries.map((entry) => {
                      const style = LEVEL_STYLES[entry.level] ?? LEVEL_STYLES.info
                      const text = style.prefix ? `${style.prefix} ${entry.text}` : entry.text
                      return (
                        <div
                          key={entry.id}
                          className={cn(
                            'whitespace-pre-wrap break-all px-2 py-0.5 rounded transition-colors duration-100',
                            'hover:bg-slate-900/60',
                            'animate-in fade-in slide-in-from-bottom-0.5 duration-150',
                            style.color,
                          )}
                        >
                          {text}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </ScrollArea>
          </div>
        )}
      </div>
    </div>
  )
}
