// Microsoft Fabric KQL analytics + anomaly reporting

const FABRIC_ENDPOINT = process.env.NEXT_PUBLIC_FABRIC_ENDPOINT ?? ''
const FABRIC_TOKEN    = process.env.NEXT_PUBLIC_FABRIC_TOKEN    ?? ''

// ── Types ─────────────────────────────────────────────────
export interface AnomalyReport {
  droneId:   string
  metric:    'battery' | 'signal' | 'ai_conf'
  value:     number
  zScore:    number
  detectedAt:string
}

export interface KqlResult<T> { tables: { rows: T[] }[] }

// ── Core fetch wrapper ────────────────────────────────────
async function kqlQuery<T>(query: string): Promise<T[]> {
  const res = await fetch(FABRIC_ENDPOINT, {
    method:  'POST',
    headers: {
      'Authorization': `Bearer ${FABRIC_TOKEN}`,
      'Content-Type':  'application/json',
    },
    body: JSON.stringify({ query }),
  })
  if (!res.ok) throw new Error(`Fabric KQL error ${res.status}`)
  const data: KqlResult<T> = await res.json()
  return data.tables[0]?.rows ?? []
}

// ── Public API ────────────────────────────────────────────

/** Fetch anomalies detected in the last N minutes */
export async function fetchAnomalies(windowMin = 5): Promise<AnomalyReport[]> {
  return kqlQuery<AnomalyReport>(`
    SwarmTelemetry
    | where TimeGenerated > ago(${windowMin}m)
    | summarize avg_battery = avg(battery),
               stdev_bat   = stdev(battery) by droneId
    | where abs(avg_battery - 65) > 2 * stdev_bat
    | project droneId, metric="battery", value=avg_battery
  `)
}

/** Poll anomalies every interval ms; call cb with each batch */
export function subscribeAnomalies(
  cb:         (reports: AnomalyReport[]) => void,
  intervalMs= 30_000,
) {
  const id = setInterval(async () => {
    try { cb(await fetchAnomalies()) }
    catch (e) { console.warn('Fabric poll error', e) }
  }, intervalMs)
  return () => clearInterval(id)
}

/** One-shot: pull last 50 KQL analytics rows for the dashboard */
export async function fetchAnalyticsSummary() {
  return kqlQuery(`
    SwarmTelemetry
    | summarize
        avg_battery = avg(battery),
        avg_signal  = avg(signal),
        avg_ai_conf = avg(ai_conf),
        events      = count()
      by bin(TimeGenerated, 1m)
    | order by TimeGenerated desc
    | take 50
  `)
}