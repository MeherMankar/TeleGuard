
import { Archive } from "lucide-react"

interface ArchivedChatsProps {
  preview: string
  onClick?: () => void
}

export function ArchivedChats({ preview, onClick }: ArchivedChatsProps) {
  return (
    <div
      onClick={onClick}
      className="flex items-center gap-3 px-4 py-3 hover:bg-secondary/50 cursor-pointer transition-colors"
    >
      <div className="h-12 w-12 rounded-full bg-primary/20 flex items-center justify-center shrink-0">
        <Archive className="h-6 w-6 text-primary" />
      </div>

      <div className="flex-1 min-w-0">
        <span className="font-medium text-foreground">Archived Chats</span>
        <p className="text-sm text-muted-foreground truncate mt-0.5">
          {preview}
        </p>
      </div>
    </div>
  )
}
