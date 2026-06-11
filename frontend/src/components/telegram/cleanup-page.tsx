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
} from "lucide-react"
import { cn } from "@/lib/utils"
import { messagingApi } from "@/lib/api"
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
  { icon: MessageSquare, label: "personal", description: "Direct messages with users" },
  { icon: Bot, label: "bots", description: "Conversations with bots" },
  { icon: Send, label: "telegram", description: "Telegram service chats" },
  { icon: AlertCircle, label: "spambot", description: "@spambot conversations" },
  { icon: Mail, label: "my_messages", description: "Delete your sent messages from groups" },
  { icon: LogOut, label: "channels", description: "Leave all channels" },
  { icon: Users, label: "groups", description: "Leave all groups" },
  { icon: Trash2, label: "owned_groups", description: "Delete groups you own" },
  { icon: Radio, label: "owned_channels", description: "Delete channels you own" },
  { icon: Flame, label: "all", description: "Everything above — full cleanup" },
]

export function CleanupPage({ isOpen, onClose }: CleanupPageProps) {
  const { activeAccount } = useUser()
  const [confirmTarget, setConfirmTarget] = useState<string | null>(null)
  const [loading, setLoading] = useState<string | null>(null)

  const handleCleanup = async (type: string) => {
    if (!activeAccount) {
      toast.error("No active account selected")
      return
    }
    setLoading(type)
    try {
      // Cleanup is implemented as a bulk message to a special target
      // The backend handles the actual cleanup via the messaging system
      await messagingApi.send(activeAccount.name, "cleanup_bot", `cleanup:${type}`)
      toast.success(`Cleanup started: ${type}`)
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setLoading(null)
      setConfirmTarget(null)
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
          {!activeAccount && (
            <div className="mx-4 mt-4 bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4">
              <p className="text-yellow-400 text-sm text-center">
                Select an active account first
              </p>
            </div>
          )}

          <div className="px-4 py-4 border-b border-white/10">
            <p className="text-base font-semibold text-white flex items-center gap-3">
              <Trash2 className="h-5 w-5 text-[#2AABEE]" />
              What would you like to clean?
            </p>
            {activeAccount && (
              <p className="text-gray-400 text-xs mt-1">Account: {activeAccount.name}</p>
            )}
          </div>

          <ul role="list">
            {cleanupItems.map(({ icon: Icon, label, description }) => (
              <li key={label} className="border-b border-white/10">
                <button
                  onClick={() => setConfirmTarget(label)}
                  disabled={!activeAccount || loading === label}
                  className="w-full flex items-center gap-4 px-4 py-4 hover:bg-white/5 transition-colors group disabled:opacity-50"
                >
                  {loading === label ? (
                    <Loader2 className="h-6 w-6 text-[#2AABEE] animate-spin flex-shrink-0" />
                  ) : (
                    <Icon className="h-6 w-6 text-[#2AABEE] transition-colors flex-shrink-0" />
                  )}
                  <div className="flex-1 text-left">
                    <span className="text-[15px] font-semibold block text-white">{label}</span>
                    <span className="text-[13px] text-gray-400">{description}</span>
                  </div>
                </button>
              </li>
            ))}
          </ul>

          <div className="px-4 py-4 border-t border-white/10">
            <div className="flex items-center gap-3 px-4 py-3 bg-[#2AABEE]/10 border border-[#2AABEE]/30 rounded-lg">
              <AlertCircle className="h-5 w-5 text-[#2AABEE] flex-shrink-0" />
              <p className="text-sm text-[#2AABEE] font-medium">
                These actions cannot be undone!
              </p>
            </div>
          </div>
        </div>
      </div>

      <AlertDialog open={!!confirmTarget} onOpenChange={() => setConfirmTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirm Cleanup</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to clean <strong>{targetItem?.label}</strong>?{" "}
              {targetItem?.description}. This action <strong>cannot be undone</strong>.
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


