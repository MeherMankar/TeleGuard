import { useState } from "react"
import { ArrowLeft, Search, Loader2, UserX } from "lucide-react"
import { cn } from "@/lib/utils"
import { useQuery } from "@tanstack/react-query"
import { contactsApi, chatsApi, type Contact } from "@/lib/api"
import { useUser } from "@/contexts/user-context"

interface ContactsListPageProps {
  isOpen: boolean
  onClose: () => void
}

const AVATAR_COLORS = [
  "bg-rose-500", "bg-amber-500", "bg-violet-500", "bg-pink-500",
  "bg-sky-500", "bg-indigo-500", "bg-emerald-500", "bg-orange-500",
  "bg-teal-500", "bg-cyan-500", "bg-lime-600", "bg-fuchsia-500",
]

function avatarColor(id: number) {
  return AVATAR_COLORS[Math.abs(id) % AVATAR_COLORS.length]
}

function formatLastSeen(ls: string | null): string {
  if (!ls) return "last seen a long time ago"
  if (ls === "online") return "online"
  if (ls === "recently") return "last seen recently"
  if (ls === "last week") return "last seen last week"
  if (ls === "last month") return "last seen last month"
  // ISO date string
  try {
    const d = new Date(ls)
    const now = new Date()
    const diffMs = now.getTime() - d.getTime()
    const diffMins = Math.floor(diffMs / 60_000)
    if (diffMins < 1) return "last seen just now"
    if (diffMins < 60) return `last seen ${diffMins}m ago`
    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `last seen ${diffHours}h ago`
    return `last seen ${d.toLocaleDateString()}`
  } catch {
    return "last seen a long time ago"
  }
}

export function ContactsListPage({ isOpen, onClose }: ContactsListPageProps) {
  const { activeAccount } = useUser()
  const [searchValue, setSearchValue] = useState("")

  const { data: contacts = [], isLoading, isError } = useQuery({
    queryKey: ["contacts", activeAccount?.name],
    queryFn: () => contactsApi.list(activeAccount!.name),
    enabled: isOpen && !!activeAccount,
    staleTime: 60_000,
  })

  const filtered = contacts.filter((c) =>
    c.name.toLowerCase().includes(searchValue.toLowerCase()) ||
    (c.username ?? "").toLowerCase().includes(searchValue.toLowerCase()) ||
    (c.phone ?? "").includes(searchValue)
  )

  return (
    <div
      style={{ zIndex: 75 }}
      className={cn(
        "fixed inset-0 bg-[#17212b] flex flex-col transition-transform duration-300 ease-in-out",
        isOpen ? "translate-x-0" : "translate-x-full"
      )}
    >
      {/* Header */}
      <header className="flex items-center gap-4 px-4 py-3 bg-[#17212b] border-b border-white/10">
        <button
          onClick={onClose}
          className="p-2 -ml-2 text-gray-400 hover:text-white transition-colors"
          aria-label="Go back"
        >
          <ArrowLeft className="h-6 w-6" />
        </button>
        <h1 className="text-xl font-medium text-white">Contacts</h1>
        {activeAccount && (
          <span className="ml-auto text-gray-500 text-xs truncate max-w-[120px]">
            {activeAccount.name}
          </span>
        )}
      </header>

      {/* Search */}
      <div className="px-4 py-3 border-b border-white/5">
        <div className="flex items-center gap-3 bg-[#1e2c3a] rounded-xl px-4 py-2.5">
          <Search className="h-4 w-4 text-gray-400 flex-shrink-0" />
          <input
            type="text"
            placeholder="Search contacts"
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
            className="flex-1 bg-transparent text-white placeholder:text-gray-500 outline-none text-sm"
          />
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto">
        {/* Loading */}
        {isLoading && (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-8 w-8 text-[#2AABEE] animate-spin" />
          </div>
        )}

        {/* Error */}
        {isError && !isLoading && (
          <div className="px-4 py-8 text-center text-red-400 text-sm">
            Failed to load contacts. Is the bot running?
          </div>
        )}

        {/* No account selected */}
        {!activeAccount && !isLoading && (
          <div className="px-4 py-8 text-center text-gray-500 text-sm">
            No account selected.
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !isError && activeAccount && filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 gap-3 text-gray-500">
            <UserX className="h-10 w-10" />
            <p className="text-sm">
              {searchValue ? "No contacts match your search" : "No contacts found"}
            </p>
          </div>
        )}

        {/* Contact count */}
        {!isLoading && !isError && contacts.length > 0 && (
          <div className="px-4 py-2">
            <span className="text-xs text-[#2AABEE] font-medium">
              {contacts.length} contact{contacts.length !== 1 ? "s" : ""}
              {searchValue && ` · ${filtered.length} match${filtered.length !== 1 ? "es" : ""}`}
            </span>
          </div>
        )}

        {/* Contact rows */}
        {filtered.map((contact) => (
          <ContactRow key={contact.id} contact={contact} accountName={activeAccount?.name ?? ""} />
        ))}
      </div>
    </div>
  )
}

function ContactRow({ contact, accountName }: { contact: Contact; accountName: string }) {
  const photoUrl = contact.has_photo && accountName
    ? chatsApi.photoUrl(accountName, contact.id)
    : null

  return (
    <div className="flex items-center gap-3 px-4 py-3 hover:bg-white/5 transition-colors cursor-pointer">
      {/* Avatar */}
      <div className={cn(
        "w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0 text-white font-bold text-base overflow-hidden",
        !photoUrl && avatarColor(contact.id)
      )}>
        {photoUrl ? (
          <img src={photoUrl} alt={contact.name} className="w-full h-full object-cover" />
        ) : (
          contact.name.charAt(0).toUpperCase()
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-white text-[15px] font-medium truncate">{contact.name}</p>
        <p className={cn(
          "text-xs truncate mt-0.5",
          contact.last_seen === "online" ? "text-[#2AABEE]" : "text-gray-500"
        )}>
          {formatLastSeen(contact.last_seen)}
        </p>
      </div>

      {/* Username badge */}
      {contact.username && (
        <span className="text-gray-500 text-xs flex-shrink-0">@{contact.username}</span>
      )}
    </div>
  )
}
