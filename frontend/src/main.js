
/**
 * Application entry point.
 *
 * Axios configuration
 * -------------------
 * baseURL — reads VITE_API_URL; falls back to localhost:8000 for development.
 *
 * withCredentials — enables cookies to be sent with API requests, including
 * the HttpOnly refresh cookie used by the refresh and logout endpoints.
 *
 * X-CSRFToken — reads the 'csrftoken' cookie and attaches it to non-safe
 * HTTP requests. Refresh and logout enforce CSRF validation through
 * CsrfEnforcedNoAuth on the backend.
 *
 * @ensure_csrf_cookie on signup/login sets the CSRF cookie but does not
 * itself validate incoming CSRF tokens.
 *
 * Token attachment
 * ----------------
 * The request interceptor attaches the access token from Pinia memory
 * to ordinary authenticated API requests.
 *
 * 401 retry / refresh
 * -------------------
 * The response interceptor attempts a refresh after eligible 401 responses,
 * retries the original request at most once, and redirects to login if
 * refreshing fails. Refresh and logout requests are excluded from retry.
 */

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import axios from 'axios'

import './assets/main.css'

// ---------------------------------------------------------------------------
// Base URL and cookie configuration
// ---------------------------------------------------------------------------
axios.defaults.baseURL =
  import.meta.env.VITE_API_URL || 'http://localhost:8000'

axios.defaults.withCredentials = true

// ---------------------------------------------------------------------------
// Helper: read a cookie by name.
// Returns an empty string when the cookie is absent.
// ---------------------------------------------------------------------------
function getCookie(name) {
  const match = document.cookie.match(
    new RegExp('(?:^|; )' + name + '=([^;]*)')
  )

  return match ? decodeURIComponent(match[1]) : ''
}

// ---------------------------------------------------------------------------
// Request interceptor
// 1. Attach the access token from Pinia memory.
// 2. Attach X-CSRFToken for non-safe HTTP methods.
// ---------------------------------------------------------------------------
axios.interceptors.request.use(async config => {
  const safeMethods = ['get', 'head', 'options', 'trace']
  const method = (config.method || 'get').toLowerCase()

  // Attach the current in-memory access token.
  // Do not attach it to login, signup, or refresh requests.
  const isAuthEndpoint =
    config.url?.includes('/api/login/') ||
    config.url?.includes('/api/signup/') ||
    config.url?.includes('/api/refresh/')

  if (!isAuthEndpoint) {
    const { useUserStore } = await import('@/stores/user')
    const userStore = useUserStore()

    if (userStore.user.access) {
      config.headers = config.headers || {}
      config.headers.Authorization = `Bearer ${userStore.user.access}`
    }
  }

  // Attach CSRF token to non-safe HTTP requests.
  if (!safeMethods.includes(method)) {
    const csrfToken = getCookie('csrftoken')

    if (csrfToken) {
      config.headers = config.headers || {}
      config.headers['X-CSRFToken'] = csrfToken
    }
  }

  return config
})

// ---------------------------------------------------------------------------
// Response interceptor — handle eligible 401 responses with one refresh.
// ---------------------------------------------------------------------------
axios.interceptors.response.use(
  response => response,

  async error => {
    const originalRequest = error.config

    // Ignore errors without an associated request.
    if (!originalRequest) {
      return Promise.reject(error)
    }

    const isAuthEndpoint =
      originalRequest.url?.includes('/api/login/') ||
      originalRequest.url?.includes('/api/signup/') ||
      originalRequest.url?.includes('/api/refresh/') ||
      originalRequest.url?.includes('/api/logout/')

    if (
      error.response?.status === 401 &&
      !originalRequest._skipAuthRetry &&
      !isAuthEndpoint
    ) {
      // Mark the request before refreshing to prevent infinite retries.
      originalRequest._skipAuthRetry = true

      try {
        const { useUserStore } = await import('@/stores/user')
        const userStore = useUserStore()

        const newToken = await userStore.attemptRefresh()

        if (newToken) {
          originalRequest.headers = originalRequest.headers || {}
          originalRequest.headers.Authorization = `Bearer ${newToken}`

          return axios(originalRequest)
        }
      } catch (refreshError) {
        // Refresh failed; continue to the login redirect below.
      }

      router.push('/login')
    }

    return Promise.reject(error)
  }
)

// ---------------------------------------------------------------------------
// Mount the Vue application
// ---------------------------------------------------------------------------
const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

app.mount('#app')
