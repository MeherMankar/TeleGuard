/**
 * Centralized API client for TeleGuard backend.
 * All requests go through this module — JWT is injected automatically.
 */

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8080"

const isBrowser = typeof window !== "undefined"

function getToken(): string | null {
  if (!isBrowser) return null
  return localStorage.getItem("tg_token")
}

export function setToken(token: string) {
  if (!isBrowser) return
  localStorage.setItem("tg_token", token)
}

export function clearToken() {
  if (!isBrowser) return
  localStorage.removeItem("tg_token")
}

export function isAuthenticated(): boolean {
  return !!getToken()
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  }
  if (token) {
    headers["Authorization"] = `Bearer ${token}`
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  })

  if (res.status === 401) {
    clearToken()
    window.location.href = "/"
    throw new Error("Unauthorized")
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(body?.detail ?? `HTTP ${res.status}`)
  }

  // 204 No Content
  if (res.status === 204) return undefined as T

  return res.json() as Promise<T>
}

const get = <T>(path: string) => request<T>(path, { method: "GET" })
const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined })
const del = <T>(path: string) => request<T>(path, { method: "DELETE" })

// ─── Auth ────────────────────────────────────────────────────────────────────

export interface AuthUser {
  id: number
  first_name: string | null
  last_name: string | null
  username: string | null
}

export interface LoginResponse {
  token: string
  user: AuthUser
}

export const authApi = {
  login: (initData: string) =>
    post<LoginResponse>("/api/auth/login", { initData }),
  devLogin: () => get<LoginResponse>("/api/auth/dev-login"),
}

// ─── Accounts ────────────────────────────────────────────────────────────────

export interface Account {
  id: string
  name: string
  phone: string
  username?: string
  is_active: boolean
  auto_reply_enabled?: boolean
  otp_destroyer_enabled?: boolean
  user_id: number
}

export interface AccountStatus {
  [name: string]: {
    connected: boolean
    phone: string
    name: string
    active: boolean
  }
}

export interface AccountProfile {
  id: number
  first_name: string
  last_name: string
  username: string
  phone: string
  bio: string
  dc_id: number | null
  premium: boolean
  verified: boolean
  has_photo: boolean
  account_name: string
}

export const accountsApi = {
  list: () => get<Account[]>("/api/accounts/list"),
  status: () => get<AccountStatus>("/api/accounts/status"),
  remove: (account_id: string) =>
    del<{ status: string }>(`/api/accounts/remove/${account_id}`),
  profile: (account_name: string) =>
    get<AccountProfile>(`/api/accounts/profile/${encodeURIComponent(account_name)}`),
  toggleReply: (name: string) =>
    post<{ status: string; auto_reply_enabled: boolean }>("/api/accounts/toggle-reply", { name }),
  sendCode: (phone: string) =>
    post<{ session_id: string; phone_code_hash: string }>("/api/accounts/send-code", { phone }),
  verifyCode: (session_id: string, code: string) =>
    post<{ status: "success" | "requires_2fa" }>("/api/accounts/verify-code", { session_id, code }),
  verifyPassword: (session_id: string, password: string) =>
    post<{ status: "success" }>("/api/accounts/verify-password", { session_id, password }),
  qrLogin: () => get<{ session_id: string; url: string }>("/api/accounts/qr-login"),
  qrStatus: (session_id: string) =>
    get<{ status: "pending" | "success" | "failed" | "requires_2fa"; error?: string }>(
      `/api/accounts/qr-status/${session_id}`,
    ),
  qrPassword: (session_id: string, password: string) =>
    post<{ status: "success" }>("/api/accounts/qr-password", { session_id, password }),
}

// ─── Chats ───────────────────────────────────────────────────────────────────

export interface MediaInfo {
  type: "photo" | "video" | "gif" | "sticker" | "voice" | "audio" | "file" | "webpage" | "unknown"
  id?: string
  width?: number
  height?: number
  duration?: number
  size?: number
  filename?: string
  mime?: string
  emoji?: string
  animated?: boolean
  round?: boolean
  has_spoiler?: boolean
  url?: string
  title?: string
  description?: string
  site_name?: string
  photo_id?: string
}

export interface InlineButton {
  text: string
  type: "url" | "callback" | "unknown"
  url?: string
  data?: string
}

export interface Dialog {
  id: number
  name: string
  title: string
  is_group: boolean
  is_channel: boolean
  is_user: boolean
  unread_count: number
  last_message: {
    id: number
    text: string | null
    date: string | null
    out: boolean
    media_type?: string | null
  } | null
  pinned: boolean
  has_photo: boolean
  entity_id: number
  status: string | null  // "online", "last seen Xm ago", "last seen recently", etc.
}

export interface Message {
  id: number
  text: string | null
  date: string | null
  out: boolean
  sender_id: number | null
  sender_name: string | null
  reply: {
    msg_id: number
    text?: string
    sender_id?: number
    media_type?: string | null
  } | null
  forward: {
    from_name?: string
    channel_post?: number
    date?: string
  } | null
  media: MediaInfo | null
  buttons: InlineButton[][] | null
  views: number | null
  pinned: boolean
  silent: boolean
}

export interface ChatFolder {
  id: number
  title: string
  emoji: string | null
  is_default: boolean
  contacts: boolean
  non_contacts: boolean
  groups: boolean
  broadcasts: boolean
  bots: boolean
  exclude_muted: boolean
  exclude_read: boolean
  exclude_archived: boolean
  included_peers: number[]
  excluded_peers: number[]
}

const API_URL_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8080"

function getPhotoToken(): string {
  if (typeof window === "undefined") return ""
  return localStorage.getItem("tg_token") ?? ""
}

export const chatsApi = {
  dialogs: (accountName: string, limit = 50) =>
    get<Dialog[]>(`/api/chats/dialogs/${encodeURIComponent(accountName)}?limit=${limit}`),
  history: (accountName: string, chatId: number, limit = 50) =>
    get<Message[]>(
      `/api/chats/history/${encodeURIComponent(accountName)}/${chatId}?limit=${limit}`,
    ),
  /** Returns a URL to proxy the entity's profile photo — includes JWT so <img> works */
  photoUrl: (accountName: string, entityId: number): string => {
    const token = getPhotoToken()
    const base = `${API_URL_BASE}/api/chats/photo/${encodeURIComponent(accountName)}/${entityId}`
    return token ? `${base}?token=${encodeURIComponent(token)}` : base
  },
  /** Returns a URL to proxy a message's media thumbnail/file */
  mediaUrl: (accountName: string, chatId: number, messageId: number): string => {
    const token = getPhotoToken()
    const base = `${API_URL_BASE}/api/chats/media/${encodeURIComponent(accountName)}/${chatId}/${messageId}`
    return token ? `${base}?token=${encodeURIComponent(token)}` : base
  },
  /** Get real-time online/last-seen status for a user */
  userStatus: (accountName: string, entityId: number) =>
    get<{ entity_id: number; status: string | null; is_online: boolean }>(
      `/api/chats/status/${encodeURIComponent(accountName)}/${entityId}`,
    ),
  // ── Folders ──────────────────────────────────────────────────────────────
  folders: (accountName: string) =>
    get<ChatFolder[]>(`/api/chats/folders/${encodeURIComponent(accountName)}`),
  createFolder: (accountName: string, folder: Partial<ChatFolder>) =>
    post<{ status: string; id: number; title: string }>(
      `/api/chats/folders/${encodeURIComponent(accountName)}`,
      folder,
    ),
  deleteFolder: (accountName: string, folderId: number) =>
    del<{ status: string }>(`/api/chats/folders/${encodeURIComponent(accountName)}/${folderId}`),
}

// ─── Messaging ───────────────────────────────────────────────────────────────

export interface MessagingStats {
  total_messages_sent: number
  auto_replies_sent: number
  active_accounts: number
  dm_topics_created: number
}

export interface AutomationJob {
  id: string
  account_id: string
  job_type: string
  job_config: string
  enabled: boolean
  interval_seconds: number
  last_run: number
  next_run: number
  created_at: number
}

export const messagingApi = {
  stats: () => get<MessagingStats>("/api/messaging/stats"),
  send: (account_name: string, target: string, message: string) =>
    post<{ status: string }>("/api/messaging/send", { account_name, target, message }),
  jobs: () => get<AutomationJob[]>("/api/messaging/jobs"),
  createJob: (payload: {
    account_id: string
    job_type: string
    job_config: Record<string, unknown>
    interval_seconds: number
  }) => post<{ status: string; job_id: string }>("/api/messaging/jobs", payload),
  deleteJob: (job_id: string) => del<{ status: string }>(`/api/messaging/jobs/${job_id}`),
  bulk: (account_name: string, targets: string[], message: string) =>
    post<{ status: string; message: string }>("/api/messaging/bulk", {
      account_name,
      targets,
      message,
    }),
}

// ─── Auto Reply ──────────────────────────────────────────────────────────────

export interface AutoReplySettings {
  keywords: Record<string, string>
}

