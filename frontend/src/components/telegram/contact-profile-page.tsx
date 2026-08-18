import { useState, useCallback } from "react"
import {
  ArrowLeft,
  Bell,
  BellOff,
  MessageSquare,
  Image as ImageIcon,
  Link2,
  PlayCircle,
  Loader2,
  CheckCircle2,
  Bot,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useQuery } from "@tanstack/react-query"
import { chatsApi, type Dialog, type Message } from "@/lib/api"
import { useUser } from "@/contexts/user-context"

interface ContactProfilePageProps {
  isOpen: boolean
  onClose: () => void
  dialog: Dialog
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatLastSeen(status: string | null): string {
  if (!status) return ""
  if (status === "online") return "online"
  if (status === "recently") return "last seen recently"
  if (status === "last_week") return "last seen last week"
  if (status === "last_month") return "last seen last month"
  try {
    const d = new Date(status)
    const diffMs = Date.now() - d.getTime()
    const mins = Math.floor(diffMs / 60_000)
    if (mins < 1) return "last seen just now"
    if (mins < 60) return `last seen ${mins}m ago`
    const hours = Math.floor(mins / 60)
    if (hours < 24) return `last seen ${hours}h ago`
    return `last seen ${d.toLocaleDateString()}`
  } catch {
    return ""
  }
}

const AVATAR_COLORS = [
  "bg-rose-500", "bg-amber-500", "bg-violet-500", "bg-pink-500",
  "bg-sky-500", "bg-indigo-500", "bg-emerald-500", "bg-orange-500",
  "bg-teal-500", "bg-cyan-500", "bg-lime-600", "bg-fuchsia-500",
]
function avatarColor(id: number) {
  return AVATAR_COLORS[Math.abs(id) % AVATAR_COLORS.length]
}

// ── Component ─────────────────────────────────────────────────────────────────

export function ContactProfilePage({ isOpen, onClose, dialog }: ContactProfilePageProps) {
  const { activeAccount } = useUser()
  const [activeTab, setActiveTab] = useState<"media" | "links">("media")

  // Fetch recent messages to extract real media/links
  const { data: messages = [], isLoading: loadingMsgs } = useQuery({
    queryKey: ["history", activeAccount?.name, dialog.entity_id],
    queryFn: () => chatsApi.history(activeAccount!.name, dialog.entity_id, 100),
    enabled: isOpen && !!activeAccount,
    staleTime: 60_000,
  })

  const photoUrl = dialog.has_photo && activeAccount
    ? chatsApi.photoUrl(activeAccount.name, dialog.entity_id)
    : null

  // Extract media messages
  const mediaMessages = messages.filter(
    (m) => m.media && (m.media.type === "photo" || m.media.type === "video" || m.media.type === "gif"),
  )
  const linkMessages = messages.filter(
    (m) => m.media?.type === "webpage" && m.media.url,
  )

  const handleClose = useCallback(() => onClose(), [onClose])

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={handleClose}
        style={{ zIndex: 74 }}
        className={cn(
          "fixed inset-0 bg-black/70 transition-opacity duration-300",
          isOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none",
        )}
      />

      {/* Panel */}
      <div
        style={{ zIndex: 75 }}
        className={cn(
          "fixed inset-0 bg-[#17212b] flex flex-col transition-transform duration-300 ease-in-out overflow-y-auto",
          isOpen ? "translate-x-0" : "translate-x-full",
        )}
      >
        {/* Top bar */}
        <div className="flex items-center justify-between px-2 pt-3 pb-2">
          <button onClick={handleClose} aria-label="Back" className="p-2 text-gray-400 hover:text-white">
            <ArrowLeft className="h-6 w-6" />
          </button>
        </div>

        {/* Avatar + name */}
        <div className="flex flex-col items-center pt-2 pb-5 px-4">
          <div className={cn(
            "w-32 h-32 rounded-full flex items-center justify-center text-5xl font-semibold text-white overflow-hidden flex-shrink-0",
            !photoUrl && avatarColor(dialog.entity_id),
          )}>
            {photoUrl
              ? <img src={photoUrl} alt={dialog.name} className="w-full h-full object-cover" />
              : dialog.name.charAt(0).toUpperCase()
            }
          </div>

          <div className="flex items-center gap-1.5 mt-4">
            <h1 className="text-2xl font-semibold text-white">{dialog.name}</h1>
            {dialog.verified && <CheckCircle2 className="h-5 w-5 text-sky-400 flex-shrink-0" />}
            {dialog.is_bot && <Bot className="h-4 w-4 text-gray-400 flex-shrink-0" />}
          </div>

          <p className={cn(
            "text-sm mt-1",
            dialog.status === "online" ? "text-sky-400" : "text-gray-500",
          )}>
            {dialog.is_group || dialog.is_channel
              ? dialog.participants_count != null
                ? `${dialog.participants_count.toLocaleString()} ${dialog.is_channel ? "subscribers" : "members"}`
                : ""
              : formatLastSeen(dialog.status)}
          </p>
        </div>

        {/* Action buttons */}
        <div className="grid grid-cols-3 gap-2 px-4 pb-4">
          {[
            { icon: MessageSquare, label: "Message" },
            { icon: dialog.muted ? BellOff : Bell, label: dialog.muted ? "Unmute" : "Mute" },
            { icon: Link2, label: "Share" },
          ].map(({ icon: Icon, label }) => (
            <button
              key={label}
              className="flex flex-col items-center justify-center gap-1.5 py-3 rounded-xl bg-[#242f3d] hover:bg-[#2a3847] transition-colors"
            >
              <Icon className="h-5 w-5 text-sky-400" />
              <span className="text-xs text-gray-300">{label}</span>
            </button>
          ))}
        </div>

        {/* Stats — media/links counts from real messages */}
        <div className="mx-3 rounded-xl bg-[#242f3d] overflow-hidden mb-3">
          <div className="flex items-center gap-3 px-4 py-3 border-b border-white/5">
            <ImageIcon className="h-5 w-5 text-gray-400" />
            <span className="flex-1 text-[15px] text-white">Photos & Videos</span>
            {loadingMsgs
              ? <Loader2 className="h-4 w-4 text-gray-500 animate-spin" />
              : <span className="text-[15px] text-sky-400">{mediaMessages.length}</span>
            }
          </div>
          <div className="flex items-center gap-3 px-4 py-3">
            <Link2 className="h-5 w-5 text-gray-400" />
            <span className="flex-1 text-[15px] text-white">Links</span>
            {loadingMsgs
              ? <Loader2 className="h-4 w-4 text-gray-500 animate-spin" />
              : <span className="text-[15px] text-sky-400">{linkMessages.length}</span>
            }
          </div>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-2 px-4 pb-3">
          {(["media", "links"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                "px-5 py-1.5 rounded-full text-sm font-medium transition-colors",
                activeTab === tab ? "bg-sky-500/20 text-sky-400" : "text-gray-500",
              )}
            >
              {tab === "media" ? "Media" : "Links"}
              {tab === "media" && mediaMessages.length > 0 && ` (${mediaMessages.length})`}
              {tab === "links" && linkMessages.length > 0 && ` (${linkMessages.length})`}
            </button>
          ))}
        </div>

        {/* Loading */}
        {loadingMsgs && (
          <div className="flex justify-center py-8">
            <Loader2 className="h-6 w-6 text-sky-400 animate-spin" />
          </div>
        )}

        {/* Media grid */}
        {!loadingMsgs && activeTab === "media" && (
          mediaMessages.length === 0 ? (
            <p className="text-center text-gray-500 text-sm py-8">No media found</p>
          ) : (
            <div className="grid grid-cols-3 gap-0.5 pb-6">
              {mediaMessages.slice(0, 99).map((msg) => (
                <MediaThumb key={msg.id} msg={msg} accountName={activeAccount?.name ?? ""} />
              ))}
            </div>
          )
        )}

        {/* Links list */}
        {!loadingMsgs && activeTab === "links" && (
          linkMessages.length === 0 ? (
            <p className="text-center text-gray-500 text-sm py-8">No links found</p>
          ) : (
            <ul className="divide-y divide-white/5 pb-6">
              {linkMessages.map((msg) => (
                <li key={msg.id} className="px-4 py-3">
                  <a
                    href={msg.media?.url ?? "#"}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block"
                  >
                    {msg.media?.title && (
                      <p className="text-white text-sm font-medium truncate">{msg.media.title}</p>
                    )}
                    <p className="text-sky-400 text-xs truncate mt-0.5">{msg.media?.url}</p>
                    {msg.media?.description && (
                      <p className="text-gray-500 text-xs mt-0.5 line-clamp-2">{msg.media.description}</p>
                    )}
                  </a>
                </li>
              ))}
            </ul>
          )
        )}
      </div>
    </>
  )
}

function MediaThumb({ msg, accountName }: { msg: Message; accountName: string }) {
  const isVideo = msg.media?.type === "video" || msg.media?.type === "gif"
  const thumbUrl = msg.media?.photo_id
    ? chatsApi.mediaUrl(accountName, msg.id, msg.id)
    : null

  return (
    <div className="relative aspect-square bg-[#1e2c3a] overflow-hidden">
      {thumbUrl ? (
        <img src={thumbUrl} alt="" className="w-full h-full object-cover" />
      ) : (
        <div className="w-full h-full flex items-center justify-center">
          <ImageIcon className="h-6 w-6 text-gray-600" />
        </div>
      )}
      {isVideo && msg.media?.duration && (
        <span className="absolute bottom-1.5 left-1.5 text-[11px] text-white font-medium bg-black/60 px-1.5 py-0.5 rounded flex items-center gap-0.5">
          <PlayCircle className="h-3 w-3" />
          {Math.floor((msg.media.duration ?? 0) / 60)}:{String((msg.media.duration ?? 0) % 60).padStart(2, "0")}
        </span>
      )}
    </div>
  )
}
