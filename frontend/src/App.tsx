import { useCallback, useEffect, useRef, useState } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { TooltipProvider } from '@/components/ui/tooltip'
import { Wrench, FolderGit2 } from 'lucide-react'
import { Header } from './components/Header'
import { SummaryCards, type SummaryState } from './components/SummaryCards'
import { EnvironmentCard } from './components/EnvironmentCard'
import { RepoCard } from './components/RepoCard'
import { CommandCard } from './components/CommandCard'
import { ProjectCard } from './components/ProjectCard'
import { LogPanel } from './components/LogPanel'
import { api } from './api'
import type {
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

export default function App() {
  const [platformInfo, setPlatformInfo] = useState<PlatformInfo | null>(null)
  const [recentProjects, setRecentProjects] = useState<string[]>([])

  // Environment
  const [envItems, setEnvItems] = useState<EnvironmentItem[]>([])
  const [envLoading, setEnvLoading] = useState(false)

  // Repo
  const [repoPath, setRepoPath] = useState('')
  const [repoStatus, setRepoStatus] = useState<RepoStatus | null>(null)
  const [repoLoading, setRepoLoading] = useState(false)
  const [repoBusy, setRepoBusy] = useState(false)

  // Commands
  const [cmdItems, setCmdItems] = useState<ToolCommandStatus[]>([])
  const [cmdLoading, setCmdLoading] = useState(false)

  // Project
  const [projectPath, setProjectPath] = useState('')
  const [projectStatus, setProjectStatus] = useState<ProjectStatus | null>(null)
  const [projectLoading, setProjectLoading] = useState(false)
  const [projectBusy, setProjectBusy] = useState(false)
  const [allowDirty, setAllowDirty] = useState(false)

  // Logs
  const [logEntries, setLogEntries] = useState<LogEntry[]>([])

  const addLogs = useCallback((...entries: LogEntry[]) => {
    setLogEntries((prev) => [...prev, ...entries])
  }, [])

  const addLog = useCallback((level: LogLevel, text: string) => {
    addLogs(mkLog(level, text))
  }, [addLogs])

  // ── Summary state ──

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
    if (!projectStatus?.path) return { value: '未选择', status: 'unknown' }
    return {
      value: projectStatus.has_trellis ? '已安装' : '待 Init',
      status: projectStatus.status,
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

  // ── Init ──

  const initialized = useRef(false)

  useEffect(() => {
    if (initialized.current) return
    initialized.current = true

    void (async () => {
      try {
        const [pi, cfg, logs, recent] = await Promise.all([
          api.getPlatformInfo(),
          api.getConfig(),
          api.getLogs(),
          api.getRecentProjects(),
        ])

        setPlatformInfo(pi)
        setRepoPath(cfg.trellis_repo)
        setRecentProjects(recent)

        if (!pi.is_macos) {
          addLog('info', '当前客户端第一版只支持 macOS。')
        }

        if (logs.length) {
          addLog('info', '== 最近操作记录 ==')
          addLogs(...logs.slice(0, 20).flatMap(operationLogToEntries))
        }

        // Initial checks
        checkEnvironmentInner()
        checkRepoInner(cfg.trellis_repo)
        checkCommandsInner()
      } catch (err) {
        addLog('error', `初始化失败：${err}`)
      }
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Environment ──

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

  // ── Repo ──

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
  }, [repoPath, addLog, addLogs])

  // ── Commands ──

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

  // ── Project ──

  const handleBrowse = useCallback(async () => {
    const selected = await api.selectDirectory()
    if (!selected) return
    setProjectPath(selected)
    handleCheckProject(selected)
  }, [])

  const handleCheckProject = useCallback(async (path?: string) => {
    const p = path ?? projectPath
    if (!p) return
    setProjectLoading(true)
    addLog('task', '== 检查业务项目 ==')
    try {
      const status = await api.inspectProject(p)
      setProjectStatus(status)
      addLog('success', `完成：检查业务项目 - ${status.status}：${status.message}`)
      if (status.path) {
        await api.rememberProject(status.path)
        const recent = await api.getRecentProjects()
        setRecentProjects(recent)
      }
    } catch (err) {
      addLog('error', `失败：检查业务项目 - ${err}`)
    } finally {
      setProjectLoading(false)
    }
  }, [projectPath, addLog])

  const handleInitProject = useCallback(async () => {
    if (!projectPath) return
    setProjectBusy(true)
    addLog('task', '== 初始化业务项目 ==')
    try {
      const report = await api.initProject(projectPath)
      addLogs(...reportToLogs(report))
      handleCheckProject(projectPath)
    } catch (err) {
      addLog('error', `失败：初始化业务项目 - ${err}`)
    } finally {
      setProjectBusy(false)
    }
  }, [projectPath, addLog, addLogs, handleCheckProject])

  const handleUpdateProject = useCallback(async () => {
    if (!projectPath) return

    if (projectStatus?.dirty && !allowDirty) {
      const confirmed = window.confirm('项目有未提交变更，继续执行 tl update --force？')
      if (!confirmed) return
    }

    setProjectBusy(true)
    addLog('task', '== 更新业务项目 ==')
    try {
      const report = await api.updateProject(projectPath, allowDirty || (projectStatus?.dirty ?? false))
      addLogs(...reportToLogs(report))
      if (report.ok) {
        const diff = report.details?.diff_stat ?? report.details?.status ?? '无 git 变更摘要'
        addLog('info', `更新摘要：${diff}`)
        setProjectStatus((prev) => prev ? { ...prev, status: 'ok' } : prev)
      } else {
        handleCheckProject(projectPath)
      }
    } catch (err) {
      addLog('error', `失败：更新业务项目 - ${err}`)
    } finally {
      setProjectBusy(false)
    }
  }, [projectPath, projectStatus, allowDirty, addLog, addLogs, handleCheckProject])

  const handleOpenDir = useCallback(async () => {
    if (!projectPath) return
    await api.openDirectory(projectPath)
    addLog('info', `已请求打开目录：${projectPath}`)
  }, [projectPath, addLog])

  // ── Log actions ──

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
      <div className="flex flex-col gap-5 px-6 py-8 min-h-screen bg-background">
        <Header platformInfo={platformInfo} readyStatus={readyStatus} />

        <SummaryCards state={summaryState} />

        <Tabs defaultValue="tools" className="flex flex-col gap-0">
          <TabsList
            variant="line"
            className="w-full h-auto rounded-none border-b justify-start gap-0 pb-0"
          >
            <TabsTrigger
              value="tools"
              className="h-auto gap-2 rounded-none px-5 pb-3 pt-1 text-sm font-semibold"
            >
              <Wrench className="size-4 shrink-0" />
              <span>工具链安装</span>
              <span className="hidden text-xs font-normal text-muted-foreground sm:inline">
                — 检查依赖、下载仓库、创建命令
              </span>
            </TabsTrigger>
            <TabsTrigger
              value="project"
              className="h-auto gap-2 rounded-none px-5 pb-3 pt-1 text-sm font-semibold"
            >
              <FolderGit2 className="size-4 shrink-0" />
              <span>业务项目</span>
              <span className="hidden text-xs font-normal text-muted-foreground sm:inline">
                — 对项目执行 Init / Update
              </span>
            </TabsTrigger>
          </TabsList>

          <TabsContent value="tools" className="flex flex-col gap-4 mt-5">
            <div className="flex gap-4">
              <EnvironmentCard
                items={envItems}
                loading={envLoading}
                onRefresh={checkEnvironmentInner}
              />
              <CommandCard
                items={cmdItems}
                loading={cmdLoading}
                onRefresh={checkCommandsInner}
              />
            </div>
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
          </TabsContent>

          <TabsContent value="project" className="mt-5">
            <ProjectCard
              projectPath={projectPath}
              status={projectStatus}
              loading={projectLoading}
              busy={projectBusy}
              allowDirty={allowDirty}
              recentProjects={recentProjects}
              onBrowse={handleBrowse}
              onCheck={() => handleCheckProject()}
              onInit={handleInitProject}
              onUpdate={handleUpdateProject}
              onOpenDir={handleOpenDir}
              onAllowDirtyChange={setAllowDirty}
              onPathChange={setProjectPath}
            />
          </TabsContent>
        </Tabs>

        <LogPanel
          entries={logEntries}
          onCopy={handleCopyLogs}
          onClear={handleClearLogs}
        />
      </div>
    </TooltipProvider>
  )
}
