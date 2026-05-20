import { useCallback, useEffect, useRef, useState } from 'react'
import { TooltipProvider } from '@/components/ui/tooltip'
import { Wrench, FolderGit2 } from 'lucide-react'
import { Header } from './components/Header'
import { SummaryCards, type SummaryState } from './components/SummaryCards'
import { EnvironmentCard } from './components/EnvironmentCard'
import { RepoCard } from './components/RepoCard'
import { CommandCard } from './components/CommandCard'
import { ProjectCard } from './components/ProjectCard'
import { ProjectList } from './components/ProjectList'
import { LogPanel } from './components/LogPanel'
import { api } from './api'
import type {
  ActiveTab,
  EnvironmentItem,
  LogEntry,
  LogLevel,
  OperationLogEntry,
  OperationReport,
  PlatformInfo,
  ProjectStatus,
  RepoStatus,
  Status,
  ToolCommandStatus,
} from './types'

const LAST_TAB_KEY = 'trellis-manager:last-active-tab'

let logIdSeq = 0
function mkLog(level: LogLevel, text: string): LogEntry {
  return { id: String(++logIdSeq), level, text, ts: new Date().toISOString() }
}

function reportToLogs(report: OperationReport): LogEntry[] {
  const entries: LogEntry[] = []
  entries.push(mkLog(report.ok ? 'success' : 'error', report.message))
  for (const cmd of report.commands) {
    entries.push(mkLog('command', `$ ${cmd.command_line}`))
    if (cmd.stdout?.trim()) entries.push(mkLog('stdout', cmd.stdout.trim()))
    if (cmd.stderr?.trim()) entries.push(mkLog('stderr', cmd.stderr.trim()))
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
    if (cmd.stdout?.trim()) entries.push(mkLog('stdout', cmd.stdout.trim()))
    if (cmd.stderr?.trim()) entries.push(mkLog('stderr', cmd.stderr.trim()))
    if (cmd.error) entries.push(mkLog('error', cmd.error))
  }
  return entries
}

