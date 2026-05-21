import { ArrowLeft, Users, Activity, MessageSquare, Shield, TrendingUp, Clock } from "lucide-react"
import { cn } from "@/lib/utils"
import { useQuery } from "@tanstack/react-query"
import { analyticsApi, messagingApi } from "@/lib/api"
import { Skeleton } from "@/components/ui/skeleton"

interface DashboardPageProps {
  isOpen: boolean
  onClose: () => void
}

export function DashboardPage({ isOpen, onClose }: DashboardPageProps) {
  const { data: dashboard, isLoading: dashLoading } = useQuery({
    queryKey: ["dashboard"],
    queryFn: analyticsApi.dashboard,
    enabled: isOpen,
    refetchInterval: isOpen ? 30_000 : false,
  })

  const { data: msgStats, isLoading: msgLoading } = useQuery({
    queryKey: ["messaging-stats"],
    queryFn: messagingApi.stats,
    enabled: isOpen,
    refetchInterval: isOpen ? 30_000 : false,
  })

  const stats = dashboard?.stats
  const activities = dashboard?.recentActivities ?? []

  const statCards = [
    {
      icon: Users,
      label: "Total Accounts",
      value: stats?.totalAccounts ?? 0,
      color: "text-blue-400",
      bg: "bg-blue-500/10",
    },
    {
      icon: Activity,
      label: "Active Sessions",
      value: stats?.activeSessions ?? 0,
      color: "text-green-400",
      bg: "bg-green-500/10",
    },
    {
      icon: MessageSquare,
      label: "Messages Sent",
      value: stats?.messagesSent ?? msgStats?.total_messages_sent ?? 0,
      color: "text-sky-400",
      bg: "bg-sky-500/10",
    },
    {
      icon: Shield,
      label: "Sessions Destroyed",
      value: stats?.destroyedSessions ?? 0,
      color: "text-red-400",
      bg: "bg-red-500/10",
    },
  ]

  return (
    <div
      style={{ zIndex: 70 }}
      className={cn(
        "fixed top-0 right-0 h-screen w-full max-w-md bg-[#17212b] flex flex-col transition-transform duration-300 ease-in-out",
        isOpen ? "translate-x-0" : "translate-x-full",
      )}
    >
      <header className="flex items-center gap-4 px-4 py-3 bg-[#17212b] border-b border-white/10">
        <button
          onClick={onClose}
          className="p-2 -ml-2 text-gray-400 hover:text-white transition-colors"
          aria-label="Go back"
        >
          <ArrowLeft className="h-6 w-6" />
        </button>
        <h1 className="text-xl font-medium text-white">Dashboard</h1>
      </header>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Stats Grid */}
        <div className="grid grid-cols-2 gap-3">
          {statCards.map(({ icon: Icon, label, value, color, bg }) => (
            <div key={label} className="bg-[#242f3d] rounded-xl p-4">
              {dashLoading || msgLoading ? (
                <Skeleton className="h-16 w-full bg-white/5" />
              ) : (
                <>
                  <div className={cn("w-10 h-10 rounded-full flex items-center justify-center mb-3", bg)}>
                    <Icon className={cn("h-5 w-5", color)} />
                  </div>
                  <p className="text-2xl font-bold text-white">{value.toLocaleString()}</p>
                  <p className="text-gray-400 text-xs mt-1">{label}</p>
                </>
              )}
            </div>
          ))}
        </div>

        {/* Messaging Stats */}
        {msgStats && (
          <div className="bg-[#242f3d] rounded-xl p-4">
            <p className="text-sky-400 text-sm font-medium mb-3 flex items-center gap-2">
              <TrendingUp className="h-4 w-4" /> Messaging Stats
            </p>
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <span className="text-gray-400 text-sm">Auto Replies Sent</span>
                <span className="text-white font-medium">{msgStats.auto_replies_sent}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400 text-sm">Active Accounts</span>
                <span className="text-white font-medium">{msgStats.active_accounts}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400 text-sm">DM Topics Created</span>
                <span className="text-white font-medium">{msgStats.dm_topics_created}</span>
              </div>
            </div>
          </div>
        )}

        {/* Recent Activity */}
        {activities.length > 0 && (
          <div className="bg-[#242f3d] rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-white/10">
              <span className="text-sky-400 text-sm font-medium">Recent Activity</span>
            </div>
            <ul role="list">
              {activities.map((activity, i) => (
                <li
                  key={i}
                  className={cn(
                    "px-4 py-3 flex items-start gap-3",
                    i < activities.length - 1 && "border-b border-white/5",
                  )}
                >
                  <Clock className="h-4 w-4 text-gray-500 mt-0.5 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-white text-sm">{activity.message}</p>
                    {activity.timestamp && (
                      <p className="text-gray-500 text-xs mt-0.5">
                        {new Date(activity.timestamp).toLocaleString()}
                      </p>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}

        {!dashLoading && activities.length === 0 && (
          <div className="text-center py-8">
            <Activity className="h-10 w-10 text-gray-600 mx-auto mb-2" />
            <p className="text-gray-400 text-sm">No recent activity</p>
          </div>
        )}
      </div>
    </div>
  )
}
