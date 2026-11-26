import { Menu, Search, Loader2, FolderOpen } from "lucide-react"
import { Input } from "@/components/ui/input"

interface SearchHeaderProps {
  isLoading?: boolean
  searchValue: string
  onSearchChange: (value: string) => void
  onMenuClick?: () => void
  onFoldersClick?: () => void
  title?: string
}

export function SearchHeader({
  isLoading = false,
  searchValue,
  onSearchChange,
  onMenuClick,
  onFoldersClick,
  title = "People",
}: SearchHeaderProps) {
  return (
    <div className="flex flex-col border-b border-white/[0.06] bg-[#17212b]">
      {/* Top header with title */}
      <div className="flex items-center justify-between px-4 pb-2 pt-4">
        <div className="flex items-center gap-4">
          <button
            onClick={onMenuClick}
            aria-label="Open menu"
            className="rounded-full p-2 transition-colors hover:bg-white/[0.06]"
          >
            <Menu className="h-6 w-6 text-muted-foreground" />
          </button>
          <h1 className="max-w-[220px] truncate text-base font-medium text-foreground">{title}</h1>
        </div>
        <button
          onClick={onFoldersClick}
          aria-label="Manage chat folders"
          className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
        >
          <FolderOpen className="h-5 w-5" />
        </button>
      </div>

      {/* Search bar */}
      <div className="px-4 pb-3">
        <div className="relative">
          <div className="absolute left-3 top-1/2 -translate-y-1/2">
            {isLoading ? (
              <Loader2 className="h-5 w-5 text-muted-foreground animate-spin" />
            ) : (
              <Search className="h-5 w-5 text-muted-foreground" />
            )}
          </div>
          <Input
            type="text"
            placeholder="Search Chats"
            value={searchValue}
            onChange={(e) => onSearchChange(e.target.value)}
            className="h-10 rounded-lg border border-white/[0.06] bg-[#1d2935] pl-10 text-foreground placeholder:text-muted-foreground focus-visible:border-[#2AABEE]/60 focus-visible:ring-0"
          />
        </div>
      </div>
    </div>
  )
}
