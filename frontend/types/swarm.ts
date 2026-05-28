export interface DroneData {
  id:       string
  x:        number
  y:        number
  altitude: number
  heading:  number
  battery:  number
  signal:   number
  ai_conf:  number
  alert:    boolean
  lat:      number
  lon:      number
  history?: Array<{ battery: number; signal: number; ai_conf: number }>
}

export interface MissionInsight {
  level: 'info' | 'warn' | 'alert'
  msg:   string
}

export interface MissionState {
  formation:   string
  mode:        string
  lastInsight?: MissionInsight
}
