import type {
  EnvironmentItem,
  ManagerConfig,
  OperationReport,
  OperationLogEntry,
  PlatformInfo,
  ProjectStatus,
  RepoStatus,
  ToolCommandStatus,
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
}
