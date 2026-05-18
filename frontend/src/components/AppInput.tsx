import { cn } from '@/lib/utils'
import type { InputHTMLAttributes } from 'react'

type AppInputProps = InputHTMLAttributes<HTMLInputElement>

export function AppInput({ className, ...props }: AppInputProps) {
  return (
    <input
      className={cn(
        'w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono',
        'transition-all duration-150',
        'placeholder:text-muted-foreground/60',
        'hover:border-foreground/30',
        'focus:outline-none focus:border-ring focus:ring-3 focus:ring-ring/20',
        'disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    />
  )
}
