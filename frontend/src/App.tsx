import { useCallback, useEffect, useRef, useState } from 'react'
import { TooltipProvider } from '@/components/ui/tooltip'
import { FolderGit2, Wrench } from 'lucide-react'
import { Header } from './components/Header'
import { SummaryCards, type SummaryState } from './components/SummaryCards'
import { EnvironmentCard } from './components/EnvironmentCard'
import { RepoCard } from './components/RepoCard'
import { CommandCard } from './components/CommandCard'
import { ProjectCard } from './components/ProjectCard'
import { ProjectGitPanel } from './components/ProjectGitPanel'
import { ProjectList } from './components/ProjectList'
import { ProjectKnowledgeBrowser } from './components/ProjectKnowledgeBrowser'
import { LogPanel } from './components/LogPanel'
import { TaskManagerPanel } from './components/TaskManagerPanel'
import { KanbanPanel } from './components/KanbanPanel'
import { UpdatePreviewDialog } from './components/UpdatePreviewDialog'
import { BatchUpdateDialog } from './components/BatchUpdateDialog'
import { SettingsCard } from './components/SettingsCard'
import { SettingsDialog } from './components/SettingsDialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from './components/ui/tabs'
import { api } from './api'
import { installRefreshCoordinator, useRefreshSubscription } from './refreshCoordinator'
import type {
  ActiveTab,
  AllTasksSnapshot,
  EnvironmentItem,
  LogEntry,
  LogLevel,
  OperationLogEntry,
  OperationReport,
  PlatformInfo,
  ProjectStatus,
  ProjectTaskCounts,
  RepoStatus,
  Status,
  ToolCommandStatus,
  UpdatePreview,
} from './types'

const LAST_TAB_KEY = 'trellis-manager:last-active-tab'
type ProjectPane = 'tasks' | 'knowledge'

let logIdSeq = 0
function mkLog(level: LogLevel, text: string): LogEntry {
  return { id: String(++logIdSeq), level, text, ts: new Date().toISOString() }
}

function reportToLogs(report: OperationReport): LogEntry[] {
  const entries: LogEntry[] = []
  entries.push(mkLog(report.ok ? 'success' : 'error', report.message))
  for (const cmd of report.commands) {
    entries.push(mkLog('command', `$ ${cmd.command_line}`))
    // stdout/stderr 保留原始内容，不因为空白字符而丢弃，确保多行输出和首尾空格在日志中完整呈现。
    if (cmd.stdout !== undefined && cmd.stdout !== '') entries.push(mkLog('stdout', cmd.stdout))
    if (cmd.stderr !== undefined && cmd.stderr !== '') entries.push(mkLog('stderr', cmd.stderr))
    if (cmd.error) entries.push(mkLog('error', cmd.error))
  }
  return entries
}

function operationLogToEntries(entry: OperationLogEntry): LogEntry[] {
  const ok = entry.ok ? '成功' : '失败'
  const entries: LogEntry[] = [
    mkLog('info', `[${entry.created_at}] ${ok} ${entry.title} ${entry.message}`),
  ]
  for (const cmd of entry.commands ?? []) {
    entries.push(mkLog('command', `$ ${cmd.command_line ?? cmd.command?.join(' ')}`))
    // 保留原始 stdout/stderr，不 trim，确保空白行和多行格式在复制日志时不丢失。
    if (cmd.stdout !== undefined && cmd.stdout !== '') entries.push(mkLog('stdout', cmd.stdout))
    if (cmd.stderr !== undefined && cmd.stderr !== '') entries.push(mkLog('stderr', cmd.stderr))
    if (cmd.error) entries.push(mkLog('error', cmd.error))
  }
  return entries
}

function getInitialTab(): ActiveTab {
  const stored = window.localStorage.getItem(LAST_TAB_KEY)
  return stored === 'toolchain' || stored === 'projects' || stored === 'kanban'
    ? stored
    : 'projects'
}

function dedupeProjects(paths: string[]): string[] {
  const seen = new Set<string>()
  return paths.filter((path) => {
    const normalized = path.trim()
    if (!normalized || seen.has(normalized)) return false
    seen.add(normalized)
    return true
  })
}

function projectName(path: string): string {
  const normalized = path.replace(/[\\/]+$/, '')
  return normalized.split(/[\\/]/).pop() || normalized
}

function projectTaskCountsFromSnapshot(snapshot: AllTasksSnapshot): ProjectTaskCounts {
  return Object.fromEntries(
    snapshot.projects.map((project) => [project.project_path, project.counts]),
  )
}

