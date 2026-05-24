import { useEffect } from 'react'
import { SettingsCard } from './SettingsCard'

interface SettingsDialogProps {
  open: boolean
  repoPath: string
  onClose: () => void
  onSaved?: () => void
}

export function SettingsDialog({ open, repoPath, onClose, onSaved }: SettingsDialogProps) {
  useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-6 backdrop-blur-sm">
      <section
        role="dialog"
        aria-modal="true"
        aria-label="工具链设置"
        className="max-h-[88vh] w-full max-w-4xl overflow-auto rounded-2xl shadow-2xl"
      >
        <SettingsCard repoPath={repoPath} onSaved={onSaved} onClose={onClose} />
      </section>
    </div>
  )
}
