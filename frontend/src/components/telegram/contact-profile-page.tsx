import { ArrowLeft, X, MoreVertical, Phone, Bell, Video, MessageSquare, AtSign, Cake, Image as ImageIcon, Link2, PlayCircle } from "lucide-react"
import { cn } from "@/lib/utils"
import type { Chat } from "@/lib/mock-data"
import { useState } from "react"

interface ContactProfilePageProps {
  isOpen: boolean
  onClose: () => void
  chat: Chat
}

function formatBirthdayShort(date?: string) {
  if (!date) return ""
  const d = new Date(date)
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
}

function calculateAge(date?: string) {
  if (!date) return 0
  const b = new Date(date)
  const t = new Date()
  let age = t.getFullYear() - b.getFullYear()
  const m = t.getMonth() - b.getMonth()
  if (m < 0 || (m === 0 && t.getDate() < b.getDate())) age--
  return age
}

const mediaTabs = [
  { id: "media", label: "Media", count: 9 },
  { id: "links", label: "Links", count: 1 },
]

const mediaThumbs = [
  { id: "1", color: "bg-rose-900", duration: "0:39" },
  { id: "2", color: "bg-purple-900", duration: null },
  { id: "3", color: "bg-indigo-900", duration: "0:09" },
  { id: "4", color: "bg-emerald-900", duration: "0:10" },
  { id: "5", color: "bg-slate-700", duration: null },
  { id: "6", color: "bg-teal-900", duration: null },
  { id: "7", color: "bg-lime-900", duration: null },
  { id: "8", color: "bg-amber-900", duration: "1:01" },
]

export function ContactProfilePage({ isOpen, onClose, chat }: ContactProfilePageProps) {
  const [activeTab, setActiveTab] = useState("media")

  return (
    <>
      <div
        onClick={onClose}
        style={{ zIndex: 60 }}
        className={cn(
          "fixed inset-0 bg-black/70 transition-opacity duration-300",
          isOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        )}
      />
      <div
        style={{ zIndex: 70 }}
        className={cn(
          "fixed top-0 right-0 h-screen w-full max-w-md bg-background flex flex-col transition-transform duration-300 ease-in-out overflow-y-auto",
          isOpen ? "translate-x-0" : "translate-x-full"
        )}
      >
        {/* Top bar */}
        <div className="flex items-center justify-between px-2 pt-3 pb-2">
          <button onClick={onClose} aria-label="Back" className="p-2 text-foreground">
            <ArrowLeft className="h-6 w-6" />
          </button>
          <button aria-label="More" className="p-2 text-foreground">
            <MoreVertical className="h-6 w-6" />
          </button>
        </div>

        {/* Avatar */}
        <div className="flex flex-col items-center pt-2 pb-5">
          <div className={cn("w-32 h-32 rounded-full flex items-center justify-center text-5xl font-semibold text-white overflow-hidden", chat.avatarColor ?? "bg-primary")}>
            {chat.name.charAt(0)}
          </div>
          <h1 className="text-2xl font-semibold text-foreground mt-4">{chat.name}</h1>
          <p className="text-sm text-muted-foreground mt-1">{chat.lastSeen ?? "last seen recently"}</p>
          {chat.userId && (
            <p className="text-sm text-muted-foreground mt-0.5">id: {chat.userId}</p>
          )}
        </div>

        {/* Action buttons */}
        <div className="grid grid-cols-4 gap-2 px-3 pb-4">
          {[
            { icon: MessageSquare, label: "Message" },
            { icon: Bell, label: "Mute" },
            { icon: Phone, label: "Call" },
            { icon: Video, label: "Video" },
          ].map(({ icon: Icon, label }) => (
            <button
              key={label}
              className="flex flex-col items-center justify-center gap-1.5 py-3 rounded-xl bg-card hover:bg-secondary transition-colors"
            >
              <Icon className="h-5 w-5 text-primary" />
              <span className="text-xs text-foreground">{label}</span>
            </button>
          ))}
        </div>

        {/* Info card */}
        <div className="mx-3 rounded-xl bg-card overflow-hidden">
          {chat.username && (
            <div className="flex items-center gap-4 px-4 py-3 border-b border-border/40">
              <div className="flex-1">
                <p className="text-[15px] text-foreground">{chat.username}</p>
                <p className="text-xs text-muted-foreground mt-0.5">Username</p>
              </div>
              <div className="grid grid-cols-2 gap-0.5 w-6 h-6">
                <div className="bg-muted-foreground rounded-sm" />
                <div className="bg-muted-foreground rounded-sm" />
                <div className="bg-muted-foreground rounded-sm" />
                <div className="bg-muted-foreground rounded-sm" />
              </div>
            </div>
          )}
          {chat.birthday && (
            <div className="flex items-center gap-4 px-4 py-3">
              <div className="flex-1">
                <p className="text-[15px] text-foreground">
                  {formatBirthdayShort(chat.birthday)}{" "}
                  <span className="text-muted-foreground">({calculateAge(chat.birthday)} years old)</span>
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">Birthday</p>
              </div>
            </div>
          )}
        </div>

        {/* Stats card */}
        <div className="mx-3 mt-3 rounded-xl bg-card overflow-hidden">
          {[
            { icon: ImageIcon, label: "Photos and videos", count: 9 },
            { icon: ImageIcon, label: "Photos", count: 5 },
            { icon: PlayCircle, label: "Videos", count: 4 },
            { icon: Link2, label: "Links", count: 1 },
          ].map(({ icon: Icon, label, count }, i, arr) => (
            <div
              key={label}
              className={cn(
                "flex items-center gap-4 px-4 py-3.5",
                i < arr.length - 1 && "border-b border-border/40"
              )}
            >
              <Icon className="h-5 w-5 text-muted-foreground" />
              <span className="flex-1 text-[15px] text-foreground">{label}</span>
              <span className="text-[15px] text-primary">{count}</span>
            </div>
          ))}
        </div>

        {/* Tabs */}
        <div className="flex items-center justify-center gap-2 mt-5 pb-3">
          {mediaTabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={cn(
                "px-5 py-1.5 rounded-full text-sm font-medium transition-colors",
                activeTab === t.id
                  ? "bg-primary/20 text-primary"
                  : "text-muted-foreground"
              )}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Media grid */}
        <div className="grid grid-cols-3 gap-0.5 pb-6">
          {mediaThumbs.map((m) => (
            <div key={m.id} className={cn("relative aspect-square", m.color)}>
              {m.duration && (
                <span className="absolute bottom-1.5 left-1.5 text-[11px] text-white font-medium bg-black/50 px-1.5 py-0.5 rounded flex items-center gap-0.5">
                  <PlayCircle className="h-3 w-3" /> {m.duration}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
    </>
  )
}
