import { useState, useCallback, useEffect } from "react"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { SearchHeader } from "@/components/telegram/search-header"
import { FabButton } from "@/components/telegram/fab-button"
import { Sidebar } from "@/components/telegram/sidebar"
import { ProfilePage } from "@/components/telegram/profile-page"
import { AuthFlow } from "@/components/telegram/auth/auth-flow"
import { SettingsPage } from "@/components/telegram/settings-page"
import { ContactsListPage } from "@/components/telegram/contacts-list-page"
import { BottomNav } from "@/components/telegram/bottom-nav"
import { UserProvider, useUser } from "@/contexts/user-context"
import { ProtectionManagerPage } from "@/components/telegram/protection-manager-page"
import { SpamMasterPage } from "@/components/telegram/spam-master-page"
import { CleanupPage } from "@/components/telegram/cleanup-page"
import { AutomationPage } from "@/components/telegram/automation-page"
import { SessionManagerPage } from "@/components/telegram/session-manager-page"
import { DashboardPage } from "@/components/telegram/dashboard-page"
import { ProxyManagerPage } from "@/components/telegram/proxy-manager-page"
import { ChatFoldersPage } from "@/components/telegram/chat-folders-page"
import { Toaster } from "@/components/ui/sonner"
import { useAuth } from "@/hooks/use-auth"
import { authApi, chatsApi, type Dialog, type ChatFolder } from "@/lib/api"
import { authStore } from "@/store/auth"
import { useWsEvent } from "@/hooks/use-ws-event"
import { Loader2, MessageSquare, FolderOpen, Users, Radio, Bot, User, Bell, Folder, Pin, Check, VolumeX, BadgeCheck } from "lucide-react"
import { cn } from "@/lib/utils"

function safeText(v: unknown): string | null {
  if (v === null || v === undefined) return null
  if (typeof v === "string") return v
  if (typeof v === "object" && v !== null) {
    // Telegram message object with text field
    const obj = v as Record<string, unknown>
    if (typeof obj.text === "string") return obj.text
    if (typeof obj.message === "string") return obj.message
  }
  try { return String(v) } catch { return null }
}

export const Route = createFileRoute("/")({
  component: IndexPage,
})

function IndexPage() {
  return (
    <UserProvider>
      <AppShell />
      <Toaster />
    </UserProvider>
  )
}

function AppShell() {
  const { authenticated } = useAuth()
  const [autoLogging, setAutoLogging] = useState(true)

  // On mount: if running inside Telegram WebApp, auto-login with initData
  useEffect(() => {
    if (authenticated) { setAutoLogging(false); return }

    const tg = (window as any).Telegram?.WebApp
    if (tg?.initData) {
      // Running inside Telegram — auto-login silently
      authApi.login(tg.initData)
        .then((res) => {
          authStore.login(res.token, res.user)
          tg.ready?.()
          tg.expand?.()
        })
        .catch(console.error)
        .finally(() => setAutoLogging(false))
    } else {
      setAutoLogging(false)
    }
  }, [authenticated])

  if (autoLogging) {
    return (
      <div className="dark min-h-screen bg-[#17212b] flex items-center justify-center">
        <Loader2 className="h-10 w-10 text-[#2AABEE] animate-spin" />
      </div>
    )
  }

  return authenticated ? <TelegramChatList /> : <LoginGate />
}

// ─── Login Gate ──────────────────────────────────────────────────────────────

