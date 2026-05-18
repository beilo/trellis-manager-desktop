export type Status = 'ok' | 'warning' | 'error' | 'unknown'

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
  recent_projects: string[]
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
