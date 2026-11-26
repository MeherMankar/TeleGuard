import { cn } from "@/lib/utils"
import { LayoutGrid, UserPlus, Users, UsersRound } from "lucide-react"

interface FilterTab {
  id: string
  icon: "all" | "bots" | "people" | "groups"
  count: number
}

interface FilterTabsProps {
  tabs: FilterTab[]
  activeTab: string
  onTabChange: (tabId: string) => void
}

const iconMap = {
  all: LayoutGrid,
  bots: UserPlus,
  people: Users,
  groups: UsersRound,
}

export function FilterTabs({ tabs, activeTab, onTabChange }: FilterTabsProps) {
  return (
    <div className="flex items-center bg-[#0b0d14] px-4 py-2">
      <div className="flex w-full items-center gap-1 rounded-lg border border-white/10 bg-[#11141c] p-1">
        {tabs.map((tab) => {
          const Icon = iconMap[tab.icon]
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={cn(
                "flex min-h-9 flex-1 items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-[#232733] text-white"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              <span
                className={cn(
                  "text-xs font-medium tabular-nums",
                  isActive ? "text-white" : "text-muted-foreground",
                )}
              >
                {tab.count}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
