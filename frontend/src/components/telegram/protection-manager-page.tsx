import {
  ArrowLeft,
  Shield,
  Zap,
  Loader2,
  AlertTriangle,
  Clock,
  CheckCircle2,
  Eye,
  Timer,
  Trash2,
  ShieldOff,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { securityApi, accountsApi, type Account } from "@/lib/api"
import { useUser } from "@/contexts/user-context"
import { useWsEvent } from "@/hooks/use-ws-event"
import { toast } from "sonner"
import { Switch } from "@/components/ui/switch"
import { useCallback } from "react"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"

interface ProtectionManagerPageProps {
  isOpen: boolean
  onClose: () => void
}

export function ProtectionManagerPage({ isOpen, onClose }: ProtectionManagerPageProps) {
  const { accounts } = useUser()
  const queryClient = useQueryClient()

  const { data: security, isLoading } = useQuery({
    queryKey: ["security"],
    queryFn: securityApi.settings,
    enabled: isOpen,
    refetchInterval: isOpen ? 20_000 : false,
  })

  const { data: logs = [] } = useQuery({
    queryKey: ["security-logs"],
    queryFn: () => securityApi.logs(10),
    enabled: isOpen,
    refetchInterval: isOpen ? 10_000 : false,
  })

  // Live security alerts from bot via WebSocket
  useWsEvent(
    "security_alert",
    useCallback(() => {
      queryClient.invalidateQueries({ queryKey: ["security"] })
      queryClient.invalidateQueries({ queryKey: ["security-logs"] })
    }, [queryClient]),
  )

  // OTP Destroyer toggled from bot side
  useWsEvent(
    "otp_destroyer_toggled",
    useCallback(() => {
      queryClient.invalidateQueries({ queryKey: ["accounts"] })
    }, [queryClient]),
  )

  const sessionDestroyerMutation = useMutation({
    mutationFn: (enabled: boolean) => securityApi.updateSettings(enabled),
    onSuccess: (res) => {
      toast.success(`Session Destroyer ${res.enabled ? "enabled" : "disabled"}`)
      queryClient.invalidateQueries({ queryKey: ["security"] })
    },
    onError: (e) => toast.error((e as Error).message),
  })

  const otpDestroyerMutation = useMutation({
    mutationFn: ({ account_id, enabled }: { account_id: string; enabled: boolean }) =>
      securityApi.toggleOtpDestroyer(account_id, enabled),
    onSuccess: (res, vars) => {
      toast.success(res.message || `OTP Destroyer ${vars.enabled ? "enabled" : "disabled"}`)
      queryClient.invalidateQueries({ queryKey: ["accounts"] })
    },
    onError: (e) => toast.error((e as Error).message),
  })

  const tempPassthroughMutation = useMutation({
    mutationFn: (account_id: string) => securityApi.tempPassthrough(account_id),
    onSuccess: (res) => toast.success(res.message || "5-min passthrough active"),
    onError: (e) => toast.error((e as Error).message),
  })

  const disableTempMutation = useMutation({
    mutationFn: (account_id: string) => securityApi.disableDestroyerTemp(account_id),
    onSuccess: (res) => toast.success(res.message || "Destroyer paused 5 min"),
    onError: (e) => toast.error((e as Error).message),
  })

  const isSessionDestroyerEnabled = security?.settings?.enabled ?? false
  const destroyedCount = security?.stats?.destroyed_count ?? 0

  return (
    <div
      style={{ zIndex: 75 }}
      className={cn(
        "fixed inset-0 bg-[#17212b] flex flex-col transition-transform duration-300 ease-in-out",
        isOpen ? "translate-x-0" : "translate-x-full",
      )}
    >
      <header className="flex items-center gap-4 px-4 py-3 bg-[#17212b] border-b border-white/10">
        <button
          onClick={onClose}
          className="p-2 -ml-2 text-gray-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="h-6 w-6" />
        </button>
        <h1 className="text-xl font-medium text-white">Protection Manager</h1>
      </header>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Hero */}
        <div className="bg-[#242f3d] rounded-xl p-5 text-center">
          <div className="w-14 h-14 rounded-full bg-gradient-to-br from-red-500 to-orange-500 flex items-center justify-center mb-3 mx-auto">
            <Shield className="h-7 w-7 text-white" />
          </div>
          <h2 className="text-white font-semibold text-base mb-1">Account Protection</h2>
          <p className="text-gray-400 text-xs">
            Controls sync live with the bot — no restart needed
          </p>
        </div>

        {/* ── Session Destroyer ── */}
        <div className="bg-[#242f3d] rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
            <span className="text-sky-400 text-sm font-medium">Session Destroyer</span>
            {destroyedCount > 0 && (
              <span className="text-xs text-red-400 bg-red-500/10 px-2 py-0.5 rounded-full">
                {destroyedCount} destroyed
              </span>
            )}
          </div>
          <div className="px-4 py-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center flex-shrink-0">
              <Zap className="h-5 w-5 text-red-400" />
            </div>
            <div className="flex-1">
              <p className="text-white font-medium text-sm">Auto Session Destroyer</p>
              <p className="text-gray-400 text-xs">
                Automatically terminates unauthorized Telegram sessions
              </p>
            </div>
            {isLoading ? (
              <Loader2 className="h-5 w-5 text-gray-400 animate-spin" />
            ) : (
              <Switch
                checked={isSessionDestroyerEnabled}
                onCheckedChange={(v) => sessionDestroyerMutation.mutate(v)}
                disabled={sessionDestroyerMutation.isPending}
              />
            )}
          </div>
          {isSessionDestroyerEnabled && (
            <div className="px-4 pb-4">
              <div className="flex items-center gap-2 bg-green-500/10 border border-green-500/30 rounded-lg px-3 py-2">
                <CheckCircle2 className="h-4 w-4 text-green-400 flex-shrink-0" />
                <p className="text-green-400 text-xs">
                  Active — monitoring all connected accounts
                </p>
              </div>
            </div>
          )}
        </div>

        {/* ── OTP Destroyer per account ── */}
        {accounts.length > 0 && (
          <div className="bg-[#242f3d] rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-white/10">
              <span className="text-sky-400 text-sm font-medium">OTP Destroyer</span>
              <p className="text-gray-500 text-xs mt-0.5">
                Invalidates unauthorized login codes in real-time
              </p>
            </div>
            <ul role="list">
              {accounts.map((acc: Account, i) => (
                <li
                  key={acc.id}
                  className={cn(
                    "px-4 py-3",
                    i < accounts.length - 1 && "border-b border-white/5",
                  )}
                >
                  <div className="flex items-center gap-3 mb-2">
                    <div className="w-8 h-8 rounded-full bg-sky-500/20 flex items-center justify-center flex-shrink-0 text-sky-400 font-bold text-sm">
                      {(acc.name || acc.phone || "?").charAt(0).toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-white text-sm font-medium truncate">
                        {acc.name || acc.phone}
                      </p>
                      {acc.phone && acc.name !== acc.phone && (
                        <p className="text-gray-500 text-xs truncate">{acc.phone}</p>
                      )}
                    </div>
                    <Switch
                      checked={acc.otp_destroyer_enabled ?? false}
                      onCheckedChange={(v) =>
                        otpDestroyerMutation.mutate({ account_id: acc.id, enabled: v })
                      }
                      disabled={otpDestroyerMutation.isPending}
                    />
                  </div>

                  {/* Quick actions when OTP Destroyer is ON */}
                  {acc.otp_destroyer_enabled && (
                    <div className="flex gap-2 ml-11">
                      <button
                        onClick={() => tempPassthroughMutation.mutate(acc.id)}
                        disabled={tempPassthroughMutation.isPending}
                        className="flex items-center gap-1.5 text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-lg px-2.5 py-1.5 hover:bg-amber-500/20 transition-colors"
                        title="Allow OTP for 5 minutes"
                      >
                        <Eye className="h-3.5 w-3.5" />
                        Temp OTP
                      </button>
                      <button
                        onClick={() => disableTempMutation.mutate(acc.id)}
                        disabled={disableTempMutation.isPending}
                        className="flex items-center gap-1.5 text-xs text-orange-400 bg-orange-500/10 border border-orange-500/20 rounded-lg px-2.5 py-1.5 hover:bg-orange-500/20 transition-colors"
                        title="Pause destroyer for 5 minutes"
                      >
                        <Timer className="h-3.5 w-3.5" />
                        Pause 5m
                      </button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* ── Recent Security Events ── */}
        {logs.length > 0 && (
          <div className="bg-[#242f3d] rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-white/10">
              <span className="text-sky-400 text-sm font-medium">Recent Events</span>
            </div>
            <ul role="list">
              {logs.map((log, i) => (
                <li
                  key={i}
                  className={cn(
                    "px-4 py-3 flex items-start gap-3",
                    i < logs.length - 1 && "border-b border-white/5",
                  )}
                >
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
                </li>
              ))}
            </ul>
          </div>
        )}

        {!isLoading && logs.length === 0 && (
          <div className="text-center py-6">
            <ShieldOff className="h-10 w-10 text-gray-600 mx-auto mb-2" />
            <p className="text-gray-400 text-sm">No security events yet</p>
          </div>
        )}

        <p className="text-gray-600 text-xs text-center px-4">
          All changes apply to the running bot immediately — no restart required.
        </p>
      </div>
    </div>
  )
}


