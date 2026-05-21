/**
 * Auth store — persists JWT + user info, drives app-wide auth state.
 * Uses a simple module-level reactive store (no Zustand needed).
 */

import { setToken, clearToken, isAuthenticated, type AuthUser } from "@/lib/api"
import { socket } from "@/lib/socket"

interface AuthState {
  user: AuthUser | null
  authenticated: boolean
  activeAccountName: string | null
}

// Listeners for state changes
type Listener = (state: AuthState) => void
const listeners = new Set<Listener>()

const isBrowser = typeof window !== "undefined"

function loadUser(): AuthUser | null {
  if (!isBrowser) return null
  try {
    const raw = localStorage.getItem("tg_user")
    return raw ? (JSON.parse(raw) as AuthUser) : null
  } catch {
    return null
  }
}

const state: AuthState = {
  user: loadUser(),
  authenticated: isAuthenticated(),
  activeAccountName: isBrowser ? localStorage.getItem("tg_active_account") : null,
}

function notify() {
  listeners.forEach((l) => l({ ...state }))
}

export const authStore = {
  getState: (): AuthState => ({ ...state }),

  subscribe: (listener: Listener) => {
    listeners.add(listener)
    return () => listeners.delete(listener)
  },

  login(token: string, user: AuthUser) {
    if (isBrowser) {
      setToken(token)
      localStorage.setItem("tg_user", JSON.stringify(user))
    }
    state.user = user
    state.authenticated = true
    socket.connect(token)
    notify()
  },

  logout() {
    if (isBrowser) {
      clearToken()
      localStorage.removeItem("tg_user")
      localStorage.removeItem("tg_active_account")
    }
    state.user = null
    state.authenticated = false
    state.activeAccountName = null
    socket.disconnect()
    notify()
  },

  setActiveAccount(name: string | null) {
    state.activeAccountName = name
    if (isBrowser) {
      if (name) {
        localStorage.setItem("tg_active_account", name)
      } else {
        localStorage.removeItem("tg_active_account")
      }
    }
    notify()
  },

  // Reconnect socket on page load if already authenticated
  init() {
    if (!isBrowser) return
    const token = localStorage.getItem("tg_token")
    if (token && state.authenticated) {
      socket.connect(token)
    }
  },
}

// Auto-init on module load
authStore.init()
