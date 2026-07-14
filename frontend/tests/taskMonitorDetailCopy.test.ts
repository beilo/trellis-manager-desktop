import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildTaskMonitorDetailCopyText,
  copyTaskMonitorDetailInfo,
} from '../src/taskMonitorDetailCopy.ts'
import type { TaskMonitorDetail } from '../src/types.ts'

function monitorDetail(overrides: Partial<TaskMonitorDetail> = {}): TaskMonitorDetail {
  return {
    channel: 'trellis-task-detail-copy-info-20260714',
    task_name: '任务详情复制基础信息',
    project_name: 'trellis-manager-desktop',
    project_path: '/workspace/trellis-manager-desktop',
    task_path: '/workspace/trellis-manager-desktop/.trellis/tasks/07-14-task-detail-copy-info',
    worker: 'worker-1',
    provider: 'codex',
    status: 'executing',
    status_label: '执行中',
    group: 'ongoing',
    sent_at: 'invalid-sent-at',
    completed_at: null,
    updated_at: 'invalid-updated-at',
    archived_at: null,
    archive_due_on: null,
    archive_days_remaining: null,
    event_summary: '不应复制的事件摘要',
    record_conflict: false,
    source_available: true,
    channel_available: true,
    errors: ['不应复制的错误'],
    source_path: '/workspace/run.json',
    handoff_path: '/workspace/handoff.md',
    recent_events: [{ kind: 'worker_message', by: 'worker-1', text: '不应复制的事件', seq: 1, ts: null }],
    ...overrides,
  }
}

test('buildTaskMonitorDetailCopyText returns exactly the seven displayed information rows', () => {
  assert.equal(
    buildTaskMonitorDetailCopyText(monitorDetail()),
    [
      'Channel：trellis-task-detail-copy-info-20260714',
      'Worker：worker-1 / codex',
      '项目：/workspace/trellis-manager-desktop',
      'Task：/workspace/trellis-manager-desktop/.trellis/tasks/07-14-task-detail-copy-info',
      '派发时间：invalid-sent-at',
      '最近更新：invalid-updated-at',
      'Handoff：/workspace/handoff.md',
    ].join('\n'),
  )
})

test('buildTaskMonitorDetailCopyText uses the displayed handoff fallback', () => {
  const text = buildTaskMonitorDetailCopyText(monitorDetail({ handoff_path: null }))

  assert.match(text, /Handoff：尚无$/)
})

test('copyTaskMonitorDetailInfo writes and returns the generated text', async () => {
  let copied = ''
  const text = await copyTaskMonitorDetailInfo(monitorDetail(), async (value) => {
    copied = value
  })

  assert.equal(copied, text)
})

test('copyTaskMonitorDetailInfo exposes clipboard rejection to the caller', async () => {
  await assert.rejects(
    copyTaskMonitorDetailInfo(monitorDetail(), async () => {
      throw new Error('clipboard denied')
    }),
    /clipboard denied/,
  )
})
