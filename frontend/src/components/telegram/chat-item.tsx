import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { VolumeX, CheckCheck, BadgeCheck, ImageIcon, Camera } from "lucide-react"
import { cn } from "@/lib/utils"
import { Link } from "@tanstack/react-router"

interface ChatItemProps {
  id: string
  avatar: string
  name: string
  preview: string
  time: string
  unreadCount?: number
  isMuted?: boolean
  isPinned?: boolean
  isRead?: boolean
  senderPrefix?: string
  avatarColor?: string
  isOnline?: boolean
  isVerified?: boolean
  messageType?: "text" | "photo" | "sticker" | "video" | "link"
}

function formatUnreadCount(count: number): string {
  if (count >= 1000000) {
    return `${(count / 1000000).toFixed(1)}M`
  }
  if (count >= 1000) {
    return `${(count / 1000).toFixed(1)}K`
  }
  return count.toString()
}

export function ChatItem({
  id,
  avatar,
  name,
  preview,
  time,
  unreadCount,
  isMuted = false,
  isPinned = false,
  isRead = false,
  senderPrefix,
  avatarColor = "bg-primary",
  isOnline = false,
  isVerified = false,
  messageType = "text",
}: ChatItemProps) {
  const getMessagePreview = () => {
    switch (messageType) {
      case "photo":
        return (
          <span className="flex items-center gap-1">
            <ImageIcon className="h-4 w-4 text-sky-400" />
            <span className="text-sky-400">Photo</span>
          </span>
        )
      case "sticker":
        return (
          <span className="flex items-center gap-1">
            <span className="text-base">👋</span>
            <span className="text-sky-400">Sticker</span>
          </span>
        )
      case "video":
        return (
          <span className="flex items-center gap-1">
            <Camera className="h-4 w-4 text-sky-400" />
            <span className="text-sky-400">Video</span>
          </span>
        )
      default:
        return preview
    }
  }

  return (
    <Link 
      to="/chat/$chatId" 
      params={{ chatId: id }} 
      className="flex items-center gap-3 px-4 py-2.5 hover:bg-[#202b36] cursor-pointer transition-colors"
    >
      {/* Avatar with online indicator */}
      <div className="relative shrink-0">
        <Avatar className="h-14 w-14">
          <AvatarImage src={avatar} alt={name} />
          <AvatarFallback className={cn(avatarColor, "text-white font-medium text-lg")}>
            {name.slice(0, 2).toUpperCase()}
          </AvatarFallback>
        </Avatar>
        {isOnline && (
          <div className="absolute bottom-0 right-0 w-4 h-4 bg-green-500 rounded-full border-2 border-[#17212b]" />
        )}
      </div>

      <div className="flex-1 min-w-0">
        {/* Name row */}
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 min-w-0">
            <span className="font-medium text-foreground truncate">{name}</span>
            {isVerified && (
              <BadgeCheck className="h-4 w-4 text-sky-400 fill-sky-400 shrink-0" />
            )}
            {isMuted && (
              <VolumeX className="h-4 w-4 text-muted-foreground shrink-0" />
            )}
          </div>
          <div className="flex items-center gap-1 shrink-0">
            {isRead && !unreadCount && (
              <CheckCheck className="h-4 w-4 text-sky-400" />
            )}
            <span className="text-xs text-muted-foreground">{time}</span>
          </div>
        </div>

        {/* Preview row */}
        <div className="flex items-center justify-between gap-2 mt-0.5">
          <div className="text-sm text-muted-foreground truncate flex items-center gap-1">
            {senderPrefix && (
              <span className="text-sky-400">{senderPrefix}: </span>
            )}
            {messageType !== "text" ? getMessagePreview() : preview}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {unreadCount && unreadCount > 0 && (
              <span
                className={cn(
                  "min-w-[22px] h-[22px] rounded-full text-xs font-medium flex items-center justify-center px-1.5",
                  isMuted
                    ? "bg-[#3e546a] text-muted-foreground"
                    : "bg-sky-500 text-white"
                )}
              >
                {formatUnreadCount(unreadCount)}
              </span>
            )}
          </div>
        </div>
      </div>
    </Link>
  )
}
