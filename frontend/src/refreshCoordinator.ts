import { useEffect, useRef } from 'react'

const DEBOUNCE_MS = 300

export type TrellisFileChangeType = 'tasks' | 'version'

export interface TrellisFileChangeEvent {
  type: TrellisFileChangeType
  projectPath: string
}

export type RefreshScope = 'tasks' | 'project' | 'kanban'

export interface RefreshNotification {
  event: TrellisFileChangeEvent
}

type RefreshCallback = (notification: RefreshNotification) => void

const subscribers: Record<RefreshScope, Set<RefreshCallback>> = {
  tasks: new Set<RefreshCallback>(),
  project: new Set<RefreshCallback>(),
  kanban: new Set<RefreshCallback>(),
}

const pendingEvents = new Map<string, TrellisFileChangeEvent>()
let debounceTimer: ReturnType<typeof window.setTimeout> | null = null
let installed = false

declare global {
  interface Window {
    onTrellisFileChange?: (event: TrellisFileChangeEvent) => void
  }
}

function isValidFileChangeEvent(event: unknown): event is TrellisFileChangeEvent {
  if (!event || typeof event !== 'object') return false

  const candidate = event as Partial<TrellisFileChangeEvent>
  const validType = candidate.type === 'tasks' || candidate.type === 'version'
  const validProjectPath = typeof candidate.projectPath === 'string' && candidate.projectPath.trim().length > 0

  return validType && validProjectPath
}

function getEventKey(event: TrellisFileChangeEvent): string {
  return `${event.type}\0${event.projectPath}`
}

function getScopesForEvent(event: TrellisFileChangeEvent): RefreshScope[] {
  if (event.type === 'tasks') return ['tasks', 'kanban']
  return ['project']
}

function notifySubscribers(event: TrellisFileChangeEvent): void {
  const notification: RefreshNotification = { event }
  for (const scope of getScopesForEvent(event)) {
    for (const callback of subscribers[scope]) {
      callback(notification)
    }
  }
}

function flushPendingEvents(): void {
  debounceTimer = null
  const events = Array.from(pendingEvents.values())
  pendingEvents.clear()

  for (const event of events) {
    notifySubscribers(event)
  }
}

function scheduleFlush(): void {
  if (debounceTimer !== null) {
    window.clearTimeout(debounceTimer)
  }
  debounceTimer = window.setTimeout(flushPendingEvents, DEBOUNCE_MS)
}

export function installRefreshCoordinator(): void {
  if (installed) return
  installed = true

  window.onTrellisFileChange = (event: TrellisFileChangeEvent): void => {
    if (!isValidFileChangeEvent(event)) return
    pendingEvents.set(getEventKey(event), event)
    scheduleFlush()
  }
}

export function subscribeRefresh(
  scope: RefreshScope,
  callback: RefreshCallback,
): () => void {
  subscribers[scope].add(callback)

  return (): void => {
    subscribers[scope].delete(callback)
  }
}

export function useRefreshSubscription(
  scope: RefreshScope,
  callback: RefreshCallback,
): void {
  const callbackRef = useRef(callback)

  useEffect(() => {
    callbackRef.current = callback
  }, [callback])

  useEffect(() => {
    const unsubscribe = subscribeRefresh(scope, (notification): void => {
      callbackRef.current(notification)
    })

    return unsubscribe
  }, [scope])
}
