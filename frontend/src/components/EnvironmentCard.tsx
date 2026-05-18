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
import type { EnvironmentItem } from '@/types'

interface EnvironmentCardProps {
  items: EnvironmentItem[]
  loading: boolean
  onRefresh: () => void
}

export function EnvironmentCard({ items, loading, onRefresh }: EnvironmentCardProps) {
  return (
    <Card className="flex-1 min-w-0 transition-all duration-200 hover:ring-foreground/15">
      <CardHeader className="flex flex-row items-start justify-between gap-4 pb-3">
        <div className="flex items-center gap-3">
          <div className={`flex size-9 items-center justify-center rounded-full bg-blue-50 text-sm font-extrabold text-blue-600 shrink-0 transition-all duration-300 ${loading ? 'animate-pulse ring-2 ring-blue-300/60' : ''}`}>
            1
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="text-base font-bold text-foreground">环境检查</span>
            <span className="text-xs text-muted-foreground">只检查系统依赖，不自动安装。</span>
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
