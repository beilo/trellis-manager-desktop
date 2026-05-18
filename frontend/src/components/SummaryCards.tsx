import { Card, CardContent } from '@/components/ui/card'
import { StatusBadge } from './StatusBadge'
import type { Status } from '@/types'

interface SummaryCardProps {
  title: string
  value: string
  status: Status
  badgeLabel?: string
}

function SummaryCard({ title, value, status, badgeLabel }: SummaryCardProps) {
  return (
    <Card className="flex-1 min-w-0 cursor-default transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md hover:ring-foreground/15">
      <CardContent className="flex items-center justify-between gap-4 px-5 py-4">
        <div className="flex flex-col gap-1 min-w-0">
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide truncate">
            {title}
          </span>
          <span className="text-2xl font-extrabold tracking-tight text-foreground truncate">
            {value}
          </span>
        </div>
        <StatusBadge status={status} label={badgeLabel} />
      </CardContent>
    </Card>
  )
}

export interface SummaryState {
  envValue: string
  envStatus: Status
  repoValue: string
  repoStatus: Status
  commandValue: string
  commandStatus: Status
  projectValue: string
  projectStatus: Status
}

export function SummaryCards({ state }: { state: SummaryState }) {
  return (
    <div className="flex gap-3">
      <SummaryCard title="环境" value={state.envValue} status={state.envStatus} />
      <SummaryCard title="工具仓库" value={state.repoValue} status={state.repoStatus} />
      <SummaryCard title="命令入口" value={state.commandValue} status={state.commandStatus} />
      <SummaryCard title="业务项目" value={state.projectValue} status={state.projectStatus} />
    </div>
  )
}