export const autoReplyApi = {
  settings: () => get<AutoReplySettings>("/api/auto-reply/settings"),
  addKeyword: (keyword: string, reply: string) =>
    post<{ status: string; keyword: string; reply: string }>("/api/auto-reply/keywords", {
      keyword,
      reply,
    }),
  deleteKeyword: (keyword: string) =>
    del<{ status: string }>(`/api/auto-reply/keywords/${encodeURIComponent(keyword)}`),
}

// ─── Sessions ────────────────────────────────────────────────────────────────

export interface Session {
  account_id: string
  account_name: string
  hash?: number
  device_model?: string
  platform?: string
  system_version?: string
  app_name?: string
  app_version?: string
  date_created?: string
  date_active?: string
  ip?: string
  country?: string
  region?: string
}

export const sessionsApi = {
  list: () => get<Session[]>("/api/sessions/list"),
  revoke: (account_id: string, session_hash: string) =>
    post<{ status: string; message: string }>("/api/sessions/revoke", {
      account_id,
      session_hash,
    }),
  addRequest: (phone: string) =>
    post<{ status: string; message: string }>("/api/sessions/add/request", { phone }),
  addConfirm: (phone: string, code?: string, password?: string) =>
    post<{ status: string; message: string }>("/api/sessions/add/confirm", {
      phone,
      code,
      password,
    }),
}

// ─── Security ────────────────────────────────────────────────────────────────

export interface SecuritySettings {
  settings: {
    enabled: boolean
    user_id?: number
  }
  stats: {
    destroyed_count: number
  }
}

export interface SecurityLog {
  device?: string
  ip?: string
  timestamp?: string
  action?: string
}

export const securityApi = {
  settings: () => get<SecuritySettings>("/api/security/settings"),
  updateSettings: (enabled: boolean) =>
    post<{ status: string; enabled: boolean }>("/api/security/settings", { enabled }),
  logs: (limit = 15) => get<SecurityLog[]>(`/api/security/logs?limit=${limit}`),
  trustedSessions: (account_id: string) =>
    get<number[]>(`/api/security/trusted/${account_id}`),
  addTrusted: (account_id: string, session_hash: number) =>
    post<{ status: string }>("/api/security/trusted/add", { account_id, session_hash }),
  removeTrusted: (account_id: string, session_hash: number) =>
    post<{ status: string }>("/api/security/trusted/remove", { account_id, session_hash }),

  // OTP Destroyer — per-account, calls running bot immediately
  toggleOtpDestroyer: (account_id: string, enabled: boolean) =>
    post<{ status: string; message: string; enabled: boolean }>(
      "/api/security/otp-destroyer/toggle",
      { account_id, enabled },
    ),
  tempPassthrough: (account_id: string) =>
    post<{ status: string; message: string }>(
      "/api/security/otp-destroyer/temp-passthrough",
      { account_id },
    ),
  disableDestroyerTemp: (account_id: string) =>
    post<{ status: string; message: string }>(
      "/api/security/otp-destroyer/disable-temp",
      { account_id },
    ),
}

// ─── Analytics ───────────────────────────────────────────────────────────────

export interface DashboardData {
  stats: {
    totalAccounts: number
    activeAccounts: number
    activeSessions: number
    messagesSent: number
    destroyedSessions: number
  }
  recentActivities: Array<{
    type: string
    message: string
    timestamp: string | null
  }>
}

export const analyticsApi = {
  dashboard: () => get<DashboardData>("/api/analytics/dashboard"),
}

// ─── Proxies ─────────────────────────────────────────────────────────────────

export interface Proxy {
  id: string
  name?: string
  type: string
  server: string
  port: number
  username?: string
  secret?: string
}

export const proxiesApi = {
  list: () => get<Proxy[]>("/api/proxies/list"),
  add: (payload: {
    name?: string
    type: string
    server: string
    port: number
    username?: string
    password?: string
    secret?: string
  }) => post<{ status: string; proxy_id: string }>("/api/proxies/add", payload),
  delete: (proxy_id: string) =>
    del<{ status: string; message: string }>(`/api/proxies/delete/${proxy_id}`),
  assign: (account_id: string, proxy_id: string) =>
    post<{ status: string; message: string }>("/api/proxies/assign", { account_id, proxy_id }),
  remove: (account_id: string) =>
    post<{ status: string; message: string }>("/api/proxies/remove", { account_id }),
  test: (proxy_id: string) =>
    post<{ status: string; message: string; latency: number }>("/api/proxies/test", { proxy_id }),
  setDefault: (proxy_id: string) =>
    post<{ status: string; message: string }>("/api/proxies/default", { proxy_id }),
  getDefault: () => get<Proxy | { status: string }>("/api/proxies/default"),
}
