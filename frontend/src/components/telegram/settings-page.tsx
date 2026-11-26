import { useRef, useState } from "react"
import {
  ArrowLeft,
  Camera,
  ChevronRight,
  Settings as SettingsIcon,
  User as UserIcon,
  MessageCircle,
  KeyRound,
  Bell,
  Folder,
  Monitor,
  Globe,
  MessageSquare,
  HelpCircle,
  Lightbulb,
  ShieldCheck,
  ExternalLink,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useUser } from "@/contexts/user-context"
import { EditProfilePage } from "./edit-profile-page"
import { SessionManagerPage } from "./session-manager-page"
import { PrivacySecurityPage } from "./privacy-security-page"
import { AccountSettingsPage } from "./account-settings-page"
import { ChatFoldersPage } from "./chat-folders-page"

interface SettingsPageProps {
  isOpen: boolean
  onClose: () => void
}

type Row = {
  icon: typeof SettingsIcon
  label: string
  subtitle?: string
}

const mainItems: Row[] = [
  { icon: UserIcon, label: "Account", subtitle: "Number, username, bio" },
  {
    icon: MessageCircle,
    label: "Chat Settings",
    subtitle: "Wallpaper, night mode, animations",
  },
  {
    icon: KeyRound,
    label: "Privacy & Security",
    subtitle: "Last seen, devices, passkeys",
  },
  { icon: Folder, label: "Chat Folders", subtitle: "Sort chats into folders" },
  { icon: Monitor, label: "Devices", subtitle: "Manage connected devices" },
  { icon: Globe, label: "Language", subtitle: "English" },
]

const helpItems: Row[] = [
  { icon: MessageSquare, label: "Ask a question" },
  { icon: HelpCircle, label: "Telegram FAQ" },
  { icon: Lightbulb, label: "Telegram features" },
  { icon: ShieldCheck, label: "Privacy policy" },
]

function SectionCard({ children, label }: { children: React.ReactNode; label?: string }) {
  return (
    <div className="mx-3 mt-4 overflow-hidden rounded-xl border border-border/50 bg-card">
      {label && (
        <p className="px-4 pb-1 pt-3 text-[13px] font-medium text-muted-foreground">{label}</p>
      )}
      {children}
    </div>
  )
}

function SettingsRow({ row, last, onClick }: { row: Row; last?: boolean; onClick?: () => void }) {
  const Icon = row.icon
  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full flex items-center gap-3 px-4 py-2 hover:bg-secondary/30 active:bg-secondary/50 transition-colors text-left",
        !last && "border-b border-border/30",
      )}
    >
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-secondary">
        <Icon className="h-4 w-4 text-muted-foreground" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[15px] text-foreground leading-tight">{row.label}</p>
        {row.subtitle && (
          <p className="text-[13px] text-muted-foreground mt-0.5 truncate">{row.subtitle}</p>
        )}
      </div>
      <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
    </button>
  )
}

function SettingsSubPage({
  title,
  isOpen,
  onClose,
}: {
  title: string
  isOpen: boolean
  onClose: () => void
}) {
  return (
    <div
      style={{ zIndex: 90 }}
      className={cn(
        "tg-screen fixed inset-0 flex flex-col bg-background transition-transform duration-300 ease-in-out",
        isOpen ? "translate-x-0" : "translate-x-full",
      )}
    >
      <div className="sticky top-0 z-10 flex items-center gap-3 px-2 py-3 bg-card/95 backdrop-blur border-b border-border/40">
        <button onClick={onClose} aria-label="Back" className="p-2 text-foreground">
          <ArrowLeft className="h-6 w-6" />
        </button>
        <h1 className="flex-1 text-[18px] font-semibold text-foreground">{title}</h1>
      </div>
      <div className="flex-1 flex flex-col items-center justify-center gap-4 p-8 text-center">
        <ExternalLink className="h-10 w-10 text-muted-foreground" />
        <p className="text-muted-foreground text-sm leading-relaxed">
          <strong className="text-foreground">{title}</strong> settings are managed in the official
          Telegram app and cannot be changed here.
        </p>
      </div>
    </div>
  )
}

