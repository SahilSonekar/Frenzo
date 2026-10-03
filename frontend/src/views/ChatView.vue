<template>
  <div class="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-4 gap-4 px-4 py-6">
    <!-- LEFT: Conversations List -->
    <div class="main-left col-span-1">
      <div class="p-4 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm">
        <div class="space-y-4">
          <div
            class="flex items-center justify-between p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer transition"
            v-for="conversation in conversations"
            :key="conversation.id"
            @click="setActiveConversation(conversation.id)"
          >
            <div class="flex items-center space-x-2">
              <template v-for="user in conversation.users" :key="user.id">
                <img v-if="user.id !== userStore.user.id" 
                :src="user.get_avatar" class="w-10 h-10 rounded-full" />
                <p
                  class="text-xs font-bold text-gray-800 dark:text-gray-200"
                  v-if="user.id !== userStore.user.id"
                >
                  {{ user.name }}
                </p>
              </template>
            </div>
<span class="text-xs text-gray-500">{{ conversation.modified_at_formatted }} ago</span>

          </div>
        </div>
      </div>
    </div>

    <!-- RIGHT: Chat View -->
    <div class="main-center col-span-1 md:col-span-3 flex flex-col space-y-4">
      <!-- Messages -->
      <div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm h-[400px] overflow-y-auto p-4">
        <template v-for="message in activeConversation.messages" :key="message.id">
          <!-- Outgoing Message -->
          <div
            class="flex w-full mt-2 space-x-3 max-w-md ml-auto justify-end"
            v-if="message.created_by.id === userStore.user.id"
          >
            <div>
              <div class="bg-blue-600 text-white p-3 rounded-l-lg rounded-br-lg">
                <p class="text-sm">{{ message.body }}</p>
              </div>
              <span class="text-xs text-gray-500">{{ message.created_at_formatted }} ago</span>
            </div>
            <img :src="message.created_by.get_avatar" class="w-10 h-10 rounded-full" />
          </div>

          <!-- Incoming Message -->
          <div
            class="flex w-full mt-2 space-x-3 max-w-md"
            v-else
          >
            <img :src="message.created_by.get_avatar" class="w-10 h-10 rounded-full" />
            <div>
              <div class="bg-gray-300 dark:bg-gray-800 text-black dark:text-white p-3 rounded-r-lg rounded-bl-lg">
                <p class="text-sm">{{ message.body }}</p>
              </div>
              <span class="text-xs text-gray-500">{{ message.created_at_formatted }} ago</span>
            </div>
          </div>
        </template>
      </div>

      <!-- Input -->
      <div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm">
        <form @submit.prevent="submitForm">
          <div class="p-4">
            <textarea
              v-model="body"
              class="p-3 w-full bg-gray-100 dark:bg-gray-800 dark:text-white rounded-lg"
              placeholder="What do you want to say?"
              rows="2"
            ></textarea>
          </div>
          <div class="p-4 border-t border-gray-100 dark:border-gray-700 flex justify-end">
            <button
              type="submit"
              class="py-2 px-5 bg-purple-600 hover:bg-purple-700 text-white rounded-lg shadow transition"
            >
              Send
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios'
import { useUserStore } from '@/stores/user'

