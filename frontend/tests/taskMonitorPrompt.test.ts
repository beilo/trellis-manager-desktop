import assert from 'node:assert/strict'
import test from 'node:test'

import { buildTaskCheckPrompt, copyTaskCheckPrompt } from '../src/taskMonitorPrompt.ts'
import type { TaskMonitorItem } from '../src/types.ts'

function monitorItem(overrides: Partial<TaskMonitorItem> = {}): TaskMonitorItem {
  return {
    channel: 'trellis-copy-20260714',
    task_name: '复制检查提示词',
    project_name: 'trellis-manager-desktop',
    project_path: '/workspace/trellis-manager-desktop',
    task_path: '/workspace/trellis-manager-desktop/.trellis/tasks/07-14-copy-task-check-prompt',
    worker: 'worker-1',
    provider: 'codex',
    status: 'waiting_result',
    status_label: '等待结果',
    group: 'ongoing',
    sent_at: '2026-07-14T08:00:00Z',
    completed_at: null,
    updated_at: '2026-07-14T09:00:00Z',
    archived_at: null,
    archive_due_on: null,
    archive_days_remaining: null,
    event_summary: '正在执行验证',
    record_conflict: false,
    source_available: true,
    channel_available: true,
    errors: [],
    ...overrides,
  }
}

test('buildTaskCheckPrompt includes every loaded ongoing task and diagnostic contract', () => {
  const prompt = buildTaskCheckPrompt([
    monitorItem(),
    monitorItem({
      channel: 'trellis-blocked-20260714',
      task_name: '阻塞任务',
      status: 'blocked',
      status_label: '已阻塞',
      event_summary: '',
      source_available: false,
      errors: ['handoff 解析失败'],
    }),
  ])

  assert.match(prompt, /下面 2 个当前页面已经加载的进行中 Trellis 任务/)
  assert.match(prompt, /项目绝对路径：\/workspace\/trellis-manager-desktop/)
  assert.match(prompt, /Trellis task 绝对路径：\/workspace\/trellis-manager-desktop\/\.trellis\/tasks\/07-14-copy-task-check-prompt/)
  assert.match(prompt, /Channel：trellis-copy-20260714/)
  assert.match(prompt, /Channel：trellis-blocked-20260714/)
  assert.match(prompt, /当前状态：blocked（已阻塞）/)
  assert.match(prompt, /最近消息摘要：无/)
  assert.match(prompt, /Run 来源可用：否/)
  assert.match(prompt, /当前解析或来源错误：handoff 解析失败/)
  assert.match(prompt, /全程只读。不得修改任何文件，不得提交代码/)
  assert.match(prompt, /分开报告“已 commit”“已 push”“已合并”/)
  assert.match(prompt, /没有证据时推断已经 push 或 merge/)
  assert.match(prompt, /相关未提交改动、建议下一步/)
})

test('copyTaskCheckPrompt writes the generated prompt and returns it', async () => {
  let copied = ''
  const prompt = await copyTaskCheckPrompt([monitorItem()], async (text) => {
    copied = text
  })

  assert.equal(copied, prompt)
  assert.match(copied, /任务 1：复制检查提示词/)
})

test('copyTaskCheckPrompt rejects empty lists before touching the clipboard', async () => {
  let called = false

  await assert.rejects(
    copyTaskCheckPrompt([], async () => {
      called = true
    }),
    /当前页面没有已加载的进行中任务/,
  )
  assert.equal(called, false)
})

test('copyTaskCheckPrompt exposes clipboard rejection to the caller', async () => {
  await assert.rejects(
    copyTaskCheckPrompt([monitorItem()], async () => {
      throw new Error('clipboard denied')
    }),
    /clipboard denied/,
  )
})
