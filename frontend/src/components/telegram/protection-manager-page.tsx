import {
  ArrowLeft, Shield, Zap, Loader2, AlertTriangle, Clock,
  CheckCircle2, Eye, Timer, ShieldOff, Forward, RefreshCw,
  LogIn, Bell,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { securityApi, accountsApi, type Account } from "@/lib/api"
import { useUser } from "@/contexts/user-context"
import { useWsEvent } from "@/hooks/use-ws-event"
import { toast } from "sonner"
import { Switch } from "@/components/ui/switch"
import { useCallback } from "react"

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
    staleTime: 0,
    refetchInterval: isOpen ? 15_000 : false,
  })

  const { data: logs = [] } = useQuery({
    queryKey: ["security-logs"],
    queryFn: () => securityApi.logs(10),
    enabled: isOpen,
    refetchInterval: isOpen ? 10_000 : false,
  })

  // Refresh on live bot events
  useWsEvent("security_alert", useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["security"] })
    queryClient.invalidateQueries({ queryKey: ["security-logs"] })
  }, [queryClient]))

  useWsEvent("otp_destroyer_toggled", useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["accounts"] })
  }, [queryClient]))

  useWsEvent("otp_forward_toggled", useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["accounts"] })
  }, [queryClient]))

  // ── Mutations ──────────────────────────────────────────────────────────────

  const sessionDestroyerMutation = useMutation({
    mutationFn: (enabled: boolean) => securityApi.updateSettings(enabled),
    onSuccess: (_, enabled) => {
      toast.success(`Session Destroyer ${enabled ? "enabled" : "disabled"}`)
      queryClient.invalidateQueries({ queryKey: ["security"] })
    },
    onError: (e) => {
      const msg = (e as Error).message
      toast.error(msg.includes("503") || msg.toLowerCase().includes("bot not running")
        ? "Bot is offline — start the bot first"
        : msg)
    },
  })

  const allowNextMutation = useMutation({
    mutationFn: () => securityApi.allowNextLogin(),
    onSuccess: (res) => toast.success(res.message),
    onError: (e) => {
      const msg = (e as Error).message
      toast.error(msg.includes("503") || msg.toLowerCase().includes("bot not running")
        ? "Bot is offline — start the bot first"
        : msg)
    },
  })

  const syncTrustedMutation = useMutation({
    mutationFn: () => securityApi.syncTrustedSessions(),
    onSuccess: (res) => toast.success(`Synced ${res.trusted_count} trusted sessions`),
    onError: (e) => {
      const msg = (e as Error).message
      toast.error(msg.includes("503") || msg.toLowerCase().includes("bot not running")
        ? "Bot is offline — start the bot first"
        : msg)
    },
  })

  const otpDestroyerMutation = useMutation({
    mutationFn: ({ account_id, enabled }: { account_id: string; enabled: boolean }) =>
      securityApi.toggleOtpDestroyer(account_id, enabled),
    onSuccess: (_, { enabled }) => {
      toast.success(`OTP Destroyer ${enabled ? "enabled" : "disabled"}`)
      queryClient.invalidateQueries({ queryKey: ["accounts"] })
    },
    onError: (e) => {
      const msg = (e as Error).message
      toast.error(msg.includes("503") || msg.toLowerCase().includes("bot not running")
        ? "Bot is offline — start the bot first"
        : msg)
    },
  })

  const otpForwardMutation = useMutation({
    mutationFn: ({ account_id, enabled }: { account_id: string; enabled: boolean }) =>
      securityApi.toggleOtpForward(account_id, enabled),
    onSuccess: (_, { enabled }) => {
      toast.success(`OTP Forward ${enabled ? "enabled" : "disabled"}`)
      queryClient.invalidateQueries({ queryKey: ["accounts"] })
    },
    onError: (e) => {
      const msg = (e as Error).message
      toast.error(msg.includes("503") || msg.toLowerCase().includes("bot not running")
        ? "Bot is offline — start the bot first"
        : msg)
    },
  })

  const tempPassthroughMutation = useMutation({
    mutationFn: (account_id: string) => securityApi.tempPassthrough(account_id),
    onSuccess: () => toast.success("OTP passthrough active for 5 min"),
    onError: (e) => {
      const msg = (e as Error).message
      toast.error(msg.includes("503") || msg.toLowerCase().includes("bot not running")
        ? "Bot is offline — start the bot first"
        : msg)
    },
  })

  const disableTempMutation = useMutation({
    mutationFn: (account_id: string) => securityApi.disableDestroyerTemp(account_id),
    onSuccess: () => toast.success("Destroyer paused for 5 min"),
    onError: (e) => {
      const msg = (e as Error).message
      toast.error(msg.includes("503") || msg.toLowerCase().includes("bot not running")
        ? "Bot is offline — start the bot first"
        : msg)
    },
  })

  const isSessionDestroyerEnabled = security?.settings?.session_destroyer_enabled
    ?? security?.enabled
    ?? false
  const destroyedCount = security?.stats?.destroyed_count ?? 0
  const otpDestroyedCount = security?.stats?.otp_destroyed ?? 0
  const allowNext = security?.settings?.allow_next ?? false

  return (
    <div style={{ zIndex: 75 }} className={cn(
      "fixed inset-0 bg-[#17212b] flex flex-col transition-transform duration-300 ease-in-out",
      isOpen ? "translate-x-0" : "translate-x-full",
    )}>
      <header className="flex items-center gap-4 px-4 py-3 bg-[#17212b] border-b border-white/10">
        <button onClick={onClose} className="p-2 -ml-2 text-gray-400 hover:text-white transition-colors">
          <ArrowLeft className="h-6 w-6" />
        </button>
        <h1 className="text-xl font-medium text-white flex-1">Protection Manager</h1>
        {(destroyedCount > 0 || otpDestroyedCount > 0) && (
          <div className="flex items-center gap-2">
            {destroyedCount > 0 && (
              <span className="text-xs text-red-400 bg-red-500/10 px-2 py-0.5 rounded-full">
                {destroyedCount} sessions
              </span>
            )}
            {otpDestroyedCount > 0 && (
              <span className="text-xs text-orange-400 bg-orange-500/10 px-2 py-0.5 rounded-full">
                {otpDestroyedCount} OTPs
              </span>
            )}
          </div>
        )}
      </header>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">

        {/* ── Session Destroyer ─────────────────────────────────────────────── */}
        <div className="bg-[#242f3d] rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-white/10">
            <p className="text-sky-400 text-sm font-medium">Session Destroyer</p>
            <p className="text-gray-500 text-xs mt-0.5">Terminates unauthorized Telegram sessions automatically</p>
          </div>

          <div className="px-4 py-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center flex-shrink-0">
              <Zap className="h-5 w-5 text-red-400" />
            </div>
            <div className="flex-1">
              <p className="text-white font-medium text-sm">Auto-terminate unauthorized sessions</p>
              {isSessionDestroyerEnabled && destroyedCount > 0 && (
                <p className="text-red-400 text-xs mt-0.5">{destroyedCount} sessions terminated</p>
              )}
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
            <div className="px-4 pb-4 space-y-2">
              <div className="flex items-center gap-2 bg-green-500/10 border border-green-500/30 rounded-lg px-3 py-2">
                <CheckCircle2 className="h-4 w-4 text-green-400 flex-shrink-0" />
                <p className="text-green-400 text-xs flex-1">Active — watching for new sessions</p>
              </div>

              {/* Allow next login */}
              <div className="flex gap-2">
                <button
                  onClick={() => allowNextMutation.mutate()}
                  disabled={allowNextMutation.isPending || allowNext}
                  className={cn(
                    "flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-medium transition-colors",
                    allowNext
                      ? "bg-blue-500/20 text-blue-300 border border-blue-500/30"
                      : "bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 border border-blue-500/20",
                  )}
                >
                  {allowNextMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <LogIn className="h-3.5 w-3.5" />}
                  {allowNext ? "Next login trusted ✓" : "Trust next login"}
                </button>
                <button
                  onClick={() => syncTrustedMutation.mutate()}
                  disabled={syncTrustedMutation.isPending}
                  className="flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-medium bg-white/5 text-gray-400 hover:bg-white/10 border border-white/10 transition-colors"
                >
                  {syncTrustedMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                  Sync trusted
                </button>
              </div>
            </div>
          )}
        </div>

        {/* ── OTP Destroyer + Forward per account ───────────────────────────── */}
        {accounts.length > 0 && (
          <div className="bg-[#242f3d] rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-white/10">
              <p className="text-sky-400 text-sm font-medium">OTP Protection — Per Account</p>
              <p className="text-gray-500 text-xs mt-0.5">Destroyer invalidates codes · Forward sends them to your bot chat</p>
            </div>
            <ul role="list">
              {accounts.map((acc: Account, i) => {
                const otpOn = acc.otp_destroyer_enabled ?? false
                const fwdOn = (acc as any).otp_forward_enabled ?? false

                return (
                  <li key={acc.id} className={cn("px-4 py-3 space-y-2.5", i < accounts.length - 1 && "border-b border-white/5")}>
                    {/* Account header */}
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-full bg-sky-500/20 flex items-center justify-center flex-shrink-0 text-sky-400 font-bold text-sm">
                        {(acc.name || acc.phone || "?").charAt(0).toUpperCase()}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-white text-sm font-medium truncate">{acc.name || acc.phone}</p>
                        {acc.phone && acc.name !== acc.phone && (
                          <p className="text-gray-500 text-xs truncate">{acc.phone}</p>
                        )}
                      </div>
                    </div>

                    {/* OTP Destroyer toggle */}
                    <div className="flex items-center justify-between bg-[#1a2535] rounded-lg px-3 py-2">
                      <div className="flex items-center gap-2">
                        <Shield className="h-4 w-4 text-red-400 flex-shrink-0" />
                        <div>
                          <p className="text-white text-xs font-medium">OTP Destroyer</p>
                          <p className="text-gray-500 text-[10px]">Invalidates login codes</p>
                        </div>
                      </div>
                      <Switch
                        checked={otpOn}
                        onCheckedChange={(v) => otpDestroyerMutation.mutate({ account_id: acc.id, enabled: v })}
                        disabled={otpDestroyerMutation.isPending}
                      />
                    </div>

                    {/* OTP Forward toggle — only when destroyer is OFF */}
                    {!otpOn && (
                      <div className="flex items-center justify-between bg-[#1a2535] rounded-lg px-3 py-2">
                        <div className="flex items-center gap-2">
                          <Forward className="h-4 w-4 text-blue-400 flex-shrink-0" />
                          <div>
                            <p className="text-white text-xs font-medium">OTP Forward</p>
                            <p className="text-gray-500 text-[10px]">Send codes to bot chat</p>
                          </div>
                        </div>
                        <Switch
                          checked={fwdOn}
                          onCheckedChange={(v) => otpForwardMutation.mutate({ account_id: acc.id, enabled: v })}
                          disabled={otpForwardMutation.isPending}
                        />
                      </div>
                    )}

                    {/* Quick actions when destroyer is ON */}
                    {otpOn && (
                      <div className="flex gap-2">
                        <button
                          onClick={() => tempPassthroughMutation.mutate(acc.id)}
                          disabled={tempPassthroughMutation.isPending}
                          className="flex-1 flex items-center justify-center gap-1.5 text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-lg py-2 hover:bg-amber-500/20 transition-colors"
                        >
                          {tempPassthroughMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Eye className="h-3.5 w-3.5" />}
                          Temp OTP (5m)
                        </button>
                        <button
                          onClick={() => disableTempMutation.mutate(acc.id)}
                          disabled={disableTempMutation.isPending}
                          className="flex-1 flex items-center justify-center gap-1.5 text-xs text-orange-400 bg-orange-500/10 border border-orange-500/20 rounded-lg py-2 hover:bg-orange-500/20 transition-colors"
                        >
                          {disableTempMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Timer className="h-3.5 w-3.5" />}
                          Pause (5m)
                        </button>
                      </div>
                    )}
                  </li>
                )
              })}
            </ul>
          </div>
        )}

        {/* ── Recent Events ─────────────────────────────────────────────────── */}
        {logs.length > 0 && (
          <div className="bg-[#242f3d] rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-white/10">
              <p className="text-sky-400 text-sm font-medium">Recent Events</p>
            </div>
            <ul role="list">
              {logs.map((log, i) => (
                <li key={i} className={cn("px-4 py-3 flex items-start gap-3", i < logs.length - 1 && "border-b border-white/5")}>
                  <AlertTriangle className="h-4 w-4 text-orange-400 mt-0.5 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-white text-sm">Session destroyed — {log.device ?? "Unknown device"}</p>
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

        <p className="text-gray-600 text-xs text-center">All changes apply to the running bot immediately.</p>
      </div>
    </div>
  )
}