export default {
  name: 'Chat',

  setup() {
    const userStore = useUserStore()
    return { userStore }
  },

  data() {
    return {
      conversations: [],
      activeConversation: {
        messages: [],
      },
      activeConversationId: null,
      body: '',
      // WebSocket state
      chatSocket: null,
      wsConnected: false,
      wsError: false,
    }
  },

  mounted() {
    this.getConversations()
  },

  beforeUnmount() {
    this.closeSocket()
  },

  methods: {
    // ── WebSocket helpers ────────────────────────────────────────────────

    openSocket(conversationId) {
      this.closeSocket()                      // close any previous connection
      if (!conversationId) return

      const token = this.userStore.user.access
      if (!token) {
        console.error('[Chat] No access token – WebSocket not opened')
        return
      }

      // Derive ws:// or wss:// from the existing axios base URL.
      const base   = (axios.defaults.baseURL || 'http://localhost:8000').replace(/^http/, 'ws')
      const url    = `${base}/ws/chat/${conversationId}/?token=${token}`

      let socket
      try {
        socket = new WebSocket(url)
      } catch (err) {
        console.error('[Chat] WebSocket constructor failed:', err)
        this.wsError = true
        return
      }

      this.chatSocket = socket

      socket.onopen = () => {
        this.wsConnected = true
        this.wsError     = false
      }

      socket.onmessage = (event) => {
        try {
          this.onSocketMessage(JSON.parse(event.data))
        } catch (err) {
          console.error('[Chat] Could not parse WebSocket message:', err)
        }
      }

      // Never log the token or the full URL.
      socket.onerror = () => {
        console.error('[Chat] WebSocket error – falling back to REST for sends')
        this.wsError = true
      }

      socket.onclose = () => {
        this.wsConnected = false
        if (this.chatSocket === socket) this.chatSocket = null
      }
    },

    closeSocket() {
      const socket = this.chatSocket
      if (!socket) return
      // Detach handlers before closing so onclose side-effects don't fire.
      socket.onopen    = null
      socket.onmessage = null
      socket.onerror   = null
      socket.onclose   = null
      try {
        if (socket.readyState === WebSocket.OPEN ||
            socket.readyState === WebSocket.CONNECTING) {
          socket.close()
        }
      } catch (err) {
        console.error('[Chat] Error closing WebSocket:', err)
      }
      this.chatSocket  = null
      this.wsConnected = false
    },

    onSocketMessage(message) {
      if (!message?.id) return
      if (!this.activeConversation?.messages) return

      // De-duplicate: the sender also receives the broadcast of its own message.
      if (this.activeConversation.messages.some((m) => m.id === message.id)) return

      this.activeConversation.messages.push(message)

      // Keep the left-hand list sorted by latest activity.
      const conv = this.conversations.find((c) => c.id === this.activeConversation.id)
      if (conv) conv.modified_at_formatted = message.created_at_formatted
      this.conversations.sort((a, b) => new Date(b.modified_at) - new Date(a.modified_at))
    },

    // ── Existing REST helpers (behaviour unchanged) ───────────────────

    setActiveConversation(id) {
      this.activeConversationId = id
      this.getMessages()
      this.openSocket(id)
    },

    getConversations() {
      axios
        .get('/api/chat/')
        .then((response) => {
          this.conversations = response.data

 this.conversations.sort((a, b) =>
        new Date(b.modified_at) - new Date(a.modified_at)
      )
          if (this.conversations.length) {
            this.activeConversationId = this.conversations[0].id
            this.getMessages()
            this.openSocket(this.activeConversationId)
          }
        })
        .catch((error) => {
          console.error(error)
        })
    },

    getMessages() {
      if (!this.activeConversationId) return

      axios
        .get(`/api/chat/${this.activeConversationId}/`)
        .then((response) => {
          this.activeConversation = response.data
        })
        .catch((error) => {
          console.error(error)
        })
    },

  submitForm() {
  if (!this.body.trim()) return

  // ── Prefer the live WebSocket channel ──────────────────────────────
  if (this.chatSocket?.readyState === WebSocket.OPEN) {
    this.chatSocket.send(JSON.stringify({ body: this.body }))
    this.body = ''
    return
  }

  // ── REST fallback (WebSocket unavailable / connecting / errored) ───
  axios.post(`/api/chat/${this.activeConversation.id}/send/`, { body: this.body })
    .then((response) => {
      // update messages in the right pane
      this.activeConversation.messages.push(response.data)
      this.body = ''

      // EITHER: quick local update of the left list time
      const conv = this.conversations.find(c => c.id === this.activeConversation.id)
      if (conv) {
        // use the new message time as the latest activity
        conv.modified_at_formatted = response.data.created_at_formatted
      }

      // OR: re-fetch the conversations list to get fresh times (and resort)
      // this.getConversations()
      
      this.conversations.sort((a, b) =>
        new Date(b.modified_at) - new Date(a.modified_at)
      )
    })
    .catch(console.error)
}

  },
}
</script>
