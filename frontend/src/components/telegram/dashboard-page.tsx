import { ArrowLeft, Activity, Clock, Globe, Server, TriangleAlert } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { analyticsApi, messagingApi, systemApi } from "@/lib/api"
import { cn } from "@/lib/utils"

interface DashboardPageProps {
  isOpen: boolean
  onClose: () => void
}

function formatActivityTimestamp(timestamp: string | null) {
  if (!timestamp) return null

  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) return null

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date)
}

export function DashboardPage({ isOpen, onClose }: DashboardPageProps) {
  const {
    data: dashboard,
    isLoading: dashLoading,
    isError: dashError,
  } = useQuery({
    queryKey: ["dashboard"],
    queryFn: analyticsApi.dashboard,
    enabled: isOpen,
    refetchInterval: isOpen ? 30_000 : false,
  })

  const {
    data: msgStats,
    isLoading: msgLoading,
    isError: msgError,
  } = useQuery({
    queryKey: ["messaging-stats"],
    queryFn: messagingApi.stats,
    enabled: isOpen,
    refetchInterval: isOpen ? 30_000 : false,
  })

  const {
    data: backendHealth,
    isLoading: backendLoading,
    isError: backendError,
  } = useQuery({
    queryKey: ["backend-health"],
    queryFn: systemApi.health,
    enabled: isOpen,
    refetchInterval: isOpen ? 30_000 : false,
  })

  const {
    data: sessionNetwork,
    isLoading: networkLoading,
    isError: networkError,
  } = useQuery({
    queryKey: ["session-network"],
    queryFn: systemApi.sessionNetwork,
    enabled: isOpen,
    refetchInterval: isOpen ? 30_000 : false,
  })

  const stats = dashboard?.stats
  const activities = dashboard?.recentActivities ?? []
  const messageCount = stats?.messagesSent ?? msgStats?.total_messages_sent

  const statCards = [
    { label: "Total accounts", value: stats?.totalAccounts, loading: dashLoading },
    {
      label: "Active sessions",
      value: stats?.activeSessions,
      loading: dashLoading,
      featured: true,
    },
    {
      label: "Messages sent",
      value: messageCount,
      loading: messageCount === undefined && (dashLoading || msgLoading),
    },
    { label: "Sessions destroyed", value: stats?.destroyedSessions, loading: dashLoading },
  ]

  const backendStatus = backendLoading
    ? "Checking"
    : backendError
      ? "Unavailable"
      : backendHealth?.status === "healthy"
        ? "Connected"
        : "Unknown"
  const networkStatus = networkLoading
    ? "Checking"
    : networkError
      ? "Unavailable"
      : sessionNetwork && "current_ip" in sessionNetwork
        ? `${sessionNetwork.stability[0].toUpperCase()}${sessionNetwork.stability.slice(1)} stability · ${sessionNetwork.ip_changes.toLocaleString()} IP changes`
        : sessionNetwork?.status === "guardian_not_initialized"
          ? "Monitor not initialized"
          : "Unknown"

  const statuses = [
    {
      icon: Server,
      label: "Backend service",
      value: backendStatus,
      tone: backendError
        ? "text-[#e5484d]"
        : backendStatus === "Connected"
          ? "text-[#4cc38a]"
          : "text-[#a3a9b8]",
    },
    {
      icon: Globe,
      label: "Session network",
      value: networkStatus,
      tone: networkError ? "text-[#e5484d]" : "text-[#a3a9b8]",
    },
  ]

  return (
    <div
      style={{ zIndex: 75 }}
      className={cn(
        "tg-screen fixed inset-0 flex flex-col bg-[#0b0d14] text-[#eef0f5] transition-transform duration-300 ease-in-out",
        isOpen ? "translate-x-0" : "translate-x-full",
      )}
    >
      <header className="flex min-h-14 items-center gap-3 border-b border-white/10 bg-[#0b0d14] px-4 py-2 sm:px-5">
        <button
          onClick={onClose}
          className="rounded-lg p-2 text-[#a3a9b8] transition-colors hover:bg-white/5 hover:text-[#eef0f5] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#2AABEE]"
          aria-label="Go back"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <h1 className="text-lg font-medium">Dashboard</h1>
      </header>

      <div className="flex-1 overflow-y-auto" aria-busy={dashLoading || msgLoading}>
        <main className="mx-auto flex w-full max-w-5xl flex-col gap-6 p-4 sm:p-6">
          {(dashError || msgError) && (
            <div
              role="alert"
              className="flex items-start gap-3 rounded-xl border border-[#e5484d]/20 bg-[#e5484d]/10 px-4 py-3 text-sm text-[#e5484d]"
            >
              <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
              <p>
                {dashError && msgError
                  ? "Dashboard and messaging data are unavailable. Check your connection."
                  : dashError
                    ? "Dashboard data is unavailable. Check your connection."
                    : "Messaging data is unavailable. Check your connection."}
              </p>
            </div>
          )}

          <section aria-labelledby="dashboard-overview">
            <h2 id="dashboard-overview" className="mb-3 text-sm font-medium text-[#a3a9b8]">
              Overview
            </h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {statCards.map(({ label, value, loading, featured }) => (
                <article
                  key={label}
                  className="min-w-0 rounded-xl border border-white/10 bg-[#11141c] p-4"
                >
                  <p className="text-sm text-[#a3a9b8]">{label}</p>
                  {loading ? (
                    <div className="mt-3 h-8 w-16 rounded-md bg-white/5" aria-hidden="true" />
                  ) : (
                    <p
                      className={cn(
                        "mt-2 text-2xl font-medium tabular-nums",
                        featured && "text-[#2AABEE]",
                      )}
                    >
                      {value === undefined ? "—" : value.toLocaleString()}
                    </p>
                  )}
                </article>
              ))}
            </div>
          </section>

          <section aria-label="Service status" className="grid gap-3 sm:grid-cols-2">
            {statuses.map(({ icon: Icon, label, value, tone }) => (
              <article
                key={label}
                className="flex min-h-20 items-center gap-3 rounded-xl border border-white/10 bg-[#11141c] px-4 py-3"
              >
                <Icon className="h-4 w-4 shrink-0 text-[#7a8296]" />
                <div className="min-w-0">
                  <h2 className="text-sm font-medium">{label}</h2>
                  <p className={cn("mt-1 truncate text-sm", tone)}>{value}</p>
                </div>
              </article>
            ))}
          </section>

          <section aria-labelledby="messaging-heading">
            <div className="mb-3 flex items-center gap-2">
              <Activity className="h-4 w-4 text-[#7a8296]" />
              <h2 id="messaging-heading" className="text-sm font-medium">
                Messaging
              </h2>
            </div>
            <div className="rounded-xl border border-white/10 bg-[#11141c] px-4">
              {msgStats ? (
                [
                  ["Auto replies sent", msgStats.auto_replies_sent],
                  ["Active accounts", msgStats.active_accounts],
                  ["DM topics created", msgStats.dm_topics_created],
                ].map(([label, value], index, rows) => (
                  <div
                    key={label}
                    className={cn(
                      "flex min-h-12 items-center justify-between gap-4 py-3",
                      index < rows.length - 1 && "border-b border-white/10",
                    )}
                  >
                    <span className="text-sm text-[#a3a9b8]">{label}</span>
                    <span className="text-sm font-medium tabular-nums">
                      {typeof value === "number" ? value.toLocaleString() : value}
                    </span>
                  </div>
                ))
              ) : msgLoading ? (
                <div className="space-y-3 py-4" aria-label="Loading messaging stats">
                  <div className="h-4 w-2/3 rounded bg-white/5" />
                  <div className="h-4 w-1/2 rounded bg-white/5" />
                  <div className="h-4 w-3/5 rounded bg-white/5" />
                </div>
              ) : (
                <p className="py-4 text-sm text-[#a3a9b8]">
                  {msgError ? "Messaging data unavailable" : "No messaging data"}
                </p>
              )}
            </div>
          </section>

          <section aria-labelledby="activity-heading">
            <div className="mb-3 flex items-center gap-2">
              <Clock className="h-4 w-4 text-[#7a8296]" />
              <h2 id="activity-heading" className="text-sm font-medium">
                Recent activity
              </h2>
            </div>
            <div className="rounded-xl border border-white/10 bg-[#11141c]">
              {dashLoading ? (
                <div className="space-y-3 p-4" aria-label="Loading recent activity">
                  <div className="h-4 w-4/5 rounded bg-white/5" />
                  <div className="h-3 w-1/3 rounded bg-white/5" />
                </div>
              ) : activities.length > 0 ? (
                <ul role="list">
                  {activities.map((activity, index) => {
                    const timestamp = formatActivityTimestamp(activity.timestamp)

                    return (
                      <li
                        key={`${activity.type}-${activity.timestamp ?? index}-${index}`}
                        className={cn(
                          "flex items-start gap-3 px-4 py-3",
                          index < activities.length - 1 && "border-b border-white/10",
                        )}
                      >
                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#2AABEE]" />
                        <div className="min-w-0 flex-1">
                          <p className="text-sm">{activity.message}</p>
                          {timestamp && (
                            <p className="mt-1 text-xs tabular-nums text-[#7a8296]">{timestamp}</p>
                          )}
                        </div>
                      </li>
                    )
                  })}
                </ul>
              ) : (
                <div className="flex items-center gap-3 px-4 py-5">
                  <Activity className="h-4 w-4 shrink-0 text-[#7a8296]" />
                  <p className="text-sm text-[#a3a9b8]">
                    {dashError ? "Activity data unavailable" : "No recent activity"}
                  </p>
                </div>
              )}
            </div>
          </section>
        </main>
      </div>
    </div>
  )
}
