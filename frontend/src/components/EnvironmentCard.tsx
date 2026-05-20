import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { StatusBadge } from './StatusBadge'
import { StepBadge, type StepStatus } from './StepBadge'
import type { EnvironmentItem } from '@/types'

interface EnvironmentCardProps {
  items: EnvironmentItem[]
  loading: boolean
  onRefresh: () => void
}

export function EnvironmentCard({ items, loading, onRefresh }: EnvironmentCardProps) {
  let stepStatus: StepStatus = 'idle'
  if (loading) {
    stepStatus = 'loading'
  } else if (items.length > 0) {
    const hasError = items.some((i) => i.status === 'error')
    const hasWarning = items.some((i) => i.status === 'warning')
    stepStatus = hasError ? 'error' : hasWarning ? 'warning' : 'ok'
  }

  return (
    <Card className="premium-card">
      <CardHeader className="flex flex-row items-start justify-between gap-4 pb-3">
        <div className="flex items-center gap-3">
          <StepBadge step={1} status={stepStatus} />
          <div className="flex flex-col gap-0.5">
            <span className="text-base font-bold text-foreground select-none">环境检查</span>
            <span className="text-xs text-muted-foreground select-none">系统核心依赖项检测。</span>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={onRefresh}
          disabled={loading}
          className="shrink-0"
        >
          {loading && <Loader2 className="size-3 animate-spin" data-icon="inline-start" />}
          {loading ? '检查中…' : '重新检查'}
        </Button>
      </CardHeader>

      <CardContent className="pt-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-28">命令</TableHead>
              <TableHead className="w-28">状态</TableHead>
              <TableHead>版本 / 信息</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={3} className="text-center text-muted-foreground py-6">
                  尚未检查
                </TableCell>
              </TableRow>
            ) : (
              items.map((item) => (
                <TableRow key={item.name}>
                  <TableCell className="font-mono font-semibold">{item.name}</TableCell>
                  <TableCell>
                    <StatusBadge status={item.status} />
                  </TableCell>
                  <TableCell
                    className="text-sm text-muted-foreground truncate max-w-0"
                    title={item.version ?? item.message}
                  >
                    {item.version ?? item.message}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}