export function SettingsPage({ isOpen, onClose }: SettingsPageProps) {
  const { profile, setAvatarUrl } = useUser()
  const avatarInputRef = useRef<HTMLInputElement>(null)
  const [activeSub, setActiveSub] = useState<string | null>(null)
  const [isEditProfileOpen, setEditProfileOpen] = useState(false)
  const [isDevicesOpen, setIsDevicesOpen] = useState(false)
  const [isPrivacySecurityOpen, setIsPrivacySecurityOpen] = useState(false)
  const [isAccountSettingsOpen, setIsAccountSettingsOpen] = useState(false)
  const [isChatFoldersOpen, setIsChatFoldersOpen] = useState(false)

  function openRow(label: string) {
    if (label === "Account") {
      setIsAccountSettingsOpen(true)
    } else if (label === "Devices") {
      setIsDevicesOpen(true)
    } else if (label === "Privacy & Security") {
      setIsPrivacySecurityOpen(true)
    } else if (label === "Chat Folders") {
      setIsChatFoldersOpen(true)
    } else {
      setActiveSub(label)
    }
  }

  function handleAvatarChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setAvatarUrl(URL.createObjectURL(file))
  }

  return (
    <div
      style={{ zIndex: 80 }}
      className={cn(
        "tg-screen fixed inset-0 flex flex-col bg-background transition-transform duration-300 ease-in-out",
        isOpen ? "translate-x-0" : "translate-x-full",
      )}
    >
      {/* Top bar */}
      <div className="sticky top-0 z-10 flex min-h-14 items-center gap-3 border-b border-border/40 bg-background px-2 py-2">
        <button onClick={onClose} aria-label="Back" className="p-2 text-foreground">
          <ArrowLeft className="h-6 w-6" />
        </button>
        <h1 className="flex-1 text-lg font-medium text-foreground">Settings</h1>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto pb-8">
        {/* Profile hero */}
        <div
          className="flex flex-col items-center pt-2 pb-6 cursor-pointer"
          onClick={() => setEditProfileOpen(true)}
        >
          <div className="relative">
            <div className="flex h-24 w-24 items-center justify-center overflow-hidden rounded-full bg-[#2AABEE] text-3xl font-medium text-white">
              {profile.avatarUrl ? (
                <img src={profile.avatarUrl} alt="Avatar" className="w-full h-full object-cover" />
              ) : (
                <span>{profile.name.charAt(0)}</span>
              )}
            </div>
            <button
              type="button"
              onClick={() => avatarInputRef.current?.click()}
              aria-label="Change avatar"
              className="absolute -bottom-1 right-0 w-9 h-9 rounded-full bg-sky-500 border-[3px] border-background flex items-center justify-center"
            >
              <Camera className="h-4 w-4 text-white" />
            </button>
            <input
              ref={avatarInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={handleAvatarChange}
            />
          </div>
          <h2 className="mt-4 text-xl font-medium text-foreground">{profile.name}</h2>
          <p className="text-[15px] text-muted-foreground mt-0.5">{profile.username}</p>
        </div>

        {/* Main settings */}
        <SectionCard>
          {mainItems.map((r, i) => (
            <SettingsRow
              key={r.label}
              row={r}
              last={i === mainItems.length - 1}
              onClick={() => openRow(r.label)}
            />
          ))}
        </SectionCard>

        {/* Help */}
        <SectionCard label="Help">
          {helpItems.map((r, i) => (
            <SettingsRow
              key={r.label}
              row={r}
              last={i === helpItems.length - 1}
              onClick={() => openRow(r.label)}
            />
          ))}
        </SectionCard>

        {/* Footer */}
        <div className="text-center mt-6 px-4">
          <p className="text-[13px] text-muted-foreground">TeleGuard</p>
          <p className="text-[13px] text-muted-foreground">v2.0.0</p>
        </div>
      </div>

      <EditProfilePage
        isOpen={isEditProfileOpen}
        onClose={() => setEditProfileOpen(false)}
        onBack={() => setEditProfileOpen(false)}
      />
      <AccountSettingsPage
        isOpen={isAccountSettingsOpen}
        onClose={() => setIsAccountSettingsOpen(false)}
      />
      <SessionManagerPage isOpen={isDevicesOpen} onClose={() => setIsDevicesOpen(false)} />
      <PrivacySecurityPage
        isOpen={isPrivacySecurityOpen}
        onClose={() => setIsPrivacySecurityOpen(false)}
      />
      <ChatFoldersPage isOpen={isChatFoldersOpen} onClose={() => setIsChatFoldersOpen(false)} />
      <SettingsSubPage
        title={activeSub ?? ""}
        isOpen={activeSub !== null}
        onClose={() => setActiveSub(null)}
      />
    </div>
  )
}
