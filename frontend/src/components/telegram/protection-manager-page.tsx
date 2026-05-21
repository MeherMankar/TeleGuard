import { ArrowLeft, Shield, Zap, Loader2, AlertTriangle, Clock, CheckCircle2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { securityApi, type SecurityLog } from "@/lib/api"
import { toast } from "sonner"
import { Switch } from "@/components/ui/switch"

interface ProtectionManagerPageProps {
  isOpen: boolean
  onClose: () => void
}

export function ProtectionManagerPage({ isOpen, onClose }: ProtectionManagerPageProps) {
  const queryClient = useQueryClient()

  const { data: security, isLoading } = useQuery({
    queryKey: ["security"],
    queryFn: securityApi.settings,
    enabled: isOpen,
  })

  const { data: logs = [] } = useQuery({
    queryKey: ["security-logs"],
    queryFn: () => securityApi.logs(10),
    enabled: isOpen,
    refetchInterval: isOpen ? 15_000 : false,
  })

  const toggleMutation = useMutation({
    mutationFn: (enabled: boolean) => securityApi.updateSettings(enabled),
    onSuccess: (res) => {
      toast.success(`Session Destroyer ${res.enabled ? "enabled" : "disabled"}`)
      queryClient.invalidateQueries({ queryKey: ["security"] })
    },
    onError: (e) => toast.error((e as Error).message),
  })

  const isEnabled = security?.settings?.enabled ?? false
  const destroyedCount = security?.stats?.destroyed_count ?? 0

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
        <h1 className="text-xl font-medium text-white">Protection Manager</h1>
      </header>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Hero */}
        <div className="bg-[#242f3d] rounded-xl p-6">
          <div className="w-16 h-16 rounded-full bg-gradient-to-br from-red-500 to-orange-500 flex items-center justify-center mb-4 mx-auto">
            <Shield className="h-8 w-8 text-white" />
          </div>
          <h2 className="text-center text-white font-semibold text-lg mb-2">Account Protection</h2>
          <p className="text-center text-gray-400 text-sm">
            Advanced security tools to protect your accounts from unauthorized access
          </p>
        </div>

        {/* Session Destroyer Toggle */}
        <div className="bg-[#242f3d] rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-white/10">
            <span className="text-sky-400 text-sm font-medium">Session Destroyer</span>
          </div>
          <div className="px-4 py-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-full bg-red-500 flex items-center justify-center flex-shrink-0">
              <Zap className="h-5 w-5 text-white" />
            </div>
            <div className="flex-1">
              <p className="text-white font-medium">Auto Session Destroyer</p>
              <p className="text-gray-400 text-sm">
                Automatically terminate unauthorized sessions
              </p>
            </div>
            {isLoading ? (
              <Loader2 className="h-5 w-5 text-gray-400 animate-spin" />
            ) : (
              <Switch
                checked={isEnabled}
                onCheckedChange={(v) => toggleMutation.mutate(v)}
                disabled={toggleMutation.isPending}
              />
            )}
          </div>
          {isEnabled && (
            <div className="px-4 pb-4">
              <div className="flex items-center gap-2 bg-green-500/10 border border-green-500/30 rounded-lg px-3 py-2">
                <CheckCircle2 className="h-4 w-4 text-green-400 flex-shrink-0" />
                <p className="text-green-400 text-xs">
                  Active — {destroyedCount} sessions destroyed
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Recent Security Logs */}
        {logs.length > 0 && (
          <div className="bg-[#242f3d] rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-white/10">
              <span className="text-sky-400 text-sm font-medium">Recent Security Events</span>
            </div>
            <ul role="list">
              {logs.map((log: SecurityLog, i) => (
                <li key={i} className={cn("px-4 py-3", i < logs.length - 1 && "border-b border-white/5")}>
                  <div className="flex items-start gap-3">
                    <AlertTriangle className="h-4 w-4 text-orange-400 mt-0.5 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-white text-sm">
                        Session destroyed — {log.device ?? "Unknown device"}
                      </p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-gray-500 text-xs">{log.ip ?? "Unknown IP"}</span>
                        {log.timestamp && (
                          <>
                            <span className="text-gray-600">·</span>
                            <span className="text-gray-500 text-xs flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {new Date(log.timestamp).toLocaleString()}
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}

        <p className="text-gray-500 text-xs text-center px-4">
          Use these tools responsibly. Misuse may result in account restrictions.
        </p>
      </div>
    </div>
  )
}
