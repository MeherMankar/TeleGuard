import { MessageCircle, Users, Settings, User } from "lucide-react"
import { cn } from "@/lib/utils"

interface BottomNavProps {
  activeTab: "chats" | "contacts" | "settings" | "profile"
  onTabChange: (tab: "chats" | "contacts" | "settings" | "profile") => void
  unreadCount?: number
}

const navItems = [
  { id: "chats" as const, label: "Chats", icon: MessageCircle },
  { id: "contacts" as const, label: "Contacts", icon: Users },
  { id: "settings" as const, label: "Settings", icon: Settings },
  { id: "profile" as const, label: "Profile", icon: User },
]

export function BottomNav({ activeTab, onTabChange, unreadCount = 0 }: BottomNavProps) {
  return (
    <div className="fixed bottom-0 left-0 right-0 bg-[#17212b] border-t border-[#242f3d] max-w-md mx-auto">
      <div className="flex items-center justify-around py-2">
        {navItems.map((item) => {
          const Icon = item.icon
          const isActive = activeTab === item.id
          const showBadge = item.id === "chats" && unreadCount > 0

          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              className="flex flex-col items-center gap-1 px-4 py-1 relative"
            >
              <div className="relative">
                <Icon
                  className={cn(
                    "h-6 w-6 transition-colors",
                    isActive ? "text-sky-400" : "text-muted-foreground"
                  )}
                />
                {showBadge && (
                  <span className="absolute -top-1.5 -right-2 min-w-[18px] h-[18px] bg-sky-500 text-white text-[10px] font-medium rounded-full flex items-center justify-center px-1">
                    {unreadCount > 999 ? "999+" : unreadCount}
                  </span>
                )}
              </div>
              <span
                className={cn(
                  "text-xs transition-colors",
                  isActive ? "text-sky-400" : "text-muted-foreground"
                )}
              >
                {item.label}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