function getInitialTab(): ActiveTab {
  return window.localStorage.getItem(LAST_TAB_KEY) === 'toolchain' ? 'toolchain' : 'projects'
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

export default function App() {
  const [platformInfo, setPlatformInfo] = useState<PlatformInfo | null>(null)
  const [activeTab, setActiveTab] = useState<ActiveTab>(getInitialTab)

  // 环境检查
  const [envItems, setEnvItems] = useState<EnvironmentItem[]>([])
  const [envLoading, setEnvLoading] = useState(false)

  // 工具仓库
  const [repoPath, setRepoPath] = useState('')
  const [repoStatus, setRepoStatus] = useState<RepoStatus | null>(null)
  const [repoLoading, setRepoLoading] = useState(false)
  const [repoBusy, setRepoBusy] = useState(false)

  // 命令入口
  const [cmdItems, setCmdItems] = useState<ToolCommandStatus[]>([])
  const [cmdLoading, setCmdLoading] = useState(false)

  // 多项目状态
  const [projects, setProjects] = useState<string[]>([])
  const [selectedProject, setSelectedProject] = useState<string | null>(null)
  const [projectStatuses, setProjectStatuses] = useState<Record<string, ProjectStatus>>({})
  const [projectLoading, setProjectLoading] = useState(false)
  const [projectBusy, setProjectBusy] = useState(false)
  const [allowDirty, setAllowDirty] = useState(false)

  // 操作日志
  const [logEntries, setLogEntries] = useState<LogEntry[]>([])

  const addLogs = useCallback((...entries: LogEntry[]) => {
    setLogEntries((prev) => [...prev, ...entries])
  }, [])

  const addLog = useCallback((level: LogLevel, text: string) => {
    addLogs(mkLog(level, text))
  }, [addLogs])

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

  const handleTabChange = useCallback((tab: ActiveTab) => {
    setActiveTab(tab)
    window.localStorage.setItem(LAST_TAB_KEY, tab)
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
      addLog('success', `完成：添加业务项目 - ${status.status}：${status.message}`)
    } catch (err) {
      addLog('error', `失败：添加业务项目 - ${err}`)
    } finally {
      setProjectBusy(false)
    }
  }, [projects, addLog])

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
      await api.saveSelectedProject(nextSelected)
      if (nextSelected && !projectStatuses[nextSelected]) {
        await inspectProjectInner(nextSelected, true)
      }
      addLog('success', `完成：移除业务项目 - ${path}`)
    } catch (err) {
      addLog('error', `失败：移除业务项目 - ${err}`)
    } finally {
      setProjectBusy(false)
    }
  }, [projects, selectedProject, projectStatuses, addLog, inspectProjectInner])

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
    } catch (err) {
      addLog('error', `失败：初始化业务项目 - ${err}`)
    } finally {
      setProjectBusy(false)
    }
  }, [selectedProject, addLog, addLogs, inspectProjectInner])

  const handleUpdateProject = useCallback(async () => {
    if (!selectedProject) return

    if (selectedProjectStatus?.dirty && !allowDirty) {
      const confirmed = window.confirm('项目有未提交变更，继续执行 tl update --force？')
      if (!confirmed) return
    }

    setProjectBusy(true)
    addLog('task', '== 更新业务项目 ==')
    try {
      const report = await api.updateProject(selectedProject, allowDirty || (selectedProjectStatus?.dirty ?? false))
      addLogs(...reportToLogs(report))
      if (report.ok) {
        const diff = report.details?.diff_stat ?? report.details?.status ?? '无 git 变更摘要'
        addLog('info', `更新摘要：${diff}`)
      }
      await inspectProjectInner(selectedProject, true)
    } catch (err) {
      addLog('error', `失败：更新业务项目 - ${err}`)
    } finally {
      setProjectBusy(false)
    }
  }, [selectedProject, selectedProjectStatus, allowDirty, addLog, addLogs, inspectProjectInner])

  const handleOpenDir = useCallback(async () => {
    if (!selectedProject) return
    await api.openDirectory(selectedProject)
    addLog('info', `已请求打开目录：${selectedProject}`)
  }, [selectedProject, addLog])

  // ── 初始化 ──

  const initialized = useRef(false)

  useEffect(() => {
    if (initialized.current) return
    initialized.current = true

    void (async () => {
      try {
        const [pi, cfg, logs] = await Promise.all([
          api.getPlatformInfo(),
          api.getConfig(),
          api.getLogs(),
        ])

        setPlatformInfo(pi)
        setRepoPath(cfg.trellis_repo)

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

        // 启动后立即刷新工具链和已保存项目状态。
        checkEnvironmentInner()
        checkRepoInner(cfg.trellis_repo)
        checkCommandsInner()
        if (initialProjects.length > 0) {
          inspectProjectsInner(initialProjects)
        }
      } catch (err) {
        addLog('error', `初始化失败：${err}`)
      }
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── 日志操作 ──

  const handleCopyLogs = useCallback(() => {
    const text = logEntries
      .map((e) => {
        const style = { task: '[任务]', success: '[成功]', error: '[失败]', command: '[命令]', info: '[信息]', stdout: '', stderr: '' }
        const prefix = style[e.level] ?? ''
        return prefix ? `${prefix} ${e.text}` : e.text
      })
      .join('\n')
    navigator.clipboard.writeText(text)
  }, [logEntries])

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
        />

        <SummaryCards state={summaryState} showProject={activeTab === 'projects'} />

        {activeTab === 'toolchain' ? (
          <div className="mx-auto flex w-full max-w-5xl flex-col gap-5">
            <div className="flex flex-col gap-1 px-1">
              <h2 className="text-base font-bold tracking-tight text-foreground flex items-center gap-2 select-none">
                <Wrench className="size-4 text-blue-500" />
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
              onCreateWrappers={handleCreateWrappers}
              onPathChange={setRepoPath}
            />

            <CommandCard
              items={cmdItems}
              loading={cmdLoading}
              onRefresh={checkCommandsInner}
            />
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-[18rem_minmax(0,1fr)] gap-6 items-start my-1">
            <ProjectList
              projects={projects}
              selectedProject={selectedProject}
              statuses={projectStatuses}
              busy={projectBusy}
              onAdd={handleAddProject}
              onSelect={handleSelectProject}
              onRemove={handleRemoveProject}
            />

            <div className="flex flex-col gap-5">
              <div className="flex flex-col gap-1 px-1">
                <h2 className="text-base font-bold tracking-tight text-foreground flex items-center gap-2 select-none">
                  <FolderGit2 className="size-4 text-emerald-500" />
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
                onAllowDirtyChange={setAllowDirty}
              />
            </div>
          </div>
        )}

        <LogPanel
          entries={logEntries}
          onCopy={handleCopyLogs}
          onClear={handleClearLogs}
        />
      </div>
    </TooltipProvider>
  )
}
