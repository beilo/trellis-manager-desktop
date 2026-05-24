import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { cn } from '@/lib/utils'

interface MarkdownViewerProps {
  content: string
  className?: string
}

export function MarkdownViewer({ content, className }: MarkdownViewerProps) {
  return (
    <div className={cn('space-y-3 text-sm leading-6 text-foreground', className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        components={{
          h1: ({ className, ...props }) => <h1 className={cn('text-xl font-bold tracking-normal', className)} {...props} />,
          h2: ({ className, ...props }) => <h2 className={cn('text-lg font-bold tracking-normal', className)} {...props} />,
          h3: ({ className, ...props }) => <h3 className={cn('text-base font-semibold tracking-normal', className)} {...props} />,
          p: ({ className, ...props }) => <p className={cn('whitespace-pre-wrap break-words', className)} {...props} />,
          ul: ({ className, ...props }) => <ul className={cn('list-disc space-y-1 pl-5', className)} {...props} />,
          ol: ({ className, ...props }) => <ol className={cn('list-decimal space-y-1 pl-5', className)} {...props} />,
          blockquote: ({ className, ...props }) => <blockquote className={cn('border-l-2 border-border pl-3 text-muted-foreground', className)} {...props} />,
          code: ({ className, ...props }) => <code className={cn('rounded bg-muted px-1 py-0.5 font-mono text-xs', className)} {...props} />,
          pre: ({ className, ...props }) => <pre className={cn('overflow-x-auto whitespace-pre-wrap break-words rounded-lg border bg-muted/40 p-3 font-mono text-xs leading-5', className)} {...props} />,
          table: ({ className, ...props }) => <div className="overflow-x-auto"><table className={cn('w-full border-collapse text-sm', className)} {...props} /></div>,
          th: ({ className, ...props }) => <th className={cn('border bg-muted/40 px-2 py-1 text-left font-semibold', className)} {...props} />,
          td: ({ className, ...props }) => <td className={cn('border px-2 py-1 align-top', className)} {...props} />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
