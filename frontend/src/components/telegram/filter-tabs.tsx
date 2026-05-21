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
    <div className="flex items-center px-4 py-2 bg-[#17212b]">
      <div className="flex items-center bg-[#242f3d] rounded-full p-1 w-full">
        {tabs.map((tab) => {
          const Icon = iconMap[tab.icon]
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={cn(
                "flex items-center justify-center gap-1.5 px-4 py-2 rounded-full text-sm font-medium transition-colors flex-1",
                isActive
                  ? "bg-[#3e546a] text-white"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Icon className="h-4 w-4" />
              <span className={cn(
                "text-xs font-medium",
                isActive ? "text-white" : "text-muted-foreground"
              )}>
                {tab.count}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
