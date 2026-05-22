import { useState } from "react"
import { ArrowLeft, Loader2, Monitor, Smartphone, Globe, Trash2, ShieldCheck } from "lucide-react"
import { cn } from "@/lib/utils"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { sessionsApi, type Session } from "@/lib/api"
import { toast } from "sonner"
import { useWsEvent } from "@/hooks/use-ws-event"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"

interface SessionManagerPageProps {
  isOpen: boolean
  onClose: () => void
}

export function SessionManagerPage({ isOpen, onClose }: SessionManagerPageProps) {
  const queryClient = useQueryClient()
  const [revokeTarget, setRevokeTarget] = useState<Session | null>(null)

  const { data: sessions = [], isLoading, error } = useQuery({
    queryKey: ["sessions"],
    queryFn: sessionsApi.list,
    enabled: isOpen,
    refetchInterval: isOpen ? 30_000 : false,
  })

  // Auto-refresh when bot destroys a session
  useWsEvent("session_revoked", () => {
    queryClient.invalidateQueries({ queryKey: ["sessions"] })
  })

  const revokeMutation = useMutation({
    mutationFn: ({ account_id, session_hash }: { account_id: string; session_hash: string }) =>
      sessionsApi.revoke(account_id, session_hash),
    onSuccess: () => {
      toast.success("Session revoked")
      queryClient.invalidateQueries({ queryKey: ["sessions"] })
      setRevokeTarget(null)
    },
    onError: (e) => toast.error((e as Error).message),
  })

  const grouped = sessions.reduce<Record<string, Session[]>>((acc, s) => {
    const key = s.account_name ?? "Unknown"
    if (!acc[key]) acc[key] = []
    acc[key].push(s)
    return acc
  }, {})

  return (
    <>
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
          <h1 className="text-xl font-medium text-white">Active Sessions</h1>
        </header>

        <div className="flex-1 overflow-y-auto">
          {isLoading && (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="h-8 w-8 text-[#2AABEE] animate-spin" />
            </div>
          )}

          {error && (
            <div className="px-4 py-8 text-center text-red-400 text-sm">
              Failed to load sessions. Check your connection.
            </div>
          )}

          {!isLoading && !error && sessions.length === 0 && (
            <div className="px-4 py-12 text-center">
              <ShieldCheck className="h-12 w-12 text-[#2AABEE] mx-auto mb-3" />
              <p className="text-white font-medium">No active sessions found</p>
              <p className="text-gray-400 text-sm mt-1">Add an account to see its sessions</p>
            </div>
          )}

          {Object.entries(grouped).map(([accountName, accountSessions]) => (
            <div key={accountName}>
              <div className="px-4 py-3 bg-[#0e1621]">
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  {accountName}
                </p>
              </div>
              <ul role="list">
                {accountSessions.map((session, i) => (
                  <li key={i} className="border-b border-white/10">
                    <div className="flex items-center gap-4 px-4 py-4">
                      <div className="w-10 h-10 rounded-full bg-[#2AABEE]/20 flex items-center justify-center flex-shrink-0">
                        {session.platform?.toLowerCase().includes("android") ||
                        session.platform?.toLowerCase().includes("ios") ? (
                          <Smartphone className="h-5 w-5 text-[#2AABEE]" />
                        ) : (
                          <Monitor className="h-5 w-5 text-[#2AABEE]" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-white font-medium text-sm truncate">
                          {session.device_model ?? session.app_name ?? "Unknown Device"}
                        </p>
                        <p className="text-gray-400 text-xs truncate">
                          {session.platform} {session.system_version}
                        </p>
                        <div className="flex items-center gap-2 mt-1">
                          <Globe className="h-3 w-3 text-gray-500" />
                          <span className="text-gray-500 text-xs">
                            {session.ip ?? "Unknown IP"} · {session.country ?? ""}
                          </span>
                        </div>
                        {session.date_active && (
                          <p className="text-gray-600 text-xs mt-0.5">
                            Last active: {new Date(session.date_active).toLocaleDateString()}
                          </p>
                        )}
                      </div>
                      {session.hash != null && (
                        <button
                          onClick={() => setRevokeTarget(session)}
                          className="p-2 text-red-400 hover:text-red-300 transition-colors flex-shrink-0"
                          aria-label="Revoke session"
                        >
                          <Trash2 className="h-5 w-5" />
                        </button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>

      <AlertDialog open={!!revokeTarget} onOpenChange={() => setRevokeTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Revoke Session</AlertDialogTitle>
            <AlertDialogDescription>
              This will terminate the session on{" "}
              <strong>{revokeTarget?.device_model ?? "this device"}</strong>. This action cannot
              be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (revokeTarget?.account_id && revokeTarget.hash != null) {
                  revokeMutation.mutate({
                    account_id: revokeTarget.account_id,
                    session_hash: String(revokeTarget.hash),
                  })
                }
              }}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {revokeMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Revoke"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
