import axios from 'axios'

// Base URL từ Vite env (fallback http://localhost:8001/api/v1 khi chạy vite dev ngoài docker).
export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1',
  timeout: 30000,
})
