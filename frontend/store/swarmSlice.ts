import { createSlice, configureStore, PayloadAction } from '@reduxjs/toolkit'
import type { DroneData, MissionState } from '@/types/swarm'

const initialDrones: DroneData[] = Array.from({ length: 20 }, (_, index) => ({
  id:        `DR-${String(index + 1).padStart(2, '0')}`,
  x:         0,
  y:         0,
  altitude:  50,
  heading:   0,
  battery:   100,
  signal:    100,
  ai_conf:   100,
  alert:     false,
  lat:       -1.2921,
  lon:       36.8219,
  history:   [],
}))

const initialMission: MissionState = {
  formation: 'V-WING',
  mode:      'SEARCH',
}

export interface SwarmState {
  drones:  DroneData[]
  mission: MissionState
}

const initialState: SwarmState = {
  drones:  initialDrones,
  mission: initialMission,
}

const slice = createSlice({
  name: 'swarm',
  initialState,
  reducers: {
    updateDrones(state, action: PayloadAction<DroneData[]>) {
      state.drones = action.payload
    },
    updateMission(state, action: PayloadAction<Partial<MissionState>>) {
      state.mission = { ...state.mission, ...action.payload }
    },
    setFormation(state, action: PayloadAction<string>) {
      state.mission.formation = action.payload
      state.mission.lastInsight = {
        level: 'info',
        msg:   `Formation updated to ${action.payload}`,
      }
    },
    issueCommand(state, action: PayloadAction<string>) {
      state.mission.lastInsight = {
        level: 'info',
        msg:   `Command issued: ${action.payload}`,
      }
    },
  },
})

export const {
  updateDrones,
  updateMission,
  setFormation,
  issueCommand,
} = slice.actions

export const store = configureStore({
  reducer: { swarm: slice.reducer },
})

export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch

export const selectDrones = (state: RootState) => state.swarm.drones
export const selectMission = (state: RootState) => state.swarm.mission

export default slice.reducer
