import type {
  AllTasksSnapshot,
  EnvironmentItem,
  ManagerConfig,
  OperationReport,
  OperationLogEntry,
  PlatformInfo,
  ProjectStatus,
  ProjectTasksBlock,
  RepoStatus,
  ToolCommandStatus,
  TrellisTaskSnapshot,
} from './types'

declare global {
  interface Window {
    pywebview?: {
      api: PywebviewAPI
    }
  }
}

interface PywebviewAPI {
  get_config(): Promise<ManagerConfig>
  save_repo_path(path: string): Promise<void>
  get_projects(): Promise<string[]>
  save_projects(projects: string[], last_selected_project?: string | null): Promise<void>
  add_project(path: string): Promise<ProjectStatus>
  remove_project(path: string): Promise<void>
  save_selected_project(path: string | null): Promise<void>
  get_platform_info(): Promise<PlatformInfo>
  check_environment(): Promise<EnvironmentItem[]>
  check_helm_status(): Promise<EnvironmentItem>
  check_tool_repo(path: string): Promise<RepoStatus>
  check_wrapper_commands(): Promise<ToolCommandStatus[]>
  install_or_update_tool_repo(path: string): Promise<OperationReport>
  ensure_wrappers_and_path(path: string): Promise<OperationReport>
  inspect_project(path: string): Promise<ProjectStatus>
  init_project(path: string): Promise<OperationReport>
  update_project(path: string, allow_dirty: boolean): Promise<OperationReport>
  remember_project(path: string): Promise<void>
  get_recent_projects(): Promise<string[]>
  get_logs(): Promise<OperationLogEntry[]>
  select_directory(): Promise<string | null>
  open_directory(path: string): Promise<void>
  open_in_iterm(path: string): Promise<void>
  list_project_tasks(path: string, include_archive: boolean): Promise<TrellisTaskSnapshot>
  list_all_tasks?: () => Promise<AllTasksSnapshot>
  open_task_directory(task_path: string): Promise<void>
  push_task_to_helm(project_path: string, task_path: string): Promise<OperationReport>
}

function isPywebviewApiReady(candidate: PywebviewAPI | undefined): candidate is PywebviewAPI {
  return typeof candidate?.get_platform_info === 'function'
}

function waitForPywebview(): Promise<PywebviewAPI> {
  return new Promise((resolve, reject) => {
    const resolveWhenReady = () => {
      const candidate = window.pywebview?.api
      if (isPywebviewApiReady(candidate)) {
        resolve(candidate)
        return
      }
      reject(new Error(`pywebview API 未就绪：${Object.keys(candidate ?? {}).join(', ') || '空对象'}`))
    }

    if (isPywebviewApiReady(window.pywebview?.api)) {
      resolve(window.pywebview.api)
      return
    }
    window.addEventListener('pywebviewready', resolveWhenReady, { once: true })
  })
}

let _api: PywebviewAPI | null = null

async function getApi(): Promise<PywebviewAPI> {
  if (_api) return _api
  _api = await waitForPywebview()
  return _api
}

function emptyCounts(): Record<string, number> {
  return {
    planning: 0,
    in_progress: 0,
    completed: 0,
    done: 0,
    unknown: 0,
  }
}

function projectName(path: string): string {
  const normalized = path.replace(/[\\/]+$/, '')
  return normalized.split(/[\\/]/).pop() || normalized
}