function LoginGate() {
  const [loading, setLoading] = useState(false)
  const [showAuthFlow, setShowAuthFlow] = useState(false)
  const isTelegramWebApp = !!(window as any).Telegram?.WebApp?.initData

  const handleDevLogin = async () => {
    setLoading(true)
    try {
      const res = await authApi.devLogin()
      authStore.login(res.token, res.user)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="dark">
      <div className="min-h-screen bg-[#17212b] text-white flex flex-col items-center justify-center px-6 max-w-md mx-auto">
        {/* Logo */}
        <div className="w-24 h-24 rounded-full bg-gradient-to-br from-sky-400 to-blue-600 flex items-center justify-center mb-6 shadow-2xl">
          <svg viewBox="0 0 24 24" className="w-14 h-14 text-white fill-current">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .37z" />
          </svg>
        </div>

        <h1 className="text-3xl font-bold mb-2">TeleGuard</h1>
        <p className="text-gray-400 text-center mb-8 text-sm leading-relaxed">
          Telegram Security Dashboard
          <br />
          Multi-account control center
        </p>

        {/* If opened in browser, explain how to use properly */}
        {!isTelegramWebApp && (
          <div className="w-full bg-[#242f3d] border border-[#2AABEE]/30 rounded-xl p-4 mb-6 text-center">
            <p className="text-[#2AABEE] text-sm font-medium mb-1">Open inside Telegram</p>
            <p className="text-gray-400 text-xs leading-relaxed">
              For automatic login, open TeleGuard via{" "}
              <span className="text-white font-medium">@TeleGuardRobot</span>
              {" "}→ Menu → Dashboard.
              <br />
              Your bot accounts will load instantly.
            </p>
          </div>
        )}

        {/* Manual Telegram login — adds this browser session as a new account */}
        <button
          onClick={() => setShowAuthFlow(true)}
          className="w-full py-4 bg-[#2AABEE] text-white rounded-xl font-semibold text-base mb-3 hover:bg-[#2AABEE]/90 transition-colors"
        >
          Login with Telegram
        </button>

        {/* Dev login — only in development mode */}
        {import.meta.env.DEV && (
          <button
            onClick={handleDevLogin}
            disabled={loading}
            className="w-full py-3 border border-white/20 text-gray-300 rounded-xl font-medium text-sm hover:bg-white/5 transition-colors flex items-center justify-center gap-2"
          >
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            Dev Login (local only)
          </button>
        )}

        <AuthFlow
          isOpen={showAuthFlow}
          onClose={() => setShowAuthFlow(false)}
          onSuccess={() => setShowAuthFlow(false)}
        />
      </div>
    </div>
  )
}

// ─── Main Chat List ───────────────────────────────────────────────────────────

function TelegramChatList() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { activeAccount } = useUser()

  const [searchValue, setSearchValue] = useState("")
  const [activeNavTab, setActiveNavTab] = useState<"chats" | "contacts" | "settings" | "profile">("chats")
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const [isProfileOpen, setIsProfileOpen] = useState(false)
  const [isAuthFlowOpen, setIsAuthFlowOpen] = useState(false)
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [isContactsOpen, setIsContactsOpen] = useState(false)
  const [isProtectionManagerOpen, setIsProtectionManagerOpen] = useState(false)
  const [isSpamMasterOpen, setIsSpamMasterOpen] = useState(false)
  const [isCleanupOpen, setIsCleanupOpen] = useState(false)
  const [isAutomationOpen, setIsAutomationOpen] = useState(false)
  const [isSessionManagerOpen, setIsSessionManagerOpen] = useState(false)
  const [isDashboardOpen, setIsDashboardOpen] = useState(false)
  const [isProxyManagerOpen, setIsProxyManagerOpen] = useState(false)
  const [isChatFoldersOpen, setIsChatFoldersOpen] = useState(false)

  const { data: dialogs = [], isLoading: dialogsLoading } = useQuery({
    queryKey: ["dialogs", activeAccount?.name],
    queryFn: () => chatsApi.dialogs(activeAccount!.name, 100),
    enabled: !!activeAccount,
    staleTime: 0,
    retry: false,
  })

  // Fetch real Telegram folders
  const { data: folders = [] } = useQuery({
    queryKey: ["folders", activeAccount?.name],
    queryFn: () => chatsApi.folders(activeAccount!.name),
    enabled: !!activeAccount,
    staleTime: 60_000,
  })

  useWsEvent(
    "new_message",
    useCallback(() => {
      queryClient.invalidateQueries({ queryKey: ["dialogs", activeAccount?.name] })
    }, [activeAccount?.name, queryClient]),
  )

  const handleNavTabChange = (tab: "chats" | "contacts" | "settings" | "profile") => {
    setActiveNavTab(tab)
    if (tab === "contacts") setIsContactsOpen(true)
    else if (tab === "settings") setIsSettingsOpen(true)
    else if (tab === "profile") setIsProfileOpen(true)
  }

  const [activeFolder, setActiveFolder] = useState<number>(0) // 0 = All Chats

  const filteredDialogs = dialogs.filter((d) => {
    const matchesSearch = !searchValue || d.name?.toLowerCase().includes(searchValue.toLowerCase())
    if (!matchesSearch) return false

    if (activeFolder === 0) return true // All Chats

    const folder = folders.find((f) => f.id === activeFolder)
    if (!folder) return true

    // Filter by folder rules
    if (folder.contacts && d.is_user) return true
    if (folder.non_contacts && d.is_user) return true
    if (folder.groups && d.is_group) return true
    if (folder.broadcasts && d.is_channel) return true
    if (folder.bots && d.is_user) return true // bots are users too
    if (folder.included_peers.includes(Math.abs(d.id))) return true

    // If folder has type rules, exclude non-matching
    const hasTypeRules = folder.contacts || folder.non_contacts || folder.groups || folder.broadcasts || folder.bots
    if (hasTypeRules || folder.included_peers.length > 0) return false
    return true
  })

  const totalUnread = dialogs.reduce((sum, d) => sum + (d.unread_count ?? 0), 0)

  return (
    <div className="dark">
      <div className="min-h-screen bg-[#17212b] text-foreground max-w-md mx-auto relative pb-16">
        <Sidebar
          isOpen={isSidebarOpen}
          onClose={() => setIsSidebarOpen(false)}
          onProfileClick={() => setIsProfileOpen(true)}
          onAddAccountClick={() => setIsAuthFlowOpen(true)}
          onSettingsClick={() => setIsSettingsOpen(true)}
          onContactsClick={() => setIsContactsOpen(true)}
          onProtectionManagerClick={() => setIsProtectionManagerOpen(true)}
          onSpamMasterClick={() => setIsSpamMasterOpen(true)}
          onCleanupClick={() => setIsCleanupOpen(true)}
          onAutomationClick={() => setIsAutomationOpen(true)}
          onSessionManagerClick={() => setIsSessionManagerOpen(true)}
          onDashboardClick={() => setIsDashboardOpen(true)}
          onProxyManagerClick={() => setIsProxyManagerOpen(true)}
          onChatFoldersClick={() => setIsChatFoldersOpen(true)}
        />

        <SettingsPage isOpen={isSettingsOpen} onClose={() => { setIsSettingsOpen(false); setActiveNavTab("chats") }} />
        <ProfilePage isOpen={isProfileOpen} onClose={() => { setIsProfileOpen(false); setActiveNavTab("chats") }} />
        <ContactsListPage isOpen={isContactsOpen} onClose={() => { setIsContactsOpen(false); setActiveNavTab("chats") }} />
        <ProtectionManagerPage isOpen={isProtectionManagerOpen} onClose={() => setIsProtectionManagerOpen(false)} />
        <SpamMasterPage isOpen={isSpamMasterOpen} onClose={() => setIsSpamMasterOpen(false)} />
        <CleanupPage isOpen={isCleanupOpen} onClose={() => setIsCleanupOpen(false)} />
        <AutomationPage isOpen={isAutomationOpen} onClose={() => setIsAutomationOpen(false)} />
        <SessionManagerPage isOpen={isSessionManagerOpen} onClose={() => setIsSessionManagerOpen(false)} />
        <DashboardPage isOpen={isDashboardOpen} onClose={() => setIsDashboardOpen(false)} />
        <ProxyManagerPage isOpen={isProxyManagerOpen} onClose={() => setIsProxyManagerOpen(false)} />
        <ChatFoldersPage isOpen={isChatFoldersOpen} onClose={() => setIsChatFoldersOpen(false)} />

        <AuthFlow
          isOpen={isAuthFlowOpen}
          onClose={() => setIsAuthFlowOpen(false)}
          onSuccess={() => {
            setIsAuthFlowOpen(false)
            queryClient.invalidateQueries({ queryKey: ["accounts"] })
          }}
        />

        <SearchHeader
          searchValue={searchValue}
          onSearchChange={setSearchValue}
          onMenuClick={() => setIsSidebarOpen(true)}
          title={activeAccount?.name ?? "TeleGuard"}
        />

        {/* Dynamic folder tabs — from real Telegram API */}
        {folders.length > 0 && (
          <div className="flex gap-1 px-2 py-2 overflow-x-auto scrollbar-hide border-b border-[#242f3d]">
            {folders.map((folder) => {
              const unread = folder.id === 0
                ? totalUnread
                : dialogs.filter((d) =>
                    d.unread_count > 0 && (
                      (folder.groups && d.is_group) ||
                      (folder.broadcasts && d.is_channel) ||
                      (folder.contacts && d.is_user) ||
                      folder.included_peers.includes(Math.abs(d.id))
                    )
                  ).reduce((s, d) => s + d.unread_count, 0)

              // Pick icon based on folder type or stored icon id
              const FolderTabIcon = folder.is_default
                ? MessageSquare
                : folder.emoji === "users" || folder.groups ? Users
                : folder.emoji === "radio" || folder.broadcasts ? Radio
                : folder.emoji === "bot" || folder.bots ? Bot
                : folder.emoji === "user" || folder.contacts ? User
                : folder.emoji === "bell" ? Bell
                : Folder

              const isActive = activeFolder === folder.id

              return (
                <button
                  key={folder.id}
                  onClick={() => setActiveFolder(folder.id)}
                  className={cn(
                    "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-colors flex-shrink-0",
                    isActive
                      ? "bg-[#2AABEE] text-white"
                      : "bg-[#242f3d] text-gray-400 hover:text-white",
                  )}
                >
                  <FolderTabIcon className="h-3.5 w-3.5 flex-shrink-0" />
                  <span>{folder.title}</span>
                  {unread > 0 && (
                    <span className={cn(
                      "text-xs font-bold px-1.5 py-0.5 rounded-full min-w-[18px] text-center",
                      isActive ? "bg-white/30 text-white" : "bg-[#2AABEE] text-white",
                    )}>
                      {unread > 99 ? "99+" : unread}
                    </span>
                  )}
                </button>
              )
            })}
            {/* Edit folders */}
            <button
              onClick={() => setIsChatFoldersOpen(true)}
              className="p-2 rounded-full text-gray-500 hover:text-[#2AABEE] bg-[#242f3d] transition-colors flex-shrink-0"
              title="Manage folders"
            >
              <FolderOpen className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* No folders yet — show edit button */}
        {activeAccount && folders.length === 0 && !dialogsLoading && (
          <div className="px-4 py-2 flex items-center gap-2">
            <button
              onClick={() => setIsChatFoldersOpen(true)}
              className="flex items-center gap-2 text-gray-500 hover:text-[#2AABEE] text-sm transition-colors"
            >
              <FolderOpen className="h-4 w-4" />
              <span>Create chat folders</span>
            </button>
          </div>
        )}

        {!activeAccount && (
          <div className="flex flex-col items-center justify-center py-20 px-6 text-center">
            <MessageSquare className="h-16 w-16 text-gray-600 mb-4" />
            <p className="text-white font-medium text-lg mb-2">No account connected</p>
            <p className="text-gray-400 text-sm mb-6">Add a Telegram account to start messaging</p>
            <button
              onClick={() => setIsAuthFlowOpen(true)}
              className="px-6 py-3 bg-[#2AABEE] text-white rounded-xl font-medium"
            >
              Add Account
            </button>
          </div>
        )}

        {activeAccount && dialogsLoading && (
          <div className="flex justify-center py-20">
            <Loader2 className="h-8 w-8 text-[#2AABEE] animate-spin" />
          </div>
        )}

        {activeAccount && !dialogsLoading && (
          <div className="divide-y divide-[#242f3d]">
            {filteredDialogs.length === 0 && (
              <div className="text-center py-16 text-gray-400 text-sm">
                {searchValue ? "No chats match your search" : "No chats yet"}
              </div>
            )}
            {filteredDialogs.map((dialog) => (
              <DialogItem
                key={dialog.id}
                dialog={dialog}
                accountName={activeAccount.name}
                onClick={() =>
                  navigate({
                    to: "/chat/$chatId",
                    params: { chatId: String(dialog.id) },
                    search: { account: activeAccount.name },
                  })
                }
              />
            ))}
          </div>
        )}

        <FabButton onClick={() => setIsContactsOpen(true)} />
        <BottomNav activeTab={activeNavTab} onTabChange={handleNavTabChange} unreadCount={totalUnread} />
      </div>
    </div>
  )
}

function DialogItem({ dialog, accountName, onClick }: { dialog: Dialog; accountName: string; onClick: () => void }) {
  const [imgError, setImgError] = useState(false)
  const displayName = dialog.name || dialog.title || "Unknown"
  const photoUrl = accountName && dialog.has_photo
    ? chatsApi.photoUrl(accountName, dialog.entity_id)
    : null

  // ── Time formatting (Telegram-style) ─────────────────────────────────
  const timeDisplay = (() => {
    if (!dialog.last_message?.date) return ""
    const msgDate = new Date(dialog.last_message.date)
    const now = new Date()
    const diffMs = now.getTime() - msgDate.getTime()
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffDays === 0) return msgDate.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    if (diffDays === 1) return "Yesterday"
    if (diffDays < 7) return msgDate.toLocaleDateString([], { weekday: "short" })
    return msgDate.toLocaleDateString([], { day: "numeric", month: "short" })
  })()

  // ── Message preview text ──────────────────────────────────────────────
  const mediaIcon = (() => {
    const t = dialog.last_message?.media_type
    if (!t) return null
    const icons: Record<string, string> = {
      photo: "🖼", video: "🎬", gif: "GIF", sticker: "🎭",
      voice: "🎤", audio: "🎵", file: "📄", webpage: "🔗",
    }
    return icons[t] ?? "📎"
  })()

  const previewText = safeText(dialog.last_message?.text)
  const senderName = safeText(dialog.last_message?.sender_name)

  // ── Avatar fallback color ─────────────────────────────────────────────
  const colors = [
    "#E53935", "#D81B60", "#8E24AA", "#5E35B1",
    "#1E88E5", "#00897B", "#43A047", "#FB8C00",
    "#F4511E", "#6D4C41", "#039BE5", "#00ACC1",
  ]
  const color = colors[Math.abs(dialog.id) % colors.length]
  const initial = displayName.charAt(0).toUpperCase()

  const isOnline = dialog.status === "online"

  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-white/5 active:bg-white/10 transition-colors text-left"
    >
      {/* Avatar */}
      <div className="relative flex-shrink-0">
        {photoUrl && !imgError ? (
          <img
            src={photoUrl}
            alt={displayName}
            onError={() => setImgError(true)}
            className="w-[54px] h-[54px] rounded-full object-cover"
            loading="lazy"
          />
        ) : (
          <div
            className="w-[54px] h-[54px] rounded-full flex items-center justify-center text-white font-semibold text-xl"
            style={{ backgroundColor: color }}
          >
            {initial}
          </div>
        )}
        {/* Online dot */}
        {isOnline && (
          <span className="absolute bottom-0.5 right-0.5 w-3 h-3 rounded-full bg-green-400 border-2 border-[#17212b]" />
        )}
        {/* Unread mentions badge */}
        {dialog.unread_mentions > 0 && (
          <span className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full bg-red-500 text-white text-[9px] font-bold flex items-center justify-center">
            @
          </span>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        {/* Row 1: Name + time */}
        <div className="flex items-center justify-between gap-1 mb-0.5">
          <div className="flex items-center gap-1 min-w-0">
            {/* Pinned */}
            {dialog.pinned && <Pin className="h-3 w-3 text-gray-500 flex-shrink-0" />}
            {/* Chat type icon */}
            {dialog.is_channel && !dialog.is_group && (
              <Radio className="h-3.5 w-3.5 text-gray-400 flex-shrink-0" />
            )}
            {dialog.is_group && (
              <Users className="h-3.5 w-3.5 text-gray-400 flex-shrink-0" />
            )}
            {dialog.is_bot && (
              <Bot className="h-3.5 w-3.5 text-gray-400 flex-shrink-0" />
            )}
            <p className="text-white font-medium text-[15px] truncate leading-tight">
              {displayName}
            </p>
            {dialog.verified && (
              <BadgeCheck className="h-3.5 w-3.5 text-[#2AABEE] flex-shrink-0" />
            )}
          </div>
          <div className="flex items-center gap-1 flex-shrink-0">
            {dialog.last_message?.out && !dialog.muted && (
              <Check className="h-3.5 w-3.5 text-gray-500" />
            )}
            {dialog.muted && <VolumeX className="h-3 w-3 text-gray-600" />}
            <span className={cn(
              "text-xs whitespace-nowrap",
              dialog.unread_count > 0 && !dialog.muted ? "text-[#2AABEE]" : "text-gray-500",
            )}>
              {timeDisplay}
            </span>
          </div>
        </div>

        {/* Row 2: Preview + unread */}
        <div className="flex items-center justify-between gap-1">
          <p className="text-gray-400 text-[13px] truncate flex-1 leading-tight">
            {/* Sender name in groups */}
            {senderName && !dialog.last_message?.out && (
              <span className="text-[#2AABEE] mr-1 font-medium">{senderName}:</span>
            )}
            {/* Outgoing indicator */}
            {dialog.last_message?.out && (
              <span className="text-gray-500 mr-1">You:</span>
            )}
            {/* Media icon */}
            {mediaIcon && <span className="mr-1">{mediaIcon}</span>}
            {/* Text preview */}
            {previewText ? (
              <span>{previewText}</span>
            ) : dialog.last_message?.media_type ? (
              <span className="capitalize text-gray-500">{dialog.last_message.media_type}</span>
            ) : null}
          </p>

          {/* Unread badge */}
          {dialog.unread_count > 0 ? (
            <span className={cn(
              "ml-1 min-w-[20px] h-5 rounded-full text-white text-xs font-bold flex items-center justify-center px-1.5 flex-shrink-0",
              dialog.muted ? "bg-gray-600" : "bg-[#2AABEE]",
            )}>
              {dialog.unread_count > 9999 ? "9999+" : dialog.unread_count}
            </span>
          ) : dialog.pinned ? (
            <Pin className="h-3.5 w-3.5 text-gray-600 flex-shrink-0" />
          ) : null}
        </div>
      </div>
    </button>
  )
}
