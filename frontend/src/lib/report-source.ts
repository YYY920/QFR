'use client'

import { useSyncExternalStore } from 'react'
import type { DataSource } from './link-data'

const STORAGE_KEY = 'qfr-report-source'
const CHANGE_EVENT = 'qfr-report-source-change'

export const DATA_SOURCE_LABELS: Record<DataSource, string> = {
  xero: 'Xero',
  quickbooks: 'QuickBooks',
}

function currentSource(): DataSource {
  if (typeof window === 'undefined') return 'quickbooks'
  return window.sessionStorage.getItem(STORAGE_KEY) === 'xero' ? 'xero' : 'quickbooks'
}

export function setStoredDataSource(source: DataSource) {
  if (typeof window === 'undefined') return
  window.sessionStorage.setItem(STORAGE_KEY, source)
  window.dispatchEvent(new Event(CHANGE_EVENT))
}

function subscribe(callback: () => void) {
  window.addEventListener(CHANGE_EVENT, callback)
  window.addEventListener('storage', callback)
  return () => {
    window.removeEventListener(CHANGE_EVENT, callback)
    window.removeEventListener('storage', callback)
  }
}

function serverSource(): DataSource {
  return 'quickbooks'
}

export function useReportSource(): [DataSource, (source: DataSource) => void] {
  const source = useSyncExternalStore(subscribe, currentSource, serverSource)
  return [source, setStoredDataSource]
}