export default function App() {
  const [platformInfo, setPlatformInfo] = useState<PlatformInfo | null>(null)
  const [activeTab, setActiveTab] = useState<ActiveTab>(getInitialTab)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [batchUpdateOpen, setBatchUpdateOpen] = useState(false)

  // 环境检查
  const [envItems, setEnvItems] = useState<EnvironmentItem[]>([])
  const [envLoading, setEnvLoading] = useState(false)

  // 工具仓库
  const [repoPath, setRepoPath] = useState('')
  const [repoStatus, setRepoStatus] = useState<RepoStatus | null>(null)
  const [repoLoading, setRepoLoading] = useState(false)
  const [repoBusy, setRepoBusy] = useState(false)
  const [githubBranchUrl, setGithubBranchUrl] = useState<string | null>(null)
  const [githubBranchZipUrl, setGithubBranchZipUrl] = useState<string | null>(null)

  // 命令入口
  const [cmdItems, setCmdItems] = useState<ToolCommandStatus[]>([])
  const [cmdLoading, setCmdLoading] = useState(false)

  // Cursor 入口状态独立检查，避免编辑器不可用影响项目检查流程。
  const [cursorStatus, setCursorStatus] = useState<EnvironmentItem | null>(null)
  const [cursorLoading, setCursorLoading] = useState(false)

  // 多项目状态
  const [projects, setProjects] = useState<string[]>([])
  const [selectedProject, setSelectedProject] = useState<string | null>(null)
  const [projectPane, setProjectPane] = useState<ProjectPane>('tasks')
  const [highlightTaskPath, setHighlightTaskPath] = useState<string | null>(null)
  const [projectStatuses, setProjectStatuses] = useState<Record<string, ProjectStatus>>({})
  // 过期项目列表由 App 统一缓存，保证工具链入口、项目入口和对话框使用同一份数据。
  const [outdatedProjects, setOutdatedProjects] = useState<ProjectStatus[]>([])
  const [outdatedLoading, setOutdatedLoading] = useState(false)
  const [projectTaskCounts, setProjectTaskCounts] = useState<ProjectTaskCounts>({})
  const [projectTaskCountsLoading, setProjectTaskCountsLoading] = useState(false)
  const [projectLoading, setProjectLoading] = useState(false)
  const [projectBusy, setProjectBusy] = useState(false)
  const [allowDirty, setAllowDirty] = useState(false)
  const [updatePreview, setUpdatePreview] = useState<UpdatePreview | null>(null)
  const [updatePreviewOpen, setUpdatePreviewOpen] = useState(false)
  const [updatePreviewBusy, setUpdatePreviewBusy] = useState(false)

  // 操作日志
  const [logEntries, setLogEntries] = useState<LogEntry[]>([])
  const [logAutoOpenEnabled, setLogAutoOpenEnabled] = useState(false)
  const [logOpenSignal, setLogOpenSignal] = useState(0)

  const addLogs = useCallback((...entries: LogEntry[]) => {
    setLogEntries((prev) => [...prev, ...entries])
  }, [])

  const addLog = useCallback((level: LogLevel, text: string) => {
    addLogs(mkLog(level, text))
  }, [addLogs])

  const requestOpenLogPanel = useCallback(() => {
    setLogOpenSignal((current) => current + 1)
  }, [])

  const loadOutdatedProjectsInner = useCallback(async () => {
    setOutdatedLoading(true)
    try {
      const result = await api.listOutdatedProjects()
      setOutdatedProjects(result)
    } catch (err) {
      addLog('error', `失败：刷新过期项目列表 - ${err}`)
    } finally {
      setOutdatedLoading(false)
    }
  }, [addLog])

  // ── 顶部状态摘要 ──

  const selectedProjectStatus = selectedProject ? projectStatuses[selectedProject] ?? null : null

  const getEnvSummary = (): { value: string; status: Status } => {
    if (!envItems.length) return { value: '未检查', status: 'unknown' }
    const ok = envItems.filter((i) => i.status === 'ok').length
    const err = envItems.filter((i) => i.status === 'error').length
    return {
      value: `${ok}/${envItems.length} 可用`,
      status: err > 0 ? 'error' : 'ok',
    }
  }

  const getRepoSummary = (): { value: string; status: Status } => {
    if (!repoStatus) return { value: '未检查', status: 'unknown' }
    return {
      value: repoStatus.version ?? (repoStatus.exists ? '已安装' : '未安装'),
      status: repoStatus.status,
    }
  }

  const getCmdSummary = (): { value: string; status: Status } => {
    if (!cmdItems.length) return { value: '未检查', status: 'unknown' }
    const ok = cmdItems.filter((i) => i.status === 'ok').length
    return {
      value: `${ok}/${cmdItems.length} 可用`,
      status: ok === cmdItems.length ? 'ok' : 'error',
    }
  }

  const getProjectSummary = (): { value: string; status: Status } => {
    if (!selectedProject) return { value: '未选择', status: 'unknown' }
    if (!selectedProjectStatus?.path) {
      return { value: projectName(selectedProject), status: 'unknown' }
    }
    return {
      value: projectName(selectedProjectStatus.path),
      status: selectedProjectStatus.status,
    }
  }

  const envSummary = getEnvSummary()
  const repoSummary = getRepoSummary()
  const cmdSummary = getCmdSummary()
  const projectSummary = getProjectSummary()

  const summaryState: SummaryState = {
    envValue: envSummary.value,
    envStatus: envSummary.status,
    repoValue: repoSummary.value,
    repoStatus: repoSummary.status,
    commandValue: cmdSummary.value,
    commandStatus: cmdSummary.status,
    projectValue: projectSummary.value,
    projectStatus: projectSummary.status,
  }

  const readyStatus: Status =
    envSummary.status === 'ok' ? 'ok' : envItems.length > 0 ? 'error' : 'unknown'

  // ── 环境检查 ──

  const checkEnvironmentInner = useCallback(async () => {
    setEnvLoading(true)
    addLog('task', '== 检查环境 ==')
    try {
      const items = await api.checkEnvironment()
      setEnvItems(items)
      const ok = items.filter((i) => i.status === 'ok').length
      const err = items.filter((i) => i.status === 'error').length
      addLog('success', `完成：检查环境 - ok ${ok} / error ${err}`)
    } catch (err) {
      addLog('error', `失败：检查环境 - ${err}`)
    } finally {
      setEnvLoading(false)
    }
  }, [addLog])

  // ── 工具仓库 ──

  const checkRepoInner = useCallback(async (path: string) => {
    setRepoLoading(true)
    addLog('task', '== 检查工具仓库 ==')
    try {
      const status = await api.checkToolRepo(path)
      setRepoStatus(status)
      addLog('success', `完成：检查工具仓库 - ${status.status}：${status.message}`)
    } catch (err) {
      addLog('error', `失败：检查工具仓库 - ${err}`)
    } finally {
      setRepoLoading(false)
    }
  }, [addLog])

  const handleCheckRepo = useCallback(async () => {
    await api.saveRepoPath(repoPath)
    checkRepoInner(repoPath)
  }, [repoPath, checkRepoInner])

  const handleInstallRepo = useCallback(async () => {
    setRepoBusy(true)
    addLog('task', '== 下载/更新并构建工具仓库 ==')
    try {
      await api.saveRepoPath(repoPath)
      const report = await api.installOrUpdateToolRepo(repoPath)
      addLogs(...reportToLogs(report))
      checkRepoInner(repoPath)
    } catch (err) {
      addLog('error', `失败：下载/更新 - ${err}`)
    } finally {
      setRepoBusy(false)
    }
  }, [repoPath, addLog, addLogs, checkRepoInner])

  const handleInstallFromZip = useCallback(async (zipPath: string, replace: boolean) => {
    setRepoBusy(true)
    addLog('task', replace ? '== 从本地 zip 重装工具仓库 ==' : '== 从本地 zip 安装工具仓库 ==')
    try {
      await api.saveRepoPath(repoPath)
      const report = await api.installFromZip(zipPath, repoPath, replace)
      addLogs(...reportToLogs(report))
      checkRepoInner(repoPath)
    } catch (err) {
      addLog('error', `失败：本地 zip 安装 - ${err}`)
    } finally {
      setRepoBusy(false)
    }
  }, [repoPath, addLog, addLogs, checkRepoInner])

  const handleInstallFromRemoteZip = useCallback(async (replace: boolean) => {
    setRepoBusy(true)
    addLog('task', replace ? '== 从远端 zip 重装工具仓库 ==' : '== 从远端 zip 安装工具仓库 ==')
    try {
      await api.saveRepoPath(repoPath)
      const report = await api.installFromRemoteZip(repoPath, replace)
      addLogs(...reportToLogs(report))
      checkRepoInner(repoPath)
    } catch (err) {
      addLog('error', `失败：远端 zip 安装 - ${err}`)
    } finally {
      setRepoBusy(false)
    }
  }, [repoPath, addLog, addLogs, checkRepoInner])

  // ── 命令入口 ──

  const checkCommandsInner = useCallback(async () => {
    setCmdLoading(true)
    addLog('task', '== 检查命令入口 ==')
    try {
      const items = await api.checkWrapperCommands()
      setCmdItems(items)
      const parts = items.map((i) => `${i.name} ${i.status === 'ok' ? '可用' : '不可用'}`)
      addLog('success', `完成：检查命令入口 - ${parts.join('；')}`)
      for (const item of items) {
        for (const cmd of item.commands) {
          addLog('command', `$ ${cmd.command_line}`)
          if (cmd.stdout?.trim()) addLog('stdout', cmd.stdout.trim())
          if (cmd.stderr?.trim()) addLog('stderr', cmd.stderr.trim())
        }
      }
    } catch (err) {
      addLog('error', `失败：检查命令入口 - ${err}`)
    } finally {
      setCmdLoading(false)
    }
  }, [addLog])

  const checkCursorInner = useCallback(async () => {
    setCursorLoading(true)
    addLog('task', '== 检查 Cursor 入口 ==')
    try {
      const status = await api.checkCursorStatus()
      setCursorStatus(status)
      addLog('success', `完成：检查 Cursor 入口 - ${status.ok ? '可用' : '不可用'}：${status.message}`)
    } catch (err) {
      const fallback: EnvironmentItem = {
        name: 'cursor',
        ok: false,
        status: 'error',
        message: `检查 Cursor 入口失败：${err}`,
        version: null,
      }
      setCursorStatus(fallback)
      addLog('error', fallback.message)
    } finally {
      setCursorLoading(false)
    }
  }, [addLog])

  const handleCreateWrappers = useCallback(async () => {
    setRepoBusy(true)
    addLog('task', '== 创建命令入口 ==')
    try {
      const report = await api.ensureWrappersAndPath(repoPath)
      addLogs(...reportToLogs(report))
      checkCommandsInner()
    } catch (err) {
      addLog('error', `失败：创建命令入口 - ${err}`)
    } finally {
      setRepoBusy(false)
    }
  }, [repoPath, addLog, addLogs, checkCommandsInner])

  // ── 项目管理 ──

  const inspectProjectInner = useCallback(async (path: string, silent = false) => {
    setProjectLoading(true)
    if (!silent) addLog('task', '== 检查业务项目 ==')
    try {
      const status = await api.inspectProject(path)
      setProjectStatuses((prev) => ({ ...prev, [path]: status }))
      if (!silent) {
        addLog('success', `完成：检查业务项目 - ${status.status}：${status.message}`)
      }
      return status
    } catch (err) {
      if (!silent) addLog('error', `失败：检查业务项目 - ${err}`)
      throw err
    } finally {
      setProjectLoading(false)
    }
  }, [addLog])

  const inspectProjectsInner = useCallback(async (paths: string[]) => {
    setProjectLoading(true)
    try {
      const entries = await Promise.all(
        paths.map(async (path) => {
          try {
            return [path, await api.inspectProject(path)] as const
          } catch (err) {
            addLog('error', `失败：检查项目 ${path} - ${err}`)
            return null
          }
        }),
      )
      const next = Object.fromEntries(
        entries.filter((entry): entry is readonly [string, ProjectStatus] => entry !== null),
      )
      setProjectStatuses((prev) => ({ ...prev, ...next }))
    } finally {
      setProjectLoading(false)
    }
  }, [addLog])

  const refreshProjectTaskCounts = useCallback(async (knownProjects: string[] = projects) => {
    if (knownProjects.length === 0) {
      setProjectTaskCounts({})
      return
    }

    setProjectTaskCountsLoading(true)
    try {
      const snapshot = await api.listAllTasks()
      // 统一从跨项目快照生成左侧计数，避免列表和看板出现两套统计口径。
      setProjectTaskCounts(projectTaskCountsFromSnapshot(snapshot))
    } catch (err) {
      addLog('error', `刷新项目任务计数失败：${err}`)
    } finally {
      setProjectTaskCountsLoading(false)
    }
  }, [addLog, projects])

  useRefreshSubscription('project', ({ event }) => {
    if (event.type !== 'version') return
    if (!projects.includes(event.projectPath) && !projectStatuses[event.projectPath]) return

    void inspectProjectInner(event.projectPath, true).catch((err: unknown) => {
      addLog('error', `自动刷新项目状态失败：${err}`)
    })
  })

  useRefreshSubscription('tasks', ({ event }) => {
    if (event.type !== 'tasks') return
    if (!projects.includes(event.projectPath)) return

    void refreshProjectTaskCounts(projects)
  })

  const handleTabChange = useCallback((tab: ActiveTab) => {
    setActiveTab(tab)
    window.localStorage.setItem(LAST_TAB_KEY, tab)
  }, [])

  const handleOpenBatchUpdate = useCallback(() => {
    setBatchUpdateOpen(true)
  }, [])

  const handleOpenSettings = useCallback(() => {
    setSettingsOpen(true)
  }, [])

  const handleOpenHelp = useCallback(async () => {
    try {
      const helpUrl = await api.getHelpUrl()
      await api.openInBrowser(helpUrl)
      addLog('info', `已打开使用说明：${helpUrl}`)
    } catch (err) {
      addLog('error', `打开使用说明失败：${err}`)
    }
  }, [addLog])

  useEffect(() => {
    void Promise.resolve().then(loadOutdatedProjectsInner)
  }, [projects, loadOutdatedProjectsInner])

  const handleNavigateToTask = useCallback(async (projectPath: string, taskPath: string) => {
    // 看板点击后复用项目 Tab 的 TaskDetail，避免在看板内重复实现任务操作。
    setSelectedProject(projectPath)
    setProjectPane('tasks')
    setHighlightTaskPath(taskPath)
    handleTabChange('projects')
    await api.saveSelectedProject(projectPath)
    if (!projectStatuses[projectPath]) {
      await inspectProjectInner(projectPath, true)
    }
  }, [handleTabChange, inspectProjectInner, projectStatuses])

  const handleHighlightConsumed = useCallback(() => {
    setHighlightTaskPath(null)
  }, [])

  const handleCheckProject = useCallback(async (path?: string) => {
    const p = path ?? selectedProject
    if (!p) return
    await inspectProjectInner(p)
  }, [selectedProject, inspectProjectInner])

  const handleAddProject = useCallback(async () => {
    const selected = await api.selectDirectory()
    if (!selected) return

    setProjectBusy(true)
    addLog('task', '== 添加业务项目 ==')
    try {
      const status = await api.addProject(selected)
      const path = status.path ?? selected
      const nextProjects = dedupeProjects([...projects, path])
      setProjects(nextProjects)
      setSelectedProject(path)
      setProjectStatuses((prev) => ({ ...prev, [path]: status }))
      await api.saveSelectedProject(path)
      await refreshProjectTaskCounts(nextProjects)
      addLog('success', `完成：添加业务项目 - ${status.status}：${status.message}`)
    } catch (err) {
      addLog('error', `失败：添加业务项目 - ${err}`)
    } finally {
      setProjectBusy(false)
    }
  }, [projects, addLog, refreshProjectTaskCounts])

  const handleRemoveProject = useCallback(async (path: string) => {
    setProjectBusy(true)
    addLog('task', '== 移除业务项目 ==')
    try {
      await api.removeProject(path)
      const nextProjects = projects.filter((project) => project !== path)
      const nextSelected = selectedProject === path ? nextProjects[0] ?? null : selectedProject
      setProjects(nextProjects)
      setSelectedProject(nextSelected)
      setProjectStatuses((prev) => {
        const rest = { ...prev }
        delete rest[path]
        return rest
      })
      setProjectTaskCounts((prev) => {
        const rest = { ...prev }
        delete rest[path]
        return rest
      })
      await api.saveSelectedProject(nextSelected)
      if (nextSelected && !projectStatuses[nextSelected]) {
        await inspectProjectInner(nextSelected, true)
      }
      await refreshProjectTaskCounts(nextProjects)
      addLog('success', `完成：移除业务项目 - ${path}`)
    } catch (err) {
      addLog('error', `失败：移除业务项目 - ${err}`)
    } finally {
      setProjectBusy(false)
    }
  }, [projects, selectedProject, projectStatuses, addLog, inspectProjectInner, refreshProjectTaskCounts])

  const handleSelectProject = useCallback(async (path: string) => {
    setSelectedProject(path)
    await api.saveSelectedProject(path)
    if (!projectStatuses[path]) {
      await inspectProjectInner(path, true)
    }
  }, [projectStatuses, inspectProjectInner])

  const handleInitProject = useCallback(async () => {
    if (!selectedProject) return
    setProjectBusy(true)
    addLog('task', '== 初始化业务项目 ==')
    try {
      const report = await api.initProject(selectedProject)
      addLogs(...reportToLogs(report))
      await inspectProjectInner(selectedProject, true)
      await loadOutdatedProjectsInner()
    } catch (err) {
      addLog('error', `失败：初始化业务项目 - ${err}`)
    } finally {
      setProjectBusy(false)
    }
  }, [selectedProject, addLog, addLogs, inspectProjectInner, loadOutdatedProjectsInner])

  const handleUpdateProject = useCallback(async () => {
    if (!selectedProject) return

    setProjectBusy(true)
    addLog('task', '== 预览业务项目 Update ==')
    try {
      const preview = await api.previewProjectUpdate(selectedProject)
      setUpdatePreview(preview)
      setUpdatePreviewOpen(true)
      addLog(preview.ok ? 'info' : 'error', `Update 预览：${preview.message}`)
    } catch (err) {
      addLog('error', `失败：预览业务项目 Update - ${err}`)
    } finally {
      setProjectBusy(false)
    }
  }, [selectedProject, addLog])

  const handleCancelUpdatePreview = useCallback(() => {
    if (updatePreviewBusy) return
    setUpdatePreviewOpen(false)
  }, [updatePreviewBusy])

  const handleConfirmUpdatePreview = useCallback(async (confirmedAllowDirty: boolean, confirmedMigrate: boolean) => {
    if (!selectedProject) return

    setUpdatePreviewBusy(true)
    setProjectBusy(true)
    addLog('task', confirmedMigrate ? '== 迁移更新业务项目 ==' : '== 更新业务项目 ==')
    try {
      const report = await api.updateProject(selectedProject, confirmedAllowDirty, confirmedMigrate)
      addLogs(...reportToLogs(report))
      if (report.ok) {
        const diff = report.details?.diff_stat ?? report.details?.status ?? '无 git 变更摘要'
        addLog('info', `更新摘要：${diff}`)
      }
      setUpdatePreviewOpen(false)
      setUpdatePreview(null)
      await inspectProjectInner(selectedProject, true)
      await loadOutdatedProjectsInner()
    } catch (err) {
      addLog('error', `失败：更新业务项目 - ${err}`)
    } finally {
      setUpdatePreviewBusy(false)
      setProjectBusy(false)
    }
  }, [selectedProject, addLog, addLogs, inspectProjectInner, loadOutdatedProjectsInner])

  const handleOpenDir = useCallback(async () => {
    if (!selectedProject) return
    await api.openDirectory(selectedProject)
    addLog('info', `已请求打开目录：${selectedProject}`)
  }, [selectedProject, addLog])

  const handleOpenCursor = useCallback(async (path?: string) => {
    const target = path ?? selectedProject
    if (!target) return
    try {
      await api.openInCursor(target)
      addLog('info', `已请求在 Cursor 中打开：${target}`)
    } catch (err) {
      addLog('error', `在 Cursor 中打开失败：${err}`)
      throw err
    }
  }, [selectedProject, addLog])

  const handleBatchUpdateCompleted = useCallback(async () => {
    addLog('info', '批量 Update 已结束，正在刷新项目状态。')
    await inspectProjectsInner(projects)
    await loadOutdatedProjectsInner()
    await refreshProjectTaskCounts(projects)
    requestOpenLogPanel()
  }, [addLog, inspectProjectsInner, projects, loadOutdatedProjectsInner, refreshProjectTaskCounts, requestOpenLogPanel])

  // ── 初始化 ──

  const initialized = useRef(false)

  useEffect(() => {
    installRefreshCoordinator()
  }, [])

  useEffect(() => {
    if (initialized.current) return
    initialized.current = true

    void (async () => {
      try {
        const [pi, cfg, logs, branchUrl, branchZipUrl] = await Promise.all([
          api.getPlatformInfo(),
          api.getConfig(),
          api.getLogs(),
          api.getGithubBranchUrl().catch(() => null),
          api.getGithubBranchZipUrl().catch(() => null),
        ])

        setPlatformInfo(pi)
        setRepoPath(cfg.trellis_repo)
        setGithubBranchUrl(branchUrl)
        setGithubBranchZipUrl(branchZipUrl)

        const initialProjects = dedupeProjects(
          cfg.projects.length > 0 ? cfg.projects : cfg.recent_projects,
        )
        const selected = cfg.last_selected_project && initialProjects.includes(cfg.last_selected_project)
          ? cfg.last_selected_project
          : initialProjects[0] ?? null
        setProjects(initialProjects)
        setSelectedProject(selected)

        if (!pi.is_macos) {
          addLog('info', '当前客户端第一版只支持 macOS。')
        }

        if (logs.length) {
          addLog('info', '== 最近操作记录 ==')
          addLogs(...logs.slice(0, 20).flatMap(operationLogToEntries))
        }

        // 启动后台检查只更新摘要和日志数量，不主动弹开底部控制台遮挡首屏内容。
        const startupChecks = [
          checkEnvironmentInner(),
          checkRepoInner(cfg.trellis_repo),
          checkCommandsInner(),
          checkCursorInner(),
          initialProjects.length > 0 ? inspectProjectsInner(initialProjects) : Promise.resolve(),
          initialProjects.length > 0 ? refreshProjectTaskCounts(initialProjects) : Promise.resolve(),
        ]
        await Promise.allSettled(startupChecks)
        setLogAutoOpenEnabled(true)
      } catch (err) {
        addLog('error', `初始化失败：${err}`)
        setLogAutoOpenEnabled(true)
      }
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── 日志操作 ──

  // 把 LogEntry 数组序列化为带前缀的纯文本，供剪贴板使用。
  const serializeLogEntries = useCallback((entries: LogEntry[]): string => {
    return entries
      .map((e) => {
        const style = { task: '[任务]', success: '[成功]', error: '[失败]', command: '[命令]', info: '[信息]', stdout: '', stderr: '[stderr]' }
        const prefix = style[e.level] ?? ''
        return prefix ? `${prefix} ${e.text}` : e.text
      })
      .join('\n')
  }, [])

  const handleCopyLogs = useCallback(async () => {
    try {
      // 拉取全部持久化历史日志（旧后端兼容：接口不存在则返回空数组）。
      const allHistory = await api.getAllLogs()
      const historyEntries = allHistory.flatMap(operationLogToEntries)
      // 历史日志按时间正序排列（文件内是倒序），当前会话日志接在后面。
      const combined = [...historyEntries, ...logEntries]
      const text = serializeLogEntries(combined)
      await navigator.clipboard.writeText(text)
    } catch (err) {
      // 复制失败时提示用户，避免静默吞掉异常。
      addLog('error', `复制日志失败：${err}`)
    }
  }, [logEntries, serializeLogEntries, addLog])

  const handleClearLogs = useCallback(() => {
    setLogEntries([])
  }, [])

  return (
    <TooltipProvider>
      <div className="flex flex-col gap-5 px-6 pt-6 pb-20 min-h-screen bg-background">
        <Header
          platformInfo={platformInfo}
          readyStatus={readyStatus}
          activeTab={activeTab}
          onTabChange={handleTabChange}
          onOpenHelp={handleOpenHelp}
          onOpenSettings={handleOpenSettings}
        />

        {activeTab === 'toolchain' && <SummaryCards state={summaryState} showProject={false} />}

        {activeTab === 'toolchain' ? (
          <div className="mx-auto flex w-full max-w-5xl flex-col gap-5">
            <div className="flex flex-col gap-1 px-1">
              <h2 className="text-lg font-serif font-normal tracking-tight text-foreground flex items-center gap-2 select-none">
                <Wrench className="size-4 text-primary" />
                <span>工具链基石</span>
              </h2>
              <p className="text-xs text-muted-foreground select-none">
                搭建本机的 Trellis 工具链，创建全局命令。
              </p>
            </div>

            <EnvironmentCard
              items={envItems}
              loading={envLoading}
              onRefresh={checkEnvironmentInner}
            />

            <RepoCard
              repoPath={repoPath}
              status={repoStatus}
              loading={repoLoading}
              busy={repoBusy}
              onCheck={handleCheckRepo}
              onInstall={handleInstallRepo}
              onInstallFromZip={handleInstallFromZip}
              onInstallFromRemoteZip={handleInstallFromRemoteZip}
              onCreateWrappers={handleCreateWrappers}
              onPathChange={setRepoPath}
              githubBranchUrl={githubBranchUrl}
              githubBranchZipUrl={githubBranchZipUrl}
            />

            <SettingsCard
              repoPath={repoPath}
              onSaved={() => {
                addLog('info', '工具链设置已更新。')
              }}
            />

            <CommandCard
              items={cmdItems}
              loading={cmdLoading}
              onRefresh={checkCommandsInner}
            />
          </div>
        ) : activeTab === 'projects' ? (
          <div className="grid grid-cols-1 lg:grid-cols-[18rem_minmax(0,1fr)] gap-6 items-start my-1">
            <ProjectList
              projects={projects}
              selectedProject={selectedProject}
              statuses={projectStatuses}
              taskCounts={projectTaskCounts}
              taskCountsLoading={projectTaskCountsLoading}
              busy={projectBusy}
              batchUpdateCount={outdatedProjects.length}
              batchUpdateLoading={outdatedLoading}
              onAdd={handleAddProject}
              onOpenBatchUpdate={handleOpenBatchUpdate}
              onSelect={handleSelectProject}
              onRemove={handleRemoveProject}
            />

            <div className="flex flex-col gap-5">
              <div className="flex flex-col gap-1 px-1">
                <h2 className="text-lg font-serif font-normal tracking-tight text-foreground flex items-center gap-2 select-none">
                  <FolderGit2 className="size-4 text-primary" />
                  <span>业务项目中心</span>
                </h2>
                <p className="text-xs text-muted-foreground select-none">
                  选择本地 Git 项目，一键执行 Trellis 的 Init 与 Update。
                </p>
              </div>

              <ProjectCard
                projectPath={selectedProject}
                status={selectedProjectStatus}
                loading={projectLoading}
                busy={projectBusy}
                allowDirty={allowDirty}
                onCheck={() => handleCheckProject()}
                onInit={handleInitProject}
                onUpdate={handleUpdateProject}
                onOpenDir={handleOpenDir}
                onOpenCursor={handleOpenCursor}
                cursorStatus={cursorStatus}
                cursorLoading={cursorLoading}
                onAllowDirtyChange={setAllowDirty}
              />

              <ProjectGitPanel projectPath={selectedProject} projectStatus={selectedProjectStatus} />

              <Tabs value={projectPane} onValueChange={(value) => setProjectPane(value as ProjectPane)}>
                <TabsList className="w-fit">
                  <TabsTrigger value="tasks">任务</TabsTrigger>
                  <TabsTrigger value="knowledge">知识库</TabsTrigger>
                </TabsList>
                <TabsContent value="tasks">
                  <TaskManagerPanel
                    projectPath={selectedProject}
                    projectStatus={selectedProjectStatus}
                    highlightTaskPath={highlightTaskPath}
                    highlightedTaskInitialTab="detail"
                    cursorStatus={cursorStatus}
                    cursorLoading={cursorLoading}
                    onOpenCursor={handleOpenCursor}
                    onHighlightConsumed={handleHighlightConsumed}
                  />
                </TabsContent>
                <TabsContent value="knowledge">
                  <ProjectKnowledgeBrowser projectPath={selectedProject} projectStatus={selectedProjectStatus} />
                </TabsContent>
              </Tabs>
            </div>
          </div>
        ) : (
          <KanbanPanel onNavigateToTask={handleNavigateToTask} />
        )}

        <LogPanel
          entries={logEntries}
          autoOpen={logAutoOpenEnabled}
          openSignal={logOpenSignal}
          onCopy={handleCopyLogs}
          onClear={handleClearLogs}
        />

        <BatchUpdateDialog
          open={batchUpdateOpen}
          projects={outdatedProjects}
          loading={outdatedLoading}
          onClose={() => setBatchUpdateOpen(false)}
          onRefresh={loadOutdatedProjectsInner}
          onCompleted={handleBatchUpdateCompleted}
          onOpenLog={requestOpenLogPanel}
        />

        <SettingsDialog
          open={settingsOpen}
          repoPath={repoPath}
          onClose={() => setSettingsOpen(false)}
          onSaved={() => {
            addLog('info', '工具链设置已更新。')
          }}
        />

        {updatePreviewOpen && selectedProject && updatePreview && (
          <UpdatePreviewDialog
            projectPath={selectedProject}
            preview={updatePreview}
            allowDirty={allowDirty}
            confirming={updatePreviewBusy}
            onCancel={handleCancelUpdatePreview}
            onConfirm={handleConfirmUpdatePreview}
          />
        )}
      </div>
    </TooltipProvider>
  )
}
