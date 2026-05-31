import { useCallback, useEffect, useState } from 'react'
import { Loader2, RotateCcw, Save, Settings, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { AppInput } from './AppInput'
import { api } from '@/api'
import type { ManagerSettings } from '@/types'

const DEFAULT_SETTINGS: ManagerSettings = {
  // 前端重置默认值要与后端 config.py 保持一致，避免加载失败时写回旧仓库源。
  official_repo_url: 'https://github.com/beilo/Trellis.git',
  accelerated_repo_url: 'https://xget.xi-xu.me/gh/beilo/Trellis.git',
  distribution_branch: 'custom/beilo-v0.5-rc',
  developer_name: '',
  init_platforms: [],
}

// 平台候选（key 与后端 VALID_INIT_PLATFORMS 对齐）
const PLATFORM_OPTIONS: readonly { key: string; label: string }[] = [
  { key: 'claude-code', label: 'Claude Code' },
  { key: 'codex', label: 'Codex' },
  { key: 'cursor', label: 'Cursor' },
]

interface SettingsCardProps {
  repoPath: string
  onSaved?: () => void
  onClose?: () => void
}

function validateSettings(settings: ManagerSettings): string | null {
  if (!settings.official_repo_url.trim()) return '官方仓库 URL 不能为空。'
  if (!settings.accelerated_repo_url.trim()) return '加速镜像 URL 不能为空。'
  if (!settings.distribution_branch.trim()) return '分发分支不能为空。'
  for (const [label, value] of [
    ['官方仓库 URL', settings.official_repo_url],
    ['加速镜像 URL', settings.accelerated_repo_url],
  ] as const) {
    if (!/^https?:\/\/.+/.test(value.trim())) return `${label} 必须是 http(s) URL。`
  }
  if (!settings.developer_name.trim()) return '开发者名不能为空。'
  if (settings.init_platforms.length === 0) return '请至少选择一个初始化平台。'
  return null
}

function togglePlatform(current: string[], key: string): string[] {
  return current.includes(key) ? current.filter((k) => k !== key) : [...current, key]
}

export function SettingsCard({ repoPath, onSaved, onClose }: SettingsCardProps) {
  const [settings, setSettings] = useState<ManagerSettings>(DEFAULT_SETTINGS)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [feedback, setFeedback] = useState<{ ok: boolean; message: string } | null>(null)

  const loadSettings = useCallback(async () => {
    setLoading(true)
    setFeedback(null)
    try {
      setSettings(await api.getSettings())
    } catch (err) {
      setFeedback({ ok: false, message: `设置加载失败：${err}` })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void Promise.resolve().then(loadSettings)
  }, [loadSettings])

  const save = async (next: ManagerSettings) => {
    const error = validateSettings(next)
    if (error) {
      setFeedback({ ok: false, message: error })
      return
    }
    setSaving(true)
    setFeedback(null)
    try {
      await api.saveSettings(next)
      setSettings(next)
      setFeedback({ ok: true, message: '设置已保存，下一次检查/下载工具仓库时生效。' })
      onSaved?.()
    } catch (err) {
      setFeedback({ ok: false, message: `保存设置失败：${err}` })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-4 pb-3">
        <div className="flex items-center gap-3">
          <Settings className="size-4 text-sky-500" />
          <div className="flex flex-col gap-0.5">
            <span className="text-base font-bold text-foreground">工具链设置</span>
            <span className="text-xs text-muted-foreground">修改 URL / 分支不会自动触发 clone、update 或 build。</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={loadSettings} disabled={loading || saving}>
            {loading && <Loader2 className="size-3 animate-spin" data-icon="inline-start" />}
            刷新
          </Button>
          {onClose && (
            <Button variant="ghost" size="icon-sm" onClick={onClose} disabled={saving} title="关闭设置">
              <X className="size-3.5" />
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="grid gap-4 pt-0">
        <div className="grid gap-1.5">
          <span className="text-xs font-medium text-muted-foreground">工具仓库路径</span>
          <div className="rounded-lg border bg-muted/35 px-3 py-2 font-mono text-sm text-muted-foreground" title={repoPath}>
            {repoPath || '未设置'}
          </div>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="grid gap-1.5">
            <span className="text-xs font-medium text-muted-foreground">官方仓库 URL</span>
            <AppInput
              value={settings.official_repo_url}
              onChange={(event) => setSettings((current) => ({ ...current, official_repo_url: event.target.value }))}
            />
          </label>
          <label className="grid gap-1.5">
            <span className="text-xs font-medium text-muted-foreground">加速镜像 URL</span>
            <AppInput
              value={settings.accelerated_repo_url}
              onChange={(event) => setSettings((current) => ({ ...current, accelerated_repo_url: event.target.value }))}
            />
          </label>
        </div>
        <label className="grid gap-1.5">
          <span className="text-xs font-medium text-muted-foreground">分发分支</span>
          <AppInput
            value={settings.distribution_branch}
            onChange={(event) => setSettings((current) => ({ ...current, distribution_branch: event.target.value }))}
          />
        </label>

        <div className="h-px bg-border" />

        <label className="grid gap-1.5">
          <span className="text-xs font-medium text-muted-foreground">开发者名</span>
          <AppInput
            value={settings.developer_name}
            onChange={(event) => setSettings((current) => ({ ...current, developer_name: event.target.value }))}
            placeholder="输入开发者名，用于 tl init -u"
          />
        </label>
        <div className="grid gap-1.5">
          <span className="text-xs font-medium text-muted-foreground">初始化平台</span>
          <div className="flex flex-wrap gap-2">
            {PLATFORM_OPTIONS.map(({ key, label }) => {
              const selected = settings.init_platforms.includes(key)
              return (
                <Button
                  key={key}
                  type="button"
                  variant={selected ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setSettings((current) => ({ ...current, init_platforms: togglePlatform(current.init_platforms, key) }))}
                >
                  {label}
                </Button>
              )
            })}
          </div>
        </div>

        {feedback && (
          <div className={`rounded-lg border px-3 py-2 text-sm ${feedback.ok ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300' : 'border-destructive/30 bg-destructive/10 text-destructive'}`}>
            {feedback.message}
          </div>
        )}

        <div className="flex flex-wrap justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              if (window.confirm('恢复默认仓库 URL 和分发分支？')) {
                // 只重置 URL/分支，保留开发者名与平台选择，避免误清空前置配置被校验卡死。
                void save({ ...settings, official_repo_url: DEFAULT_SETTINGS.official_repo_url, accelerated_repo_url: DEFAULT_SETTINGS.accelerated_repo_url, distribution_branch: DEFAULT_SETTINGS.distribution_branch })
              }
            }}
            disabled={saving}
          >
            <RotateCcw className="size-3" data-icon="inline-start" />
            恢复默认
          </Button>
          <Button type="button" onClick={() => void save(settings)} disabled={saving}>
            {saving ? <Loader2 className="size-3 animate-spin" data-icon="inline-start" /> : <Save className="size-3" data-icon="inline-start" />}
            保存设置
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