async function listAllTasksCompat(bridge: PywebviewAPI): Promise<AllTasksSnapshot> {
  if (typeof bridge.list_all_tasks === 'function') {
    return bridge.list_all_tasks()
  }

  // 兼容正在运行的旧桌面后端：前端热更新后，新桥接方法不存在时复用旧接口聚合。
  const projectPaths = await bridge.get_projects()
  const totalCounts = emptyCounts()
  const projects: ProjectTasksBlock[] = await Promise.all(
    projectPaths.map(async (path) => {
      const snapshot = await bridge.list_project_tasks(path, false)
      for (const [status, count] of Object.entries(snapshot.counts)) {
        totalCounts[status] = (totalCounts[status] ?? 0) + count
      }
      return {
        project_path: snapshot.project_path,
        project_name: projectName(snapshot.project_path),
        has_trellis: snapshot.has_trellis,
        counts: snapshot.counts,
        tasks: snapshot.tasks,
      }
    }),
  )

  return {
    projects,
    total_counts: totalCounts,
    project_count: projects.length,
  }
}

export const api = {
  async getConfig(): Promise<ManagerConfig> {
    return (await getApi()).get_config()
  },

  async saveRepoPath(path: string): Promise<void> {
    return (await getApi()).save_repo_path(path)
  },

  async getProjects(): Promise<string[]> {
    return (await getApi()).get_projects()
  },

  async saveProjects(projects: string[], lastSelectedProject?: string | null): Promise<void> {
    return (await getApi()).save_projects(projects, lastSelectedProject ?? null)
  },

  async addProject(path: string): Promise<ProjectStatus> {
    return (await getApi()).add_project(path)
  },

  async removeProject(path: string): Promise<void> {
    return (await getApi()).remove_project(path)
  },

  async saveSelectedProject(path: string | null): Promise<void> {
    return (await getApi()).save_selected_project(path)
  },

  async getPlatformInfo(): Promise<PlatformInfo> {
    return (await getApi()).get_platform_info()
  },

  async checkEnvironment(): Promise<EnvironmentItem[]> {
    return (await getApi()).check_environment()
  },

  async checkHelmStatus(): Promise<EnvironmentItem> {
    return (await getApi()).check_helm_status()
  },

  async checkToolRepo(path: string): Promise<RepoStatus> {
    return (await getApi()).check_tool_repo(path)
  },

  async checkWrapperCommands(): Promise<ToolCommandStatus[]> {
    return (await getApi()).check_wrapper_commands()
  },

  async installOrUpdateToolRepo(path: string): Promise<OperationReport> {
    return (await getApi()).install_or_update_tool_repo(path)
  },

  async ensureWrappersAndPath(path: string): Promise<OperationReport> {
    return (await getApi()).ensure_wrappers_and_path(path)
  },

  async inspectProject(path: string): Promise<ProjectStatus> {
    return (await getApi()).inspect_project(path)
  },

  async initProject(path: string): Promise<OperationReport> {
    return (await getApi()).init_project(path)
  },

  async updateProject(path: string, allowDirty: boolean): Promise<OperationReport> {
    return (await getApi()).update_project(path, allowDirty)
  },

  async rememberProject(path: string): Promise<void> {
    return (await getApi()).remember_project(path)
  },

  async getRecentProjects(): Promise<string[]> {
    return (await getApi()).get_recent_projects()
  },

  async getLogs(): Promise<OperationLogEntry[]> {
    return (await getApi()).get_logs()
  },

  async selectDirectory(): Promise<string | null> {
    return (await getApi()).select_directory()
  },

  async openDirectory(path: string): Promise<void> {
    return (await getApi()).open_directory(path)
  },

  async openInIterm(path: string): Promise<void> {
    return (await getApi()).open_in_iterm(path)
  },

  async listProjectTasks(
    path: string,
    includeArchive: boolean = false
  ): Promise<TrellisTaskSnapshot> {
    return (await getApi()).list_project_tasks(path, includeArchive)
  },

  async listAllTasks(): Promise<AllTasksSnapshot> {
    return listAllTasksCompat(await getApi())
  },

  async openTaskDirectory(taskPath: string): Promise<void> {
    return (await getApi()).open_task_directory(taskPath)
  },

  async pushTaskToHelm(projectPath: string, taskPath: string): Promise<OperationReport> {
    return (await getApi()).push_task_to_helm(projectPath, taskPath)
  },
}
