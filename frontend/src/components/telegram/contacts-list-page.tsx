import { useEffect, useState } from "react"
import { ArrowLeft, Search, Users, Megaphone, User, UserPlus } from "lucide-react"
import { cn } from "@/lib/utils"

interface Contact {
  id: string
  name: string
  avatar?: string
  avatarColor: string
  lastSeen: string
  hasContactIcon?: boolean
}

const mockContacts: Contact[] = [
  { id: "1", name: "Saurabh Mule", avatarColor: "bg-rose-500", lastSeen: "last seen at 3:52 PM", hasContactIcon: true },
  { id: "2", name: "Room Kaka", avatarColor: "bg-amber-600", lastSeen: "last seen at 3:32 PM", hasContactIcon: true },
  { id: "3", name: "Baba Bada Lundeswar", avatarColor: "bg-violet-500", lastSeen: "last seen at 3:05 PM" },
  { id: "4", name: "Somya", avatarColor: "bg-pink-500", lastSeen: "last seen at 3:04 PM", hasContactIcon: true },
  { id: "5", name: "Wasif Shaikh Mca", avatarColor: "bg-sky-500", lastSeen: "last seen at 3:00 PM" },
  { id: "6", name: "Abhi Da", avatarColor: "bg-indigo-500", lastSeen: "last seen at 2:44 PM" },
  { id: "7", name: "Pratik Dada", avatarColor: "bg-emerald-500", lastSeen: "last seen at 2:26 PM" },
  { id: "8", name: "Bhavesh Hood", avatarColor: "bg-orange-500", lastSeen: "last seen at 2:17 PM", hasContactIcon: true },
  { id: "9", name: "Akolkar", avatarColor: "bg-teal-500", lastSeen: "last seen at 1:54 PM", hasContactIcon: true },
  { id: "10", name: "Abhi Da", avatarColor: "bg-rose-400", lastSeen: "last seen at 1:53 PM", hasContactIcon: true },
]

interface ContactsListPageProps {
  isOpen: boolean
  onClose: () => void
}

export function ContactsListPage({ isOpen, onClose }: ContactsListPageProps) {
  const [searchValue, setSearchValue] = useState("")
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden"
      // Small delay to trigger animation
      requestAnimationFrame(() => {
        setIsVisible(true)
      })
    } else {
      setIsVisible(false)
      document.body.style.overflow = ""
    }
    return () => {
      document.body.style.overflow = ""
    }
  }, [isOpen])

  const filteredContacts = mockContacts.filter((contact) =>
    contact.name.toLowerCase().includes(searchValue.toLowerCase())
  )

  if (!isOpen) return null

  return (
    <div
      className={cn(
        "fixed inset-0 z-50 bg-background transition-transform duration-300 ease-out",
        isVisible ? "translate-x-0" : "translate-x-full"
      )}
    >
      {/* Header */}
      <header className="flex items-center gap-4 px-4 py-3 bg-primary text-primary-foreground">
        <button
          onClick={onClose}
          className="p-2 -ml-2 hover:bg-white/10 rounded-full transition-colors"
          aria-label="Go back"
        >
          <ArrowLeft className="h-6 w-6" />
        </button>
        <h1 className="text-xl font-medium">New Message</h1>
        <div className="flex-1" />
        <button className="p-2 hover:bg-white/10 rounded-full transition-colors">
          <svg className="h-6 w-6" viewBox="0 0 24 24" fill="currentColor">
            <path d="M3 18h6v-2H3v2zM3 6v2h18V6H3zm0 7h12v-2H3v2z" />
          </svg>
        </button>
      </header>

      {/* Search Bar */}
      <div className="px-4 py-3 bg-background">
        <div className="flex items-center gap-3 bg-secondary/50 rounded-full px-4 py-2.5">
          <Search className="h-5 w-5 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search Contacts"
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
            className="flex-1 bg-transparent text-foreground placeholder:text-muted-foreground outline-none text-[15px]"
          />
        </div>
      </div>

      {/* Actions */}
      <div className="bg-card border-b border-border/30">
        <button className="w-full flex items-center gap-4 px-5 py-4 hover:bg-secondary/30 transition-colors">
          <div className="w-12 h-12 rounded-full bg-primary flex items-center justify-center">
            <Users className="h-6 w-6 text-primary-foreground" />
          </div>
          <span className="text-[15px] text-foreground font-medium">New Group</span>
        </button>
        <button className="w-full flex items-center gap-4 px-5 py-4 hover:bg-secondary/30 transition-colors">
          <div className="w-12 h-12 rounded-full bg-primary flex items-center justify-center">
            <Megaphone className="h-6 w-6 text-primary-foreground" />
          </div>
          <span className="text-[15px] text-foreground font-medium">New Channel</span>
        </button>
      </div>

      {/* Contacts List */}
      <div className="flex-1 overflow-y-auto">
        {/* Sort Label */}
        <div className="px-5 py-3">
          <span className="text-sm text-primary font-medium">Sorted by last seen time</span>
        </div>

        {/* Contact Items */}
        <div className="divide-y divide-border/20">
          {filteredContacts.map((contact) => (
            <button
              key={contact.id}
              className="w-full flex items-center gap-4 px-5 py-3 hover:bg-secondary/30 transition-colors"
            >
              {/* Avatar */}
              <div
                className={cn(
                  "w-12 h-12 rounded-full flex items-center justify-center text-white font-semibold text-lg flex-shrink-0",
                  contact.avatarColor
                )}
              >
                {contact.avatar ? (
                  <img src={contact.avatar} alt={contact.name} className="w-full h-full rounded-full object-cover" />
                ) : (
                  contact.name
                    .split(" ")
                    .map((n) => n[0])
                    .join("")
                    .slice(0, 2)
                    .toUpperCase()
                )}
              </div>

              {/* Contact Info */}
              <div className="flex-1 text-left">
                <div className="flex items-center gap-2">
                  {contact.hasContactIcon && <User className="h-4 w-4 text-primary" />}
                  <span className="text-[15px] text-foreground font-medium">{contact.name}</span>
                </div>
                <p className="text-sm text-muted-foreground mt-0.5">{contact.lastSeen}</p>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* FAB - Add Contact */}
      <button
        className="fixed bottom-6 right-6 h-14 w-14 rounded-full bg-primary text-primary-foreground shadow-lg flex items-center justify-center hover:bg-primary/90 transition-colors"
        aria-label="Add new contact"
      >
        <UserPlus className="h-6 w-6" />
      </button>
    </div>
  )
}
