import type { FileTreeItem } from '@/types'

export function isPreviewableFile(item: FileTreeItem): boolean {
  return item.type === 'file' && (
    item.name.endsWith('.md') ||
    item.name.endsWith('.jsonl') ||
    item.name.endsWith('.txt')
  )
}

export function flattenPreviewableFiles(items: FileTreeItem[]): FileTreeItem[] {
  const files: FileTreeItem[] = []
  for (const item of items) {
    if (isPreviewableFile(item)) files.push(item)
    for (const child of item.children ?? []) {
      files.push(...flattenPreviewableFiles([child]))
    }
  }
  return files
}
