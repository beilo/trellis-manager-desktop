export type Status = 'ok' | 'warning' | 'error' | 'unknown' | 'info' | 'dirty'

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

export type ProjectTaskCounts = Record<string, Record<string, number>>

export interface EnvironmentItem {
  name: string
  ok: boolean
  status: Status
  message: string
  version: string | null
}

export type SourceType = 'git' | 'zip_snapshot' | 'embedded_zip_snapshot' | 'local_zip_snapshot' | 'remote_zip_snapshot' | 'invalid' | 'missing'

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
  source_type?: SourceType
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

export interface CommitEntry {
  short_hash: string
  date: string | null
  title: string
  oneline: string
}

export interface GitSummary {
  branch: string | null
  dirty: boolean
  dirty_files: string[]
  ahead: number | null
  behind: number | null
  recent_commits: CommitEntry[]
}

export interface UpdatePreview {
  ok: boolean
  message: string
  dry_run_output: string
  dirty_files_before: string[]
  trellis_version_before: string | null
  latest_version: string | null
  would_run_migrations: boolean
  requires_migrate: boolean
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
  mem_help_ok: boolean
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

export interface ManagerSettings {
  official_repo_url: string
  accelerated_repo_url: string
  distribution_branch: string
  developer_name: string
  init_platforms: string[]
}

export interface ManagerConfig extends ManagerSettings {
  trellis_repo: string
  projects: string[]
  last_selected_project: string | null
  recent_projects: string[]
}

export type TaskMonitorStatus =
  | 'executing'
  | 'waiting_worker'
  | 'waiting_result'
  | 'done'
  | 'blocked'
  | 'failed'
  | 'partial'
  | 'sent'
  | 'unknown'

export type TaskMonitorGroup = 'ongoing' | 'ended' | 'archived'

export interface TaskMonitorEvent {
  kind: string
  by: string
  text: string
  seq: number | null
  ts: string | null
}

export interface TaskMonitorItem {
  channel: string
  task_name: string
  project_name: string
  project_path: string
  task_path: string
  worker: string
  provider: string
  status: TaskMonitorStatus
  status_label: string
  group: TaskMonitorGroup
  sent_at: string | null
  completed_at: string | null
  updated_at: string
  archived_at: string | null
  archive_due_on: string | null
  archive_days_remaining: number | null
  event_summary: string
  record_conflict: boolean
  source_available: boolean
  channel_available: boolean
  errors: string[]
}

export interface TaskMonitorDetail extends TaskMonitorItem {
  source_path: string
  handoff_path: string | null
  recent_events: TaskMonitorEvent[]
}

export interface TaskMonitorPage<T extends TaskMonitorItem = TaskMonitorItem> {
  items: T[]
  total: number
  next_offset: number | null
}

export interface TaskMonitorSearchItem extends TaskMonitorItem {
  hit_source: string
  snippet: string
  rank: number
}

export interface TaskMonitorActionResult {
  ok: boolean
  message: string
}

export type ActiveTab = 'toolchain' | 'projects' | 'kanban' | 'monitor'

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
  results?: ProjectUpdateResult[]
}

export interface ProjectUpdateResult {
  path: string
  ok: boolean
  message: string
  report: OperationLogEntry | null
  skipped: boolean
  reason: string | null
}

export interface BatchUpdateReport {
  ok: boolean
  message: string
  results: ProjectUpdateResult[]
  total: number
  updated_count: number
  failed_count: number
  skipped_count: number
}

export interface FileReadError {
  code: string
  message: string
}

export type FileKind = 'file' | 'directory'

export interface FileTreeItem {
  path: string
  name: string
  type: FileKind
  size: number
  mtime: number
  children?: FileTreeItem[] | null
}

export interface FileTreeResult {
  ok: boolean
  root: string | null
  items: FileTreeItem[]
  error?: FileReadError | null
}

export interface TextFileResult {
  ok: boolean
  path: string | null
  content: string | null
  size: number | null
  truncated: boolean
  error?: FileReadError | null
}

export interface JsonlLineError {
  line: number
  message: string
}

export interface JsonlFileResult {
  ok: boolean
  path: string | null
  items: unknown[]
  offset: number
  limit: number
  next_offset: number | null
  errors: JsonlLineError[]
  error?: FileReadError | null
}

export type TaskDocumentKind = 'prd' | 'design' | 'implement'
