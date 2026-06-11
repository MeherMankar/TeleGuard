import { useState, useRef, useEffect, useCallback } from "react"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import {
  ArrowLeft, Search, MoreVertical, Smile, Paperclip, Mic, Send,
  ArrowDown, Loader2, File, Music, Play, Image, Sticker, Globe,
  Pin, Eye, Forward, Reply,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { chatsApi, messagingApi, type Message, type Dialog, type InlineButton } from "@/lib/api"
import { useWsEvent } from "@/hooks/use-ws-event"
import { useUser, UserProvider } from "@/contexts/user-context"
import { toast } from "sonner"
import { format } from "date-fns"
import { Toaster } from "@/components/ui/sonner"

function safeText(v: unknown): string | null {
  if (v === null || v === undefined) return null
  if (typeof v === "string") return v
  if (typeof v === "object" && v !== null) {
    const obj = v as Record<string, unknown>
    if (typeof obj.text === "string") return obj.text
    if (typeof obj.message === "string") return obj.message
  }
  try { return String(v) } catch { return null }
}

export const Route = createFileRoute("/chat/$chatId")({
  validateSearch: (search: Record<string, unknown>) => ({
    account: (search.account as string) ?? "",
  }),
  component: ChatPageWrapper,
})

function ChatPageWrapper() {
  return (
    <UserProvider>
      <ChatPage />
      <Toaster />
    </UserProvider>
  )
}

function ChatPage() {
  const { chatId } = Route.useParams()
  const { account: accountName } = Route.useSearch()
  const navigate = useNavigate()
  const { activeAccount } = useUser()
  const qc = useQueryClient()

  const effectiveAccount = accountName || activeAccount?.name || ""

  const [messageText, setMessageText] = useState("")
  const [showScrollBtn, setShowScrollBtn] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)

  const { data: dialogs = [] } = useQuery({
    queryKey: ["dialogs", effectiveAccount],
    queryFn: () => chatsApi.dialogs(effectiveAccount, 100),
    enabled: !!effectiveAccount,
    staleTime: 30_000,
  })

  const dialog = dialogs.find((d) => String(d.id) === chatId) as Dialog | undefined

  const { data: messages = [], isLoading } = useQuery({
    queryKey: ["messages", effectiveAccount, chatId],
    queryFn: () => chatsApi.history(effectiveAccount, parseInt(chatId), 50),
    enabled: !!effectiveAccount && !!chatId,
    staleTime: 5_000,
  })

  const sortedMessages = [...messages].reverse()

  const sendMutation = useMutation({
    mutationFn: (text: string) => messagingApi.send(effectiveAccount, String(chatId), text),
    onSuccess: () => {
      setMessageText("")
      qc.invalidateQueries({ queryKey: ["messages", effectiveAccount, chatId] })
      qc.invalidateQueries({ queryKey: ["dialogs", effectiveAccount] })
      scrollToBottom()
    },
    onError: (e) => toast.error((e as Error).message),
  })

  useWsEvent("new_message", useCallback(() => {
    qc.invalidateQueries({ queryKey: ["messages", effectiveAccount, chatId] })
  }, [effectiveAccount, chatId, qc]))

  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })

  useEffect(() => { scrollToBottom() }, [sortedMessages.length])

  const handleScroll = () => {
    const el = scrollContainerRef.current
    if (!el) return
    setShowScrollBtn(el.scrollHeight - el.scrollTop - el.clientHeight > 200)
  }

  const handleSend = () => {
    const text = messageText.trim()
    if (!text || sendMutation.isPending) return
    sendMutation.mutate(text)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const displayName = dialog?.name || dialog?.title || `Chat ${chatId}`
  const isChannel = dialog?.is_channel ?? false
  const isGroup = dialog?.is_group ?? false
  const entityId = dialog?.entity_id ?? parseInt(chatId)

  // Profile photo URL (proxied through backend)
  const photoUrl = effectiveAccount && dialog?.has_photo
    ? chatsApi.photoUrl(effectiveAccount, entityId)
    : null

  return (
    <div className="dark">
      <div className="min-h-screen bg-background text-foreground max-w-md mx-auto relative flex flex-col">
        {/* Header */}
        <div className="sticky top-0 z-30 flex items-center gap-3 px-2 py-2 bg-card/95 backdrop-blur border-b border-border/40">
          <button onClick={() => navigate({ to: "/" })} aria-label="Back" className="p-1.5 text-foreground flex-shrink-0">
            <ArrowLeft className="h-6 w-6" />
          </button>
          <div className="flex items-center gap-3 flex-1 min-w-0">
            {/* Avatar — uses real photo or colored initial */}
            <EntityAvatar
              name={displayName}
              photoUrl={photoUrl}
              size={10}
              className="flex-shrink-0"
            />
            <div className="min-w-0">
              <p className="text-[15px] font-semibold text-foreground truncate">{displayName}</p>
              <p className="text-xs text-muted-foreground">
                {isChannel ? "channel" : isGroup ? "group" : "private chat"}
              </p>
            </div>
          </div>
          <button aria-label="Search" className="p-2 text-foreground flex-shrink-0"><Search className="h-5 w-5" /></button>
          <button aria-label="More" className="p-2 text-foreground flex-shrink-0"><MoreVertical className="h-5 w-5" /></button>
        </div>

        {/* Messages */}
        <div
          ref={scrollContainerRef}
          onScroll={handleScroll}
          className="flex-1 px-3 py-4 space-y-1 bg-[oklch(0.18_0.02_260)] overflow-y-auto"
          style={{ minHeight: 0 }}
        >
          {isLoading && <div className="flex justify-center py-10"><Loader2 className="h-6 w-6 text-primary animate-spin" /></div>}
          {!isLoading && sortedMessages.length === 0 && (
            <p className="text-center text-sm text-muted-foreground py-10">No messages yet</p>
          )}
          {sortedMessages.map((m, i) => {
            const prev = sortedMessages[i - 1]
            const showDate = !prev || (m.date && prev.date &&
              new Date(m.date).toDateString() !== new Date(prev.date).toDateString())
            return (
              <div key={m.id}>
                {showDate && m.date && (
                  <div className="flex justify-center my-3">
                    <span className="bg-black/30 text-white/70 text-xs px-3 py-1 rounded-full">
                      {format(new Date(m.date), "MMMM d, yyyy")}
                    </span>
                  </div>
                )}
                <MessageBubble
                  message={m}
                  accountName={effectiveAccount}
                  chatId={parseInt(chatId)}
                  isChannel={isChannel}
                />
              </div>
            )
          })}
          <div ref={messagesEndRef} />
        </div>

        {showScrollBtn && (
          <button
            onClick={scrollToBottom}
            className="fixed bottom-20 right-4 w-10 h-10 rounded-full bg-card border border-border/40 flex items-center justify-center text-muted-foreground shadow-lg z-20"
          >
            <ArrowDown className="h-5 w-5" />
          </button>
        )}

        {/* Input — hidden for channels */}
        {!isChannel && (
          <div className="sticky bottom-0 z-30 bg-card border-t border-border/40 px-2 py-2 flex items-center gap-2">
            <button className="p-2 text-muted-foreground"><Smile className="h-6 w-6" /></button>
            <textarea
              value={messageText}
              onChange={(e) => setMessageText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Message"
              rows={1}
              className="flex-1 bg-transparent text-foreground text-[15px] outline-none placeholder:text-muted-foreground py-2 resize-none max-h-32"
            />
            <button className="p-2 text-muted-foreground"><Paperclip className="h-6 w-6" /></button>
            {messageText.trim() ? (
              <button
                onClick={handleSend}
                disabled={sendMutation.isPending}
                className="w-10 h-10 rounded-full bg-primary flex items-center justify-center text-primary-foreground disabled:opacity-70"
              >
                {sendMutation.isPending ? <Loader2 className="h-5 w-5 animate-spin" /> : <Send className="h-5 w-5" />}
              </button>
            ) : (
              <button className="w-10 h-10 rounded-full bg-primary flex items-center justify-center text-primary-foreground">
                <Mic className="h-5 w-5" />
              </button>
            )}
          </div>
        )}
        {isChannel && (
          <div className="sticky bottom-0 z-30 bg-card border-t border-border/40 px-4 py-3 flex items-center justify-center">
            <p className="text-muted-foreground text-sm">Channel — read only</p>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Entity Avatar ────────────────────────────────────────────────────────────

function EntityAvatar({
  name,
  photoUrl,
  size = 10,
  className,
}: {
  name: string
  photoUrl: string | null
  size?: number
  className?: string
}) {
  const [imgError, setImgError] = useState(false)
  const initial = (name || "?").charAt(0).toUpperCase()
  const sizeClass = `w-${size} h-${size}`

  const colors = [
    "bg-pink-500", "bg-green-500", "bg-blue-600", "bg-purple-500",
    "bg-amber-500", "bg-rose-600", "bg-cyan-600", "bg-indigo-500",
  ]
  const color = colors[initial.charCodeAt(0) % colors.length]

  if (photoUrl && !imgError) {
    return (
      <img
        src={photoUrl}
        alt={name}
        onError={() => setImgError(true)}
        className={cn(`${sizeClass} rounded-full object-cover`, className)}
      />
    )
  }

  return (
    <div className={cn(`${sizeClass} rounded-full flex items-center justify-center text-white font-semibold`, color, className)}>
      {initial}
    </div>
  )
}

// ── Message Bubble ───────────────────────────────────────────────────────────

function MessageBubble({
  message: m,
  accountName,
  chatId,
  isChannel,
}: {
  message: Message
  accountName: string
  chatId: number
  isChannel: boolean
}) {
  const outgoing = m.out
  const timeStr = m.date ? format(new Date(m.date), "HH:mm") : ""
  const mediaUrl = m.media?.id
    ? chatsApi.mediaUrl(accountName, chatId, m.id)
    : null

  return (
    <div className={cn("flex flex-col", outgoing ? "items-end" : "items-start")}>
      {/* Sender name for groups */}
      {!outgoing && m.sender_name && typeof m.sender_name === "string" && !isChannel && (
        <p className="text-xs font-medium text-sky-400 ml-2 mb-0.5">{safeText(m.sender_name)}</p>
      )}

      {/* Forwarded header */}
      {m.forward && (
        <div className={cn("flex items-center gap-1 text-xs text-muted-foreground mb-0.5",
          outgoing ? "mr-2" : "ml-2")}>
          <Forward className="h-3 w-3" />
          <span>Forwarded{m.forward.from_name ? ` from ${m.forward.from_name}` : ""}</span>
        </div>
      )}

      {/* Pinned indicator */}
      {m.pinned && (
        <div className={cn("flex items-center gap-1 text-xs text-amber-400 mb-0.5",
          outgoing ? "mr-2" : "ml-2")}>
          <Pin className="h-3 w-3" />
          <span>Pinned</span>
        </div>
      )}

      <div className={cn(
        "max-w-[85%] rounded-2xl overflow-hidden",
        outgoing ? "bg-sky-700 text-white rounded-br-sm" : "bg-card text-foreground rounded-bl-sm",
      )}>
        {/* Reply context */}
        {m.reply && (
          <div className={cn(
            "border-l-2 border-sky-400 pl-2 py-1 mx-3 mt-2 text-xs",
            outgoing ? "text-white/70" : "text-muted-foreground",
          )}>
            <div className="flex items-center gap-1 mb-0.5">
              <Reply className="h-3 w-3" />
              {m.reply.sender_id && <span className="font-medium">Reply</span>}
            </div>
            {m.reply.text && typeof m.reply.text === "string" && <p className="truncate">{safeText(m.reply.text)}</p>}
            {m.reply.media_type && !m.reply.text && (
              <p className="capitalize">{m.reply.media_type}</p>
            )}
          </div>
        )}

        {/* Media */}
        {m.media && m.media.type !== "webpage" && (
          <MediaBlock media={m.media} mediaUrl={mediaUrl} outgoing={outgoing} />
        )}

        {/* Text */}
        {m.text && typeof m.text === "string" && (
          <div className="px-3 py-2">
            {/* Webpage preview above text */}
            {m.media?.type === "webpage" && m.media.url && (
              <WebPagePreview media={m.media} outgoing={outgoing} />
            )}
            <p className="text-[15px] whitespace-pre-wrap break-words leading-snug">{safeText(m.text)}</p>
            <MessageMeta time={timeStr} outgoing={outgoing} views={m.views} />
          </div>
        )}

        {/* Media-only (no text) meta */}
        {!m.text && m.media && (
          <div className="px-3 pb-2">
            <MessageMeta time={timeStr} outgoing={outgoing} views={m.views} />
          </div>
        )}

        {/* No content at all */}
        {!m.text && !m.media && (
          <div className="px-3 py-2">
            <p className="text-[13px] italic text-muted-foreground">Unsupported message</p>
            <MessageMeta time={timeStr} outgoing={outgoing} views={m.views} />
          </div>
        )}
      </div>

      {/* Inline buttons */}
      {m.buttons && m.buttons.length > 0 && (
        <InlineKeyboard buttons={m.buttons} outgoing={outgoing} />
      )}
    </div>
  )
}

// ── Media block ───────────────────────────────────────────────────────────────

function MediaBlock({
  media,
  mediaUrl,
  outgoing,
}: {
  media: NonNullable<Message["media"]>
  mediaUrl: string | null
  outgoing: boolean
}) {
  const [imgError, setImgError] = useState(false)

  // Photo
  if (media.type === "photo") {
    return (
      <div className="relative">
        {mediaUrl && !imgError ? (
          <img
            src={mediaUrl}
            alt="Photo"
            onError={() => setImgError(true)}
            className="w-full max-h-80 object-cover"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-48 bg-gradient-to-br from-slate-700 to-slate-900 flex items-center justify-center">
            <Image className="h-10 w-10 text-white/40" />
          </div>
        )}
        {media.has_spoiler && (
          <div className="absolute inset-0 backdrop-blur-xl bg-black/40 flex items-center justify-center">
            <p className="text-white text-sm font-medium">Spoiler</p>
          </div>
        )}
      </div>
    )
  }

  // Video / Round video
  if (media.type === "video") {
    return (
      <div className={cn(
        "relative bg-gradient-to-br from-slate-700 to-slate-900",
        media.round ? "w-40 h-40 rounded-full overflow-hidden mx-auto" : "w-full h-52",
      )}>
        {mediaUrl && !imgError ? (
          <img
            src={mediaUrl}
            alt="Video thumbnail"
            onError={() => setImgError(true)}
            className="w-full h-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Play className="h-10 w-10 text-white/40" />
          </div>
        )}
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-12 h-12 rounded-full bg-black/50 flex items-center justify-center">
            <Play className="h-6 w-6 text-white fill-white ml-0.5" />
          </div>
        </div>
        {media.duration != null && (
          <div className="absolute bottom-1.5 right-2 bg-black/60 text-white text-xs px-1.5 py-0.5 rounded">
            {formatDuration(media.duration)}
          </div>
        )}
        {media.has_spoiler && (
          <div className="absolute inset-0 backdrop-blur-xl bg-black/40 flex items-center justify-center">
            <p className="text-white text-sm font-medium">Spoiler</p>
          </div>
        )}
      </div>
    )
  }

  // GIF
  if (media.type === "gif") {
    return (
      <div className="relative w-full h-40 bg-gradient-to-br from-slate-700 to-slate-900 flex items-center justify-center">
        {mediaUrl && !imgError ? (
          <img src={mediaUrl} alt="GIF" onError={() => setImgError(true)} className="w-full h-full object-cover" loading="lazy" />
        ) : (
          <Play className="h-8 w-8 text-white/40" />
        )}
        <span className="absolute bottom-1.5 left-2 bg-black/60 text-white text-[10px] font-bold px-1.5 py-0.5 rounded">GIF</span>
      </div>
    )
  }

  // Sticker
  if (media.type === "sticker") {
    return (
      <div className="px-3 py-2 flex items-center gap-2">
        <Sticker className="h-5 w-5 text-muted-foreground" />
        <span className="text-sm text-muted-foreground">
          Sticker {media.emoji || ""}
        </span>
      </div>
    )
  }

  // Voice / Audio
  if (media.type === "voice" || media.type === "audio") {
    return (
      <div className="px-3 py-2 flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
          <Music className="h-5 w-5 text-primary" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">
            {media.type === "voice" ? "Voice message" : media.title || "Audio"}
          </p>
          {media.duration != null && (
            <p className="text-xs text-muted-foreground">{formatDuration(media.duration)}</p>
          )}
        </div>
      </div>
    )
  }

  // File
  if (media.type === "file") {
    return (
      <div className="px-3 py-2 flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center flex-shrink-0">
          <File className="h-5 w-5 text-primary" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">{media.filename || "File"}</p>
          {media.size != null && (
            <p className="text-xs text-muted-foreground">{formatFileSize(media.size)}</p>
          )}
        </div>
      </div>
    )
  }

  return null
}

// ── Web page preview ──────────────────────────────────────────────────────────

function WebPagePreview({ media, outgoing }: { media: NonNullable<Message["media"]>; outgoing: boolean }) {
  return (
    <div className={cn(
      "border-l-2 border-sky-400 pl-2 mb-2 text-xs",
      outgoing ? "text-white/80" : "text-muted-foreground",
    )}>
      {media.site_name && <p className="font-semibold text-sky-400">{media.site_name}</p>}
      {media.title && <p className="font-medium">{media.title}</p>}
      {media.description && <p className="line-clamp-2 opacity-80">{media.description}</p>}
      {media.url && (
        <a href={media.url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-sky-400 hover:underline mt-0.5">
          <Globe className="h-3 w-3" />{media.url.replace(/^https?:\/\//, "").split("/")[0]}
        </a>
      )}
    </div>
  )
}

// ── Inline keyboard ───────────────────────────────────────────────────────────

function InlineKeyboard({ buttons, outgoing }: { buttons: InlineButton[][]; outgoing: boolean }) {
  return (
    <div className={cn("mt-1 space-y-1 w-full max-w-[85%]", outgoing ? "self-end" : "self-start")}>
      {buttons.map((row, ri) => (
        <div key={ri} className="flex gap-1">
          {row.map((btn, bi) => (
            <button
              key={bi}
              onClick={() => btn.url && window.open(btn.url, "_blank")}
              className={cn(
                "flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-colors text-center",
                btn.url
                  ? "bg-sky-600/30 text-sky-300 hover:bg-sky-600/50 border border-sky-600/40"
                  : "bg-white/10 text-foreground hover:bg-white/15 border border-white/10",
              )}
            >
              {btn.text}
            </button>
          ))}
        </div>
      ))}
    </div>
  )
}

// ── Message meta (time + checkmarks + views) ──────────────────────────────────

function MessageMeta({ time, outgoing, views }: { time: string; outgoing: boolean; views?: number | null }) {
  return (
    <div className="flex items-center justify-end gap-1.5 mt-0.5">
      {views != null && (
        <span className={cn("text-[10px] flex items-center gap-0.5", outgoing ? "text-white/60" : "text-muted-foreground")}>
          <Eye className="h-3 w-3" />{formatViews(views)}
        </span>
      )}
      <span className={cn("text-[11px]", outgoing ? "text-white/70" : "text-muted-foreground")}>{time}</span>
      {outgoing && (
        <svg viewBox="0 0 16 16" className="h-3.5 w-3.5 text-white/80 flex-shrink-0">
          <path fill="currentColor" d="M2 8l3 3 4-5M7 11l3-5" />
        </svg>
      )}
    </div>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, "0")}`
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function formatViews(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}
