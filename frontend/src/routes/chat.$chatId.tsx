import { useState, useRef, useEffect, useCallback } from "react"
import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router"
import { ArrowLeft, Search, MoreVertical, Smile, Paperclip, Mic, Send, ArrowDown, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { chatsApi, messagingApi, type Message } from "@/lib/api"
import { useWsEvent } from "@/hooks/use-ws-event"
import { toast } from "sonner"
import { format } from "date-fns"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { UserProvider, useUser } from "@/contexts/user-context"
import { Toaster } from "@/components/ui/sonner"

export const Route = createFileRoute("/chat/$chatId")({
  validateSearch: (search: Record<string, unknown>) => ({
    account: (search.account as string) ?? "",
  }),
  component: ChatPageWrapper,
})

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 5_000 } },
})

function ChatPageWrapper() {
  return (
    <QueryClientProvider client={queryClient}>
      <UserProvider>
        <ChatPage />
        <Toaster />
      </UserProvider>
    </QueryClientProvider>
  )
}

function ChatPage() {
  const { chatId } = Route.useParams()
  const { account: accountName } = useSearch({ from: "/chat/$chatId" })
  const navigate = useNavigate()
  const { activeAccount } = useUser()
  const qc = useQueryClient()

  const effectiveAccount = accountName || activeAccount?.name || ""

  const [messageText, setMessageText] = useState("")
  const [showScrollBtn, setShowScrollBtn] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)

  // Fetch dialogs to get chat name
  const { data: dialogs = [] } = useQuery({
    queryKey: ["dialogs", effectiveAccount],
    queryFn: () => chatsApi.dialogs(effectiveAccount, 100),
    enabled: !!effectiveAccount,
    staleTime: 30_000,
  })

  const dialog = dialogs.find((d) => String(d.id) === chatId)

  // Fetch message history
  const { data: messages = [], isLoading } = useQuery({
    queryKey: ["messages", effectiveAccount, chatId],
    queryFn: () => chatsApi.history(effectiveAccount, parseInt(chatId), 50),
    enabled: !!effectiveAccount && !!chatId,
    staleTime: 5_000,
  })

  // Reverse messages (API returns newest first)
  const sortedMessages = [...messages].reverse()

  // Send message mutation
  const sendMutation = useMutation({
    mutationFn: (text: string) =>
      messagingApi.send(effectiveAccount, chatId, text),
    onSuccess: () => {
      setMessageText("")
      qc.invalidateQueries({ queryKey: ["messages", effectiveAccount, chatId] })
      qc.invalidateQueries({ queryKey: ["dialogs", effectiveAccount] })
      scrollToBottom()
    },
    onError: (e) => toast.error((e as Error).message),
  })

  // Live message updates via WebSocket
  useWsEvent("new_message", useCallback(() => {
    qc.invalidateQueries({ queryKey: ["messages", effectiveAccount, chatId] })
  }, [effectiveAccount, chatId, qc]))

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [sortedMessages.length])

  const handleScroll = () => {
    const el = scrollContainerRef.current
    if (!el) return
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    setShowScrollBtn(distFromBottom > 200)
  }

  const handleSend = () => {
    const text = messageText.trim()
    if (!text || sendMutation.isPending) return
    sendMutation.mutate(text)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const displayName = dialog?.name || dialog?.title || `Chat ${chatId}`

  return (
    <div className="dark">
      <div className="min-h-screen bg-background text-foreground max-w-md mx-auto relative flex flex-col">
        {/* Header */}
        <div className="sticky top-0 z-30 flex items-center gap-3 px-2 py-2 bg-card/95 backdrop-blur border-b border-border/40">
          <button
            onClick={() => navigate({ to: "/" })}
            aria-label="Back"
            className="p-1.5 text-foreground"
          >
            <ArrowLeft className="h-6 w-6" />
          </button>
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <div
              className={cn(
                "w-10 h-10 rounded-full flex items-center justify-center text-white font-semibold shrink-0",
                "bg-sky-600",
              )}
            >
              {displayName.charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0">
              <p className="text-[15px] font-semibold text-foreground truncate">{displayName}</p>
              <p className="text-xs text-muted-foreground truncate">
                {dialog?.is_group ? "group" : dialog?.is_channel ? "channel" : "private"}
              </p>
            </div>
          </div>
          <button aria-label="Search" className="p-2 text-foreground">
            <Search className="h-5 w-5" />
          </button>
          <button aria-label="More" className="p-2 text-foreground">
            <MoreVertical className="h-5 w-5" />
          </button>
        </div>

        {/* Messages */}
        <div
          ref={scrollContainerRef}
          onScroll={handleScroll}
          className="flex-1 px-3 py-4 space-y-1 bg-[oklch(0.18_0.02_260)] overflow-y-auto"
          style={{ minHeight: 0 }}
        >
          {isLoading && (
            <div className="flex justify-center py-10">
              <Loader2 className="h-6 w-6 text-primary animate-spin" />
            </div>
          )}

          {!isLoading && sortedMessages.length === 0 && (
            <p className="text-center text-sm text-muted-foreground py-10">No messages yet</p>
          )}

          {sortedMessages.map((m, i) => {
            const prev = sortedMessages[i - 1]
            const showDate =
              !prev ||
              (m.date &&
                prev.date &&
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
                <MessageBubble message={m} />
              </div>
            )
          })}

          <div ref={messagesEndRef} />
        </div>

        {/* Scroll to bottom button */}
        {showScrollBtn && (
          <button
            onClick={scrollToBottom}
            className="fixed bottom-20 right-4 w-10 h-10 rounded-full bg-card border border-border/40 flex items-center justify-center text-muted-foreground shadow-lg z-20"
          >
            <ArrowDown className="h-5 w-5" />
          </button>
        )}

        {/* Input bar */}
        <div className="sticky bottom-0 z-30 bg-card border-t border-border/40 px-2 py-2 flex items-center gap-2">
          <button className="p-2 text-muted-foreground">
            <Smile className="h-6 w-6" />
          </button>
          <textarea
            value={messageText}
            onChange={(e) => setMessageText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message"
            rows={1}
            className="flex-1 bg-transparent text-foreground text-[15px] outline-none placeholder:text-muted-foreground py-2 resize-none max-h-32"
          />
          <button className="p-2 text-muted-foreground">
            <Paperclip className="h-6 w-6" />
          </button>
          {messageText.trim() ? (
            <button
              onClick={handleSend}
              disabled={sendMutation.isPending}
              className="w-10 h-10 rounded-full bg-primary flex items-center justify-center text-primary-foreground disabled:opacity-70"
            >
              {sendMutation.isPending ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : (
                <Send className="h-5 w-5" />
              )}
            </button>
          ) : (
            <button className="w-10 h-10 rounded-full bg-primary flex items-center justify-center text-primary-foreground">
              <Mic className="h-5 w-5" />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function MessageBubble({ message: m }: { message: Message }) {
  const outgoing = m.out
  const timeStr = m.date ? format(new Date(m.date), "HH:mm") : ""

  return (
    <div className={cn("flex", outgoing ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[80%] rounded-2xl overflow-hidden",
          outgoing ? "bg-sky-600 text-white rounded-br-md" : "bg-card text-foreground rounded-bl-md",
        )}
      >
        {m.media && !m.text && (
          <div className="w-48 h-48 bg-gradient-to-br from-stone-600 to-stone-800 flex items-center justify-center">
            <span className="text-white/60 text-sm">Media</span>
          </div>
        )}
        {m.text && (
          <div className="px-3 py-2">
            <p className="text-[15px] whitespace-pre-wrap break-words">{m.text}</p>
            <div className="flex items-center justify-end gap-1 mt-0.5">
              <span className={cn("text-[11px]", outgoing ? "text-white/70" : "text-muted-foreground")}>
                {timeStr}
              </span>
              {outgoing && (
                <svg viewBox="0 0 16 16" className="h-3.5 w-3.5 text-white/80">
                  <path fill="currentColor" d="M2 8l3 3 4-5M7 11l3-5" />
                </svg>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
