import http from './http'

export interface WeatherPreheatResponse {
  status: 'hit' | 'refreshed' | 'no_address' | 'error'
  weather: string | null
}

export const weatherApi = {
  preheat: async (): Promise<WeatherPreheatResponse> => {
    const res = await http.post('/weather/preheat')
    return res.data
  },
}
