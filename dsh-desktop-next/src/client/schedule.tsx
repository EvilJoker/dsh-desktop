/** Manage the official reminder stack through its optional upstream bundle. */
import { useEffect, useRef, useState } from 'react'
import type { Context } from '@deepseek-ai/cordis'
import type { BundleInfo } from '@deepseek-ai/dsh-api-remotes/client'
import { Switch, Toast, Button } from '@deepseek-ai/dsh-client-ui-primitives'

/** Upstream bundle that inserts the context, Host service and task UI together. */
export const SCHEDULE_BUNDLE = '@deepseek-ai/dsh-experimental-schedule-bundle'

export function ScheduleSettings({ context, zh }: { context: Context; zh: boolean }) {
  const t = (cn: string, en: string): string => zh ? cn : en
  const [revision, refresh] = useState(0)
  const [row, setRow] = useState<BundleInfo>()
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const pending = useRef(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  useEffect(() => {
    const reload = (): void => { refresh(value => value + 1) }
    const off = context.remote.$on('plugin-manager/changed', reload)
    const reset = context.on('connection/reset', reload)
    window.addEventListener('focus', reload)
    return () => { off(); reset(); window.removeEventListener('focus', reload) }
  }, [context])
  useEffect(() => {
    let disposed = false
    setLoading(true)
    void context.remote.pluginManager.listBundles().then(result => {
      if (disposed) return
      if (!result.ok) throw new Error(result.error.message)
      setRow(result.value.find(bundle => bundle.name === SCHEDULE_BUNDLE))
    }).catch(failure => { if (!disposed) { setRow(undefined); setError(String(failure)) } })
      .finally(() => { if (!disposed) setLoading(false) })
    return () => { disposed = true }
  }, [context, revision])
  const locked = loading || busy || !row || row.readOnlyReason !== undefined || row.error !== undefined
  const change = async (value: boolean): Promise<void> => {
    if (pending.current || locked) return
    pending.current = true
    setBusy(true); setError(''); setNotice('')
    try {
      const result = await context.remote.pluginManager.setBundleEnabled(SCHEDULE_BUNDLE, value)
      if (!result.ok) throw new Error(result.error.message)
      const outcome = result.value
      if (outcome.application === 'failed' || outcome.application === 'cancelled') {
        throw new Error(outcome.error?.diagnostic ?? t('无法更改定时任务状态。', 'Could not change scheduled tasks.'))
      }
      if (outcome.application === 'overridden') throw new Error(t('当前配置覆盖了此开关，请检查插件配置。', 'Another configuration overrides this switch. Check your plugin configuration.'))
      if (outcome.application === 'restart-required') setNotice(t('已保存，请重启后台服务以应用。', 'Saved. Restart the background service to apply.'))
    } catch (failure) { setError(failure instanceof Error ? failure.message : String(failure)) }
    finally { pending.current = false; setBusy(false); refresh(value => value + 1) }
  }
  return <div className="dshNextPluginDetail" data-next-schedule>
    <div className="dshNextPluginActions">
      <Switch label={t('启用定时任务', 'Enable scheduled tasks')} checked={row?.enabled ?? false} disabled={locked} onChange={value => { void change(value) }} />
    </div>
    {notice && <Toast text={notice} onDone={() => { setNotice('') }} />}
    {error && <Toast text={error} onDone={() => { setError('') }} />}
    {error && <Button variant="outline" size="sm" disabled={loading || busy} onClick={() => { refresh(value => value + 1) }}>{t('重试', 'Retry')}</Button>}
  </div>
}
