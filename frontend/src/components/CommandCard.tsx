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
import type { ToolCommandStatus } from '@/types'

interface CommandCardProps {
  items: ToolCommandStatus[]
  loading: boolean
  onRefresh: () => void
}

export function CommandCard({ items, loading, onRefresh }: CommandCardProps) {
  return (
    <Card className="flex-1 min-w-0 transition-all duration-200 hover:ring-foreground/15">
      <CardHeader className="flex flex-row items-start justify-between gap-4 pb-3">
        <div className="flex items-center gap-3">
          <div className={`flex size-9 items-center justify-center rounded-full bg-blue-50 text-sm font-extrabold text-blue-600 shrink-0 transition-all duration-300 ${loading ? 'animate-pulse ring-2 ring-blue-300/60' : ''}`}>
            3
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="text-base font-bold text-foreground">命令入口</span>
            <span className="text-xs text-muted-foreground">wrapper 指向本地工具仓库，不依赖 npm link。</span>
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
              <TableHead className="w-24">命令</TableHead>
              <TableHead>路径</TableHead>
              <TableHead className="w-16 text-center">可执行</TableHead>
              <TableHead className="w-14 text-center">版本</TableHead>
              <TableHead className="w-14 text-center">帮助</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-muted-foreground py-6">
                  尚未检查
                </TableCell>
              </TableRow>
            ) : (
              items.map((item) => (
                <TableRow key={item.name}>
                  <TableCell>
                    <StatusBadge status={item.status} label={item.name} />
                  </TableCell>
                  <TableCell
                    className="text-xs font-mono text-muted-foreground truncate max-w-0"
                    title={item.path}
                  >
                    {item.path}
                  </TableCell>
                  <TableCell className="text-center text-sm">
                    {item.executable ? '是' : '否'}
                  </TableCell>
                  <TableCell className="text-center text-sm">
                    {item.version_ok ? '是' : '否'}
                  </TableCell>
                  <TableCell className="text-center text-sm">
                    {item.help_ok ? '是' : '否'}
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
