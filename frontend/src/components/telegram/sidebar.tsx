import { useEffect, useState } from "react"
import {
  X,
  UserCircle2,
  Users,
  BookMarked,
  Phone,
  Settings,
  Megaphone,
  Plus,
  Shield,
  Skull,
  Trash2,
  Zap,
  KeyRound,
  LayoutDashboard,
  Globe,
  ChevronDown,
  LogOut,
  Check,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useUser } from "@/contexts/user-context"
import { authStore } from "@/store/auth"
import { useAuth } from "@/hooks/use-auth"

interface SidebarProps {
  isOpen: boolean
  onClose: () => void
  onProfileClick: () => void
  onAddAccountClick: () => void
  onSettingsClick: () => void
  onContactsClick: () => void
  onProtectionManagerClick: () => void
  onSpamMasterClick: () => void
  onCleanupClick: () => void
  onAutomationClick: () => void
  onSessionManagerClick: () => void
  onDashboardClick: () => void
  onProxyManagerClick: () => void
}

const navItems = [
  { icon: Plus, label: "Add Account", action: "add_account" },
  { icon: LayoutDashboard, label: "Dashboard", action: "dashboard" },
  { icon: UserCircle2, label: "My Profile", action: "profile" },
  { icon: Users, label: "Contacts", action: "contacts" },
  { icon: BookMarked, label: "Saved Messages", action: null },
  { icon: Phone, label: "Calls", action: null },
  { icon: Settings, label: "Settings", action: "settings" },
  { icon: Shield, label: "Protection Manager", action: "protection" },
  { icon: Skull, label: "Spam Master", action: "spam" },
  { icon: Trash2, label: "Cleanup", action: "cleanup" },
  { icon: Zap, label: "Automation", action: "automation" },
  { icon: KeyRound, label: "Session Manager", action: "sessions" },
  { icon: Globe, label: "Proxy Manager", action: "proxy" },
  { icon: Megaphone, label: "New Channel", action: null },
]

export function Sidebar({
  isOpen,
  onClose,
  onProfileClick,
  onAddAccountClick,
  onSettingsClick,
  onContactsClick,
  onProtectionManagerClick,
  onSpamMasterClick,
  onCleanupClick,
  onAutomationClick,
  onSessionManagerClick,
  onDashboardClick,
  onProxyManagerClick,
}: SidebarProps) {
  const { profile, accounts, activeAccount, setActiveAccount } = useUser()
  const { user } = useAuth()
  const [showAccountSwitcher, setShowAccountSwitcher] = useState(false)

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden"
    } else {
      document.body.style.overflow = ""
    }
    return () => {
      document.body.style.overflow = ""
    }
  }, [isOpen])

  const handleAction = (action: string | null) => {
    if (!action) return
    onClose()
    switch (action) {
      case "add_account": onAddAccountClick(); break
      case "profile": onProfileClick(); break
      case "settings": onSettingsClick(); break
      case "contacts": onContactsClick(); break
      case "protection": onProtectionManagerClick(); break
      case "spam": onSpamMasterClick(); break
      case "cleanup": onCleanupClick(); break
      case "automation": onAutomationClick(); break
      case "sessions": onSessionManagerClick(); break
      case "dashboard": onDashboardClick(); break
      case "proxy": onProxyManagerClick(); break
    }
  }

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        className={cn(
          "fixed inset-0 z-40 bg-black/70 transition-opacity duration-300",
          isOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none",
        )}
        aria-hidden="true"
      />

      {/* Drawer */}
      <aside
        aria-label="Navigation menu"
        className={cn(
          "fixed top-0 left-0 z-50 h-screen w-80 flex flex-col bg-card text-card-foreground shadow-2xl transition-transform duration-300 ease-in-out",
          isOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        {/* Profile Header */}
        <div className="relative bg-primary px-6 pt-8 pb-4">
          <button
            onClick={onClose}
            aria-label="Close menu"
            className="absolute top-5 right-5 p-1 text-primary-foreground/80 hover:text-primary-foreground transition-colors"
          >
            <X className="h-6 w-6" />
          </button>

          {/* Avatar */}
          <div className="w-16 h-16 rounded-full bg-gradient-to-br from-sky-400 to-blue-600 flex items-center justify-center text-2xl font-bold text-white mb-3 flex-shrink-0 overflow-hidden">
            {profile.avatarUrl ? (
              <img src={profile.avatarUrl} alt="Avatar" className="w-full h-full object-cover" />
            ) : (
              <span>{(profile.name || "T").charAt(0).toUpperCase()}</span>
            )}
          </div>

          <p className="font-semibold text-primary-foreground text-base leading-tight">
            {profile.name}
          </p>
          {profile.username && (
            <p className="text-primary-foreground/70 text-sm mt-0.5">{profile.username}</p>
          )}

          {/* Account Switcher */}
          {accounts.length > 0 && (
            <button
              onClick={() => setShowAccountSwitcher(!showAccountSwitcher)}
              className="flex items-center gap-1 mt-2 text-primary-foreground/70 hover:text-primary-foreground transition-colors"
            >
              <span className="text-xs">{accounts.length} account{accounts.length !== 1 ? "s" : ""}</span>
              <ChevronDown
                className={cn(
                  "h-3.5 w-3.5 transition-transform",
                  showAccountSwitcher && "rotate-180",
                )}
              />
            </button>
          )}

          {/* Account list */}
          {showAccountSwitcher && accounts.length > 0 && (
            <div className="mt-2 space-y-1">
              {accounts.map((acc) => (
                <button
                  key={acc.id}
                  onClick={() => {
                    setActiveAccount(acc)
                    setShowAccountSwitcher(false)
                  }}
                  className="w-full flex items-center gap-2 py-1.5 px-2 rounded-lg hover:bg-white/10 transition-colors text-left"
                >
                  <div className="w-7 h-7 rounded-full bg-white/20 flex items-center justify-center text-xs font-bold text-white flex-shrink-0">
                    {(acc.name || acc.phone || "?").charAt(0).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-primary-foreground text-xs font-medium truncate">
                      {acc.name || acc.phone}
                    </p>
                    {acc.phone && acc.name !== acc.phone && (
                      <p className="text-primary-foreground/60 text-[10px] truncate">{acc.phone}</p>
                    )}
                  </div>
                  {activeAccount?.id === acc.id && (
                    <Check className="h-3.5 w-3.5 text-primary-foreground/80 flex-shrink-0" />
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Nav Items */}
        <nav className="flex-1 overflow-y-auto py-1">
          <ul role="list">
            {navItems.map(({ icon: Icon, label, action }) => (
              <li key={label}>
                <button
                  onClick={() => handleAction(action)}
                  className={cn(
                    "w-full flex items-center gap-4 px-6 py-3.5 hover:bg-secondary/50 transition-colors group active:bg-secondary/70",
                    !action && "opacity-50 cursor-default",
                  )}
                >
                  <Icon className="h-5 w-5 text-[#2AABEE] transition-colors flex-shrink-0" />
                  <span className="flex-1 text-left text-[15px] text-foreground font-medium">
                    {label}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </nav>

        {/* Logout */}
        <div className="border-t border-border/40 p-2">
          <button
            onClick={() => {
              onClose()
              authStore.logout()
            }}
            className="w-full flex items-center gap-4 px-4 py-3 text-destructive hover:bg-destructive/10 rounded-lg transition-colors"
          >
            <LogOut className="h-5 w-5 flex-shrink-0" />
            <span className="text-[15px] font-medium">Logout</span>
          </button>
        </div>
      </aside>
    </>
  )
}
