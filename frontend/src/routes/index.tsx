import { useState, useCallback } from "react"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { SearchHeader } from "@/components/telegram/search-header"
import { FilterTabs } from "@/components/telegram/filter-tabs"
import { ArchivedChats } from "@/components/telegram/archived-chats"
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
import { QueryClientProvider, QueryClient } from "@tanstack/react-query"
import { Toaster } from "@/components/ui/sonner"
import { useAuth } from "@/hooks/use-auth"
import { authApi } from "@/lib/api"
import { authStore } from "@/store/auth"
import { chatsApi, type Dialog } from "@/lib/api"
import { useWsEvent } from "@/hooks/use-ws-event"
import { Loader2, MessageSquare } from "lucide-react"
import { cn } from "@/lib/utils"
import { formatDistanceToNow } from "date-fns"

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "TeleGuard" },
      { name: "description", content: "TeleGuard — Telegram Security Dashboard" },
    ],
  }),
  component: IndexPage,
})

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 10_000 },
  },
})

const tabs = [
  { id: "all", icon: "all" as const, count: 0 },
  { id: "people", icon: "people" as const, count: 0 },
  { id: "groups", icon: "groups" as const, count: 0 },
  { id: "bots", icon: "bots" as const, count: 0 },
]

function IndexPage() {
  return (
    <QueryClientProvider client={queryClient}>
      <UserProvider>
        <AppShell />
        <Toaster />
      </UserProvider>
    </QueryClientProvider>
  )
}

function AppShell() {
  const { authenticated } = useAuth()

  if (!authenticated) {
    return <LoginGate />
  }

  return <TelegramChatList />
}

function LoginGate() {
  const [loading, setLoading] = useState(false)
  const [showAuthFlow, setShowAuthFlow] = useState(false)

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

        <h1 className="text-3xl font-bold text-white mb-2">TeleGuard</h1>
        <p className="text-gray-400 text-center mb-10 text-sm leading-relaxed">
          Telegram Security Dashboard
          <br />
          Multi-account control center
        </p>

        <button
          onClick={() => setShowAuthFlow(true)}
          className="w-full py-4 bg-[#2AABEE] text-white rounded-xl font-semibold text-base mb-3 hover:bg-[#2AABEE]/90 transition-colors"
        >
          Login with Telegram
        </button>

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

function TelegramChatList() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { activeAccount } = useUser()
  const [searchValue, setSearchValue] = useState("")
  const [activeTab, setActiveTab] = useState("all")
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

  // Fetch dialogs for active account
  const { data: dialogs = [], isLoading: dialogsLoading } = useQuery({
    queryKey: ["dialogs", activeAccount?.name],
    queryFn: () => chatsApi.dialogs(activeAccount!.name, 100),
    enabled: !!activeAccount,
    staleTime: 15_000,
  })

  // Refresh dialogs on new message via WebSocket
  useWsEvent("new_message", useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["dialogs", activeAccount?.name] })
  }, [activeAccount?.name, queryClient]))

  const handleNavTabChange = (tab: "chats" | "contacts" | "settings" | "profile") => {
    setActiveNavTab(tab)
    if (tab === "contacts") setIsContactsOpen(true)
    else if (tab === "settings") setIsSettingsOpen(true)
    else if (tab === "profile") setIsProfileOpen(true)
  }

  // Filter dialogs
  const filteredDialogs = dialogs.filter((d) => {
    const matchesSearch = !searchValue || d.name?.toLowerCase().includes(searchValue.toLowerCase())
    if (!matchesSearch) return false
    if (activeTab === "all") return true
    if (activeTab === "people") return d.is_user
    if (activeTab === "groups") return d.is_group
    if (activeTab === "bots") return false // no bot flag from backend yet
    return true
  })

  const totalUnread = dialogs.reduce((sum, d) => sum + (d.unread_count ?? 0), 0)

  const tabsWithCounts = [
    { id: "all", icon: "all" as const, count: totalUnread },
    { id: "people", icon: "people" as const, count: dialogs.filter((d) => d.is_user && d.unread_count > 0).length },
    { id: "groups", icon: "groups" as const, count: dialogs.filter((d) => d.is_group && d.unread_count > 0).length },
    { id: "bots", icon: "bots" as const, count: 0 },
  ]

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

        <FilterTabs tabs={tabsWithCounts} activeTab={activeTab} onTabChange={setActiveTab} />

        {/* No account selected */}
        {!activeAccount && (
          <div className="flex flex-col items-center justify-center py-20 px-6 text-center">
            <MessageSquare className="h-16 w-16 text-gray-600 mb-4" />
            <p className="text-white font-medium text-lg mb-2">No account connected</p>
            <p className="text-gray-400 text-sm mb-6">
              Add a Telegram account to start messaging
            </p>
            <button
              onClick={() => setIsAuthFlowOpen(true)}
              className="px-6 py-3 bg-[#2AABEE] text-white rounded-xl font-medium"
            >
              Add Account
            </button>
          </div>
        )}

        {/* Loading */}
        {activeAccount && dialogsLoading && (
          <div className="flex justify-center py-20">
            <Loader2 className="h-8 w-8 text-[#2AABEE] animate-spin" />
          </div>
        )}

        {/* Chat list */}
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

        <BottomNav
          activeTab={activeNavTab}
          onTabChange={handleNavTabChange}
          unreadCount={totalUnread}
        />
      </div>
    </div>
  )
}

function DialogItem({ dialog, onClick }: { dialog: Dialog; onClick: () => void }) {
  const avatarColors = [
    "bg-pink-500", "bg-green-500", "bg-blue-500", "bg-purple-500",
    "bg-amber-500", "bg-rose-600", "bg-cyan-500", "bg-indigo-500",
  ]
  const colorIndex = Math.abs(dialog.id) % avatarColors.length
  const avatarColor = avatarColors[colorIndex]

  const lastMsgText = dialog.last_message?.text
  const lastMsgTime = dialog.last_message?.date
    ? formatDistanceToNow(new Date(dialog.last_message.date), { addSuffix: false })
    : ""

  const displayName = dialog.name || dialog.title || "Unknown"

  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-3 px-4 py-3 hover:bg-white/5 transition-colors text-left"
    >
      {/* Avatar */}
      <div
        className={cn(
          "w-12 h-12 rounded-full flex items-center justify-center text-white font-semibold text-lg flex-shrink-0",
          avatarColor,
        )}
      >
        {displayName.charAt(0).toUpperCase()}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-0.5">
          <p className="text-white font-medium text-[15px] truncate">{displayName}</p>
          <span className="text-gray-400 text-xs flex-shrink-0 ml-2">{lastMsgTime}</span>
        </div>
        <div className="flex items-center justify-between">
          <p className="text-gray-400 text-sm truncate flex-1">
            {dialog.last_message?.out && (
              <span className="text-[#2AABEE] mr-1">You:</span>
            )}
            {lastMsgText ?? (dialog.is_channel ? "Channel" : dialog.is_group ? "Group" : "")}
          </p>
          {dialog.unread_count > 0 && (
            <span className="ml-2 min-w-[20px] h-5 rounded-full bg-[#2AABEE] text-white text-xs font-bold flex items-center justify-center px-1.5 flex-shrink-0">
              {dialog.unread_count > 99 ? "99+" : dialog.unread_count}
            </span>
          )}
        </div>
      </div>
    </button>
  )
}
