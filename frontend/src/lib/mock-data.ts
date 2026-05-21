export interface Chat {
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
  username?: string
  lastSeen?: string
  userId?: string
  birthday?: string
  isOnline?: boolean
  isVerified?: boolean
  messageType?: "text" | "photo" | "sticker" | "video" | "link"
}

export const chats: Chat[] = [
  { id: "1", avatar: "", name: "Chinki 🥴", preview: "Photo", time: "4:07 PM", isRead: true, avatarColor: "bg-pink-500", isOnline: true, messageType: "photo" },
  { id: "2", avatar: "", name: "Rashi Kolpyakwar", preview: "Sticker", time: "4:05 PM", isRead: true, isMuted: true, avatarColor: "bg-green-500", isOnline: true, messageType: "sticker" },
  { id: "3", avatar: "", name: "Sanika Ramteke", preview: "Sticker", time: "4:04 PM", isRead: true, isMuted: true, avatarColor: "bg-green-500", isOnline: true, messageType: "sticker" },
  { id: "4", avatar: "", name: "Sharayu", preview: "2 photos", time: "1:39 PM", isRead: true, avatarColor: "bg-amber-500", isOnline: true, messageType: "photo" },
  { id: "5", avatar: "", name: "ṜÜƧӇṀɅX 🔥 #GUJ...", preview: "https://explicitexchange.netlify.app/", time: "12:34 PM", isRead: true, isMuted: true, avatarColor: "bg-rose-600", messageType: "link" },
  { id: "6", avatar: "", name: "DB9", preview: "Id mil gai wapas?", time: "8:36 AM", isRead: true, isMuted: true, avatarColor: "bg-slate-600", isOnline: true, messageType: "text" },
  { id: "7", avatar: "", name: "kasuro Giya", preview: "Hiii", time: "Wed", isRead: true, avatarColor: "bg-pink-500", isOnline: true, messageType: "text" },
  { id: "8", avatar: "", name: "Telegram Notifications", preview: "Login code: 🎉🎊. Do not give this co...", time: "Tue", avatarColor: "bg-pink-500", isVerified: true, messageType: "text" },
  { id: "9", avatar: "", name: "Ambivert", preview: "Photo", time: "Tue", avatarColor: "bg-purple-500", isOnline: true, messageType: "photo" },
]

export interface ChatMessage {
  id: string
  type: "text" | "image" | "video" | "reply"
  content: string
  time: string
  isOutgoing: boolean
  isRead?: boolean
  imageUrl?: string
  videoDuration?: string
  videoSize?: string
  replyTo?: { name: string; content: string; nameColor?: string }
}

export const chatMessages: Record<string, ChatMessage[]> = {
  "4": [
    { id: "m1", type: "image", content: "", time: "8:01 PM", isOutgoing: false, imageUrl: "photo1" },
    { id: "m2", type: "video", content: "", time: "8:02 PM", isOutgoing: false, videoDuration: "0:39", videoSize: "4.8 MB", imageUrl: "video1" },
    { id: "m3", type: "reply", content: "Ky he", time: "10:24 PM", isOutgoing: false, replyTo: { name: "मेहर मानकर", content: "Video", nameColor: "text-orange-400" } },
    { id: "m4", type: "text", content: "Are te husban le sodun bf sang geli", time: "10:25 PM", isOutgoing: true, isRead: true },
  ],
}
