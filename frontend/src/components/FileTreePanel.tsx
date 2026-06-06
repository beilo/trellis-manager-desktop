import { ChevronDown, ChevronRight, FileText, Folder } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { isPreviewableFile } from './fileTreeUtils'
import type { FileTreeItem } from '@/types'

interface FileTreePanelProps {
  items: FileTreeItem[]
  selectedPath: string | null
  onSelect: (item: FileTreeItem) => void
}

function FileTreeNode({
  item,
  level,
  selectedPath,
  onSelect,
}: {
  item: FileTreeItem
  level: number
  selectedPath: string | null
  onSelect: (item: FileTreeItem) => void
}) {
  const [open, setOpen] = useState(level < 1)
  const selected = selectedPath === item.path
  const children = item.children ?? []
  const isDirectory = item.type === 'directory'

  return (
    <div>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className={cn(
          'h-8 w-full justify-start gap-1 overflow-hidden px-2 text-left font-normal',
          selected && 'bg-accent text-foreground hover:bg-accent',
          !isDirectory && !isPreviewableFile(item) && 'text-muted-foreground',
        )}
        style={{ paddingLeft: `${level * 12 + 8}px` }}
        onClick={() => {
          if (isDirectory) {
            setOpen((value) => !value)
            return
          }
          if (isPreviewableFile(item)) onSelect(item)
        }}
        title={item.path}
      >
        {isDirectory ? (
          open ? <ChevronDown className="size-3 shrink-0" /> : <ChevronRight className="size-3 shrink-0" />
        ) : (
          <span className="w-3 shrink-0" />
        )}
        {isDirectory ? <Folder className="size-3 shrink-0" /> : <FileText className="size-3 shrink-0" />}
        <span className="truncate">{item.name}</span>
      </Button>
      {isDirectory && open && children.length > 0 && (
        <div>
          {children.map((child) => (
            <FileTreeNode
              key={child.path}
              item={child}
              level={level + 1}
              selectedPath={selectedPath}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export function FileTreePanel({ items, selectedPath, onSelect }: FileTreePanelProps) {
  if (items.length === 0) {
    return (
      <div className="rounded-lg border bg-muted/20 px-3 py-6 text-center text-sm text-muted-foreground">
        暂无可浏览文件
      </div>
    )
  }

  return (
    <div className="rounded-lg border bg-background p-1">
      {items.map((item) => (
        <FileTreeNode
          key={item.path}
          item={item}
          level={0}
          selectedPath={selectedPath}
          onSelect={onSelect}
        />
      ))}
    </div>
  )
}
