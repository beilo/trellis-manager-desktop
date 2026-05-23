export type Status = 'ok' | 'warning' | 'error' | 'unknown' | 'info'

export type TrellisTaskStatus =
  | 'planning'
  | 'in_progress'
  | 'completed'
  | 'done'
  | 'unknown'

export interface TrellisTaskItem {
  dir_name: string
  path: string
  title: string
  status: TrellisTaskStatus
  raw_status: string
  assignee: string | null
  priority: string | null
  created_at: string | null
  completed_at: string | null
  parent: string | null
  children: string[]
  child_done: number
  child_total: number
  branch: string | null
  base_branch: string | null
  has_prd: boolean
  has_design: boolean
  has_implement: boolean
  archived: boolean
  archive_month: string | null
  error: string | null
}

/** 归档任务按月份分组 */
export interface ArchiveMonthGroup {
  month: string
  tasks: TrellisTaskItem[]
  error_count: number
}

export interface TrellisTaskSnapshot {
  project_path: string
  has_trellis: boolean
  tasks_dir: string | null
  tasks: TrellisTaskItem[]
  counts: Record<string, number>
  errors: string[]
  archived_groups: ArchiveMonthGroup[]
  archive_counts: Record<string, number>
}

export interface ProjectTasksBlock {
  project_path: string
  project_name: string
  has_trellis: boolean
  counts: Record<string, number>
  tasks: TrellisTaskItem[]
}

export interface AllTasksSnapshot {
  projects: ProjectTasksBlock[]
  total_counts: Record<string, number>
  project_count: number
}

export interface EnvironmentItem {
  name: string
  ok: boolean
  status: Status
  message: string
  version: string | null
}

export interface RepoStatus {
  path: string
  exists: boolean
  is_git: boolean
  is_trellis_repo: boolean
  dirty: boolean
  branch: string | null
  origin: string | null
  version: string | null
  ahead: number | null
  behind: number | null
  status: Status
  message: string
}

export interface ProjectStatus {
  path: string | null
  exists: boolean
  is_git: boolean
  has_trellis: boolean
  dirty: boolean
  status: Status
  message: string
  trellis_version: string | null
  latest_version: string | null
  version_outdated: boolean
}

export interface CommandResult {
  command: string[]
  command_line: string
  cwd: string | null
  returncode: number | null
  stdout: string
  stderr: string
  duration_ms: number
  error: string | null
}

export interface ToolCommandStatus {
  name: string
  path: string
  exists: boolean
  executable: boolean
  version_ok: boolean
  help_ok: boolean
  status: Status
  message: string
  commands: CommandResult[]
}

export interface OperationReport {
  title: string
  ok: boolean
  message: string
  commands: CommandResult[]
  details: Record<string, string>
}

export interface ManagerConfig {
  trellis_repo: string
  projects: string[]
  last_selected_project: string | null
  recent_projects: string[]
}

export type ActiveTab = 'toolchain' | 'projects' | 'kanban'

export interface AppState {
  activeTab: ActiveTab
  projects: string[]
  selectedProject: string | null
  projectStatuses: Record<string, ProjectStatus>
}

export interface PlatformInfo {
  is_macos: boolean
  python_version: string
}

export type LogLevel = 'task' | 'success' | 'error' | 'command' | 'stdout' | 'stderr' | 'info'

export interface LogEntry {
  id: string
  level: LogLevel
  text: string
  ts: string
}

export interface OperationLogEntry {
  title: string
  ok: boolean
  message: string
  created_at: string
  commands?: CommandResult[]
  details?: Record<string, string>
}
