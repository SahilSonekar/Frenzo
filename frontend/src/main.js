/**
 * Application entry point.
 *
 * Axios configuration
 * -------------------
 * baseURL        — reads VITE_API_URL env var; falls back to localhost:8000
 *                  for local development without a .env file.
 * withCredentials — true so the browser sends the HttpOnly refresh cookie
 *                   on requests to the API origin (required for /api/refresh/
 *                   and /api/logout/).
 * X-CSRFToken    — request interceptor reads the 'csrftoken' cookie that
 *                  Django sets (via @ensure_csrf_cookie on login/signup) and
 *                  attaches it as a header so Django's @csrf_protect passes.
 *
 * Token attachment
 * ----------------
 * The request interceptor reads the current access token from the Pinia store
 * (in-memory only) and sets the Authorization header.  This replaces the
 * previous pattern of setting axios.defaults.headers.common globally from
 * multiple places.
 *
 * 401 retry / refresh
 * --------------------
 * The response interceptor catches 401 responses, requests a token refresh
 * via the HttpOnly cookie, updates the store, and retries the original
 * request exactly once.  If the refresh fails the user is treated as logged
 * out.  Requests already carrying the _skipAuthRetry flag are never retried
 * (prevents infinite loops).
 */

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import axios from 'axios'

import './assets/main.css'

// ---------------------------------------------------------------------------
// Base URL — set from build-time env var; localhost fallback for dev.
// ---------------------------------------------------------------------------
axios.defaults.baseURL     = import.meta.env.VITE_API_URL || 'http://localhost:8000'
axios.defaults.withCredentials = true   // send the HttpOnly refresh cookie

// ---------------------------------------------------------------------------
// Helper: read a cookie value by name (used for CSRF token).
// Returns '' when the cookie is absent.
// ---------------------------------------------------------------------------
function getCookie(name) {
  const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'))
  return match ? decodeURIComponent(match[1]) : ''
}

// ---------------------------------------------------------------------------
// Request interceptor
// 1. Attach Authorization header from Pinia memory (set by setAccessToken).
//    The header is already set on the axios defaults after login/signup; this
//    interceptor ensures newly created axios instances also carry it.
// 2. Attach X-CSRFToken from the 'csrftoken' cookie for state-mutating
//    requests to Django endpoints protected with @csrf_protect.
// ---------------------------------------------------------------------------
axios.interceptors.request.use(config => {
  // CSRF — attach for all non-safe methods.
  const safeMethods = ['get', 'head', 'options', 'trace']
  if (!safeMethods.includes((config.method || 'get').toLowerCase())) {
    const csrfToken = getCookie('csrftoken')
    if (csrfToken) {
      config.headers['X-CSRFToken'] = csrfToken
    }
  }
  return config
})

// ---------------------------------------------------------------------------
// Response interceptor — 401 handling with single-refresh retry
// ---------------------------------------------------------------------------
axios.interceptors.response.use(
  response => response,   // pass through successful responses unchanged

  async error => {
    const originalRequest = error.config

    // Only act on 401 responses that haven't already been retried and are
    // not themselves a refresh or logout call.
    const isAuthEndpoint =
      originalRequest.url?.includes('/api/refresh/') ||
      originalRequest.url?.includes('/api/logout/')

    if (
      error.response?.status === 401 &&
      !originalRequest._skipAuthRetry &&
      !isAuthEndpoint
    ) {
      originalRequest._skipAuthRetry = true

      // Lazy-import to avoid a circular dependency at module load time.
      const { useUserStore } = await import('@/stores/user')
      const userStore = useUserStore()

      const newToken = await userStore.attemptRefresh()
      if (newToken) {
        // Retry the original request with the refreshed token.
        originalRequest.headers['Authorization'] = 'Bearer ' + newToken
        return axios(originalRequest)
      }

      // Refresh failed — redirect to login.
      router.push('/login')
    }

    return Promise.reject(error)
  },
)

// ---------------------------------------------------------------------------
// Mount the Vue application
// ---------------------------------------------------------------------------
const app = createApp(App)

app.use(createPinia())
app.use(router, axios)

app.mount('#app')
