import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import axios from 'axios'

import './assets/main.css'

// ---------------------------------------------------------------------------
// Axios base URL
//
// In development:  set VITE_API_URL=http://localhost:8000 in frontend/.env
//                  (the fallback below keeps local dev working without a .env)
// In production:   set VITE_API_URL=https://api.yoursite.com in the build
//                  environment before running `npm run build`.
//
// VITE_API_URL must NOT end with a trailing slash.
// ---------------------------------------------------------------------------
axios.defaults.baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const app = createApp(App)

app.use(createPinia())
app.use(router, axios)

app.mount('#app')
