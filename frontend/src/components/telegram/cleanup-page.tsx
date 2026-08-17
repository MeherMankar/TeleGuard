import { useState } from "react"
import {
  ArrowLeft,
  Trash2,
  MessageSquare,
  Bot,
  Send,
  AlertCircle,
  Mail,
  LogOut,
  Users,
  Radio,
  Flame,
  Loader2,
  CheckCircle2,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { cleanupApi, apiErrorMessage } from "@/lib/api"
import { useUser } from "@/contexts/user-context"
import { toast } from "sonner"
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

interface CleanupPageProps {
  isOpen: boolean
  onClose: () => void
}

const cleanupItems = [
  { icon: MessageSquare, label: "personal",       description: "Delete all direct message conversations" },
  { icon: Bot,          label: "bots",            description: "Delete all bot conversations" },
  { icon: Send,         label: "telegram",        description: "Delete Telegram service chats" },
  { icon: AlertCircle,  label: "spambot",         description: "Delete @spambot conversation" },
  { icon: Mail,         label: "my_messages",     description: "Delete your sent messages from groups" },
  { icon: LogOut,       label: "channels",        description: "Leave all channels" },
  { icon: Users,        label: "groups",          description: "Leave all groups" },
  { icon: Trash2,       label: "owned_groups",    description: "Delete groups you own" },
  { icon: Radio,        label: "owned_channels",  description: "Delete channels you own" },
  { icon: Flame,        label: "all",             description: "Everything above — full cleanup", danger: true },
]

export function CleanupPage({ isOpen, onClose }: CleanupPageProps) {
  const { activeAccount } = useUser()
  const [confirmTarget, setConfirmTarget] = useState<string | null>(null)
  const [loading, setLoading] = useState<string | null>(null)
  const [resultMsg, setResultMsg] = useState<string | null>(null)

  const handleCleanup = async (type: string) => {
    if (!activeAccount) {
      toast.error("No active account selected")
      return
    }
    setConfirmTarget(null)
    setLoading(type)
    setResultMsg(null)
    try {
      const res = await cleanupApi.run(activeAccount.name, type)
      setResultMsg(res.message)
      toast.success(`Cleanup complete`)
    } catch (e) {
      toast.error(apiErrorMessage(e))
    } finally {
      setLoading(null)
    }
  }

  const targetItem = cleanupItems.find((i) => i.label === confirmTarget)

  return (
    <>
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
            aria-label="Go back"
          >
            <ArrowLeft className="h-6 w-6" />
          </button>
          <h1 className="text-xl font-medium text-white">Cleanup</h1>
        </header>

        <div className="flex-1 overflow-y-auto">
          {/* No account warning */}
          {!activeAccount && (
            <div className="mx-4 mt-4 bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4">
              <p className="text-yellow-400 text-sm text-center">Select an active account first</p>
            </div>
          )}

          {/* Account label */}
          {activeAccount && (
            <div className="px-4 pt-4 pb-2">
              <p className="text-gray-400 text-xs">
                Account: <span className="text-white font-medium">{activeAccount.name}</span>
              </p>
            </div>
          )}

          {/* Result box */}
          {resultMsg && (
            <div className="mx-4 mb-2 bg-green-500/10 border border-green-500/30 rounded-xl p-4 flex items-start gap-3">
              <CheckCircle2 className="h-5 w-5 text-green-400 flex-shrink-0 mt-0.5" />
              <p className="text-green-400 text-sm whitespace-pre-wrap">{resultMsg}</p>
            </div>
          )}

          {/* Cleanup items */}
          <ul role="list" className="mt-1">
            {cleanupItems.map(({ icon: Icon, label, description, danger }) => (
              <li key={label} className="border-b border-white/5">
                <button
                  onClick={() => setConfirmTarget(label)}
                  disabled={!activeAccount || loading !== null}
                  className={cn(
                    "w-full flex items-center gap-4 px-4 py-4 hover:bg-white/5 transition-colors disabled:opacity-50",
                    danger && "hover:bg-red-500/5",
                  )}
                >
                  {loading === label ? (
                    <Loader2 className="h-5 w-5 text-[#2AABEE] animate-spin flex-shrink-0" />
                  ) : (
                    <Icon className={cn(
                      "h-5 w-5 flex-shrink-0",
                      danger ? "text-red-400" : "text-[#2AABEE]",
                    )} />
                  )}
                  <div className="flex-1 text-left">
                    <p className={cn(
                      "text-[15px] font-medium",
                      danger ? "text-red-400" : "text-white",
                    )}>
                      {label}
                    </p>
                    <p className="text-[13px] text-gray-500 mt-0.5">{description}</p>
                  </div>
                </button>
              </li>
            ))}
          </ul>

          {/* Warning footer */}
          <div className="px-4 py-4">
            <div className="flex items-center gap-3 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl">
              <AlertCircle className="h-4 w-4 text-red-400 flex-shrink-0" />
              <p className="text-red-400 text-xs">
                These actions are <strong>permanent</strong> and cannot be undone.
                Cleanup runs on your Telegram account directly.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Confirm dialog */}
      <AlertDialog open={!!confirmTarget} onOpenChange={() => setConfirmTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirm Cleanup</AlertDialogTitle>
            <AlertDialogDescription>
              Run <strong>{targetItem?.label}</strong> cleanup on{" "}
              <strong>{activeAccount?.name}</strong>?{" "}
              {targetItem?.description}.{" "}
              This action <strong>cannot be undone</strong>.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => confirmTarget && handleCleanup(confirmTarget)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Yes, Clean
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
