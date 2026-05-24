import { ArrowUpRight, Loader2, RefreshCw, Rows3 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'

interface BatchUpdateCardProps {
  outdatedCount: number
  loading: boolean
  onRefresh: () => void
  onOpen: () => void
}

export function BatchUpdateCard({ outdatedCount, loading, onRefresh, onOpen }: BatchUpdateCardProps) {
  const hasOutdated = outdatedCount > 0

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-4 pb-3">
        <div className="flex items-center gap-3">
          <Rows3 className="size-4 text-cyan-500" />
          <div className="flex flex-col gap-0.5">
            <span className="text-base font-bold text-foreground">批量 Update</span>
            <span className="text-xs text-muted-foreground">
              {loading ? '正在检查过期项目…' : hasOutdated ? `${outdatedCount} 个项目待更新` : '暂无版本过期项目'}
            </span>
          </div>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={onRefresh} disabled={loading}>
          {loading ? <Loader2 className="size-3 animate-spin" data-icon="inline-start" /> : <RefreshCw className="size-3" data-icon="inline-start" />}
          刷新
        </Button>
      </CardHeader>
      <CardContent className="flex flex-wrap items-center justify-between gap-3 pt-0">
        <span className="text-sm text-muted-foreground">
          打开对话框后选择项目，dirty 项目默认跳过，允许 dirty 后才会真实更新。
        </span>
        <Button type="button" onClick={onOpen} disabled={loading || !hasOutdated}>
          <ArrowUpRight className="size-3" data-icon="inline-start" />
          更新 {outdatedCount} 个过期项目
        </Button>
      </CardContent>
    </Card>
  )
}
