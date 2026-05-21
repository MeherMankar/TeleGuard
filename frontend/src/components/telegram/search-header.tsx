import { Menu, Search, Loader2, FolderOpen, MoreVertical } from "lucide-react"
import { Input } from "@/components/ui/input"

interface SearchHeaderProps {
  isLoading?: boolean
  searchValue: string
  onSearchChange: (value: string) => void
  onMenuClick?: () => void
  title?: string
}

export function SearchHeader({
  isLoading = false,
  searchValue,
  onSearchChange,
  onMenuClick,
  title = "People",
}: SearchHeaderProps) {
  return (
    <div className="flex flex-col">
      {/* Top header with title */}
      <div className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-4">
          <button
            onClick={onMenuClick}
            aria-label="Open menu"
            className="p-1 hover:bg-secondary rounded-full transition-colors"
          >
            <Menu className="h-6 w-6 text-muted-foreground" />
          </button>
          <h1 className="text-xl font-medium text-foreground">{title}</h1>
        </div>
        <div className="flex items-center gap-2">
          <button className="p-2 hover:bg-secondary rounded-full transition-colors">
            <FolderOpen className="h-5 w-5 text-muted-foreground" />
          </button>
          <button className="p-2 hover:bg-secondary rounded-full transition-colors">
            <MoreVertical className="h-5 w-5 text-muted-foreground" />
          </button>
        </div>
      </div>

      {/* Search bar */}
      <div className="px-4 pb-2">
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
            className="pl-10 bg-[#242f3d] border-0 rounded-lg h-10 placeholder:text-muted-foreground text-foreground"
          />
        </div>
      </div>
    </div>
  )
}
