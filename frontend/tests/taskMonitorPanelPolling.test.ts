import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../src/components/TaskMonitorPanel.tsx', import.meta.url), 'utf8')

test('task monitor polls SQLite every five seconds without a backend callback', () => {
  assert.match(source, /setTimeout\(\(\) => void loadLists\(\), 0\)/)
  assert.match(source, /setInterval\([^]*5_000\)/)
  assert.doesNotMatch(source, /onTaskMonitorRefreshed/)
})

test('task monitor guards list overlap and invalidates stale detail requests', () => {
  assert.match(source, /listRequestInFlight\.current/)
  assert.match(source, /if \(pending\)/)
  assert.match(source, /loadLists\(true, true\)/)
  assert.match(source, /detailRequestSeq\.current \+= 1/)
  assert.match(source, /seq === detailRequestSeq\.current/)
})

test('task monitor does not render an automatic archive countdown', () => {
  assert.doesNotMatch(source, /自动归档还剩/)
})
