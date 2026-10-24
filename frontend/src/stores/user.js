/**
 * Pinia user store — secure JWT storage
 *
 * Access token  → Pinia reactive memory ONLY.  Never written to
 *                 localStorage, sessionStorage, or any JS-readable storage.
 * Refresh token → HttpOnly cookie managed exclusively by the backend.
 *                 This store never reads, writes, or holds the refresh token.
 *
 * Session restoration on page reload
 * ------------------------------------
 * Because the access token lives only in memory it is lost on reload.
 * initStore() calls the /api/refresh/ endpoint (which reads the HttpOnly
 * cookie automatically) to obtain a fresh access token.  If the cookie is
 * absent or expired the user is treated as unauthenticated.
 *
 * Circular-dependency note
 * ------------------------
 * This store must NOT import from main.js (which sets up Axios interceptors).
 * It uses a raw axios call for the refresh so it can be called before the
 * interceptors are fully wired up.
 */

import { defineStore } from 'pinia'
import axios from 'axios'

export const useUserStore = defineStore({
  id: 'user',

  state: () => ({
    user: {
      isAuthenticated: false,
      id    : null,
      name  : null,
      email : null,
      access: null,   // in-memory access token — never persisted to storage
      avatar: null,
    },
    // Flag used by the Axios interceptor to avoid concurrent refresh calls.
    _refreshing: false,
    _refreshQueue: [],
  }),

  actions: {
    /**
     * Called once on application startup (App.vue created()).
     * Attempts to restore the session via the refresh cookie.
     * Never marks the user as authenticated until the server confirms it.
     */
    async initStore() {
      // Non-sensitive UI preferences are fine in localStorage.
      // Token data is NOT restored from localStorage.
      try {
        const response = await axios.post(
          '/api/refresh/',
          {},
          { withCredentials: true },
        )
        const { access } = response.data
        this.user.access         = access
        this.user.isAuthenticated = true

        // Attach the fresh access token to the default Axios header
        // so the subsequent /api/me/ call succeeds.
        axios.defaults.headers.common['Authorization'] = 'Bearer ' + access

        const me = await axios.get('/api/me/')
        this.setUserInfo(me.data)
      } catch {
        // Refresh cookie absent, expired, or invalid — unauthenticated.
        this._clearUserState()
      }
    },

    /**
     * Store the access token in Pinia memory and set the Axios default header.
     * Called after a successful login or signup.
     * Never touches localStorage or sessionStorage.
     *
     * @param {string} accessToken
     */
    setAccessToken(accessToken) {
      this.user.access          = accessToken
      this.user.isAuthenticated = true
      axios.defaults.headers.common['Authorization'] = 'Bearer ' + accessToken
    },

    /**
     * Store user profile information.
     * Only non-sensitive profile fields are preserved in localStorage so that
     * the UI can show a name/avatar before the async initStore() completes.
     */
    setUserInfo(userData) {
      this.user.id     = userData.id
      this.user.name   = userData.name
      this.user.email  = userData.email
      this.user.avatar = userData.avatar ?? userData.get_avatar ?? null

      // Persist only display-only fields — never tokens.
      localStorage.setItem('user.id',     this.user.id     ?? '')
      localStorage.setItem('user.name',   this.user.name   ?? '')
      localStorage.setItem('user.email',  this.user.email  ?? '')
      localStorage.setItem('user.avatar', this.user.avatar ?? '')
    },

    /**
     * Clear all authentication state and remove the Axios Authorization header.
     * Logs the user out on the frontend.  The backend clears the HttpOnly
     * cookie via POST /api/logout/.
     */
    removeToken() {
      this._clearUserState()
    },

    // ── Internal helpers ─────────────────────────────────────────────────

    _clearUserState() {
      this.user.access          = null
      this.user.isAuthenticated = false
      this.user.id              = null
      this.user.name            = null
      this.user.email           = null
      this.user.avatar          = null

      delete axios.defaults.headers.common['Authorization']

      // Remove the display-only localStorage values too.
      ['user.id', 'user.name', 'user.email', 'user.avatar'].forEach(k =>
        localStorage.removeItem(k),
      )
    },

    /**
     * Attempt a token refresh.  Returns the new access token string on
     * success, or null on failure.
     *
     * Used by the Axios response interceptor to retry after a 401.
     * Queues any callers that arrive while a refresh is already in flight
     * so only one refresh request is ever sent at a time.
     */
    async attemptRefresh() {
      if (this._refreshing) {
        // Queue the caller and resolve/reject it when the in-flight
        // refresh finishes.
        return new Promise((resolve, reject) => {
          this._refreshQueue.push({ resolve, reject })
        })
      }

      this._refreshing = true
      try {
        const response = await axios.post(
          '/api/refresh/',
          {},
          {
            withCredentials: true,
            // Skip the response interceptor for this request to avoid loops.
            _skipAuthRetry: true,
          },
        )
        const { access } = response.data
        this.setAccessToken(access)

        // Resolve all queued callers with the new token.
        this._refreshQueue.forEach(p => p.resolve(access))
        return access
      } catch (err) {
        this._clearUserState()
        this._refreshQueue.forEach(p => p.reject(err))
        return null
      } finally {
        this._refreshing    = false
        this._refreshQueue  = []
      }
    },
  },
})
