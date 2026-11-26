import { useState, useCallback } from "react"
import {
  ArrowLeft,
  ChevronRight,
  Eye,
  Phone,
  UserPlus,
  Users,
  AtSign,
  Link2,
  Trash2,
  Key,
  Smartphone,
  Loader2,
  AlertCircle,
  PhoneCall,
  Mic,
  Check,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { privacyApi, apiErrorMessage, type PrivacySettings } from "@/lib/api"
import { useUser } from "@/contexts/user-context"
import { toast } from "sonner"
import { SessionManagerPage } from "./session-manager-page"

interface PrivacySecurityPageProps {
  isOpen: boolean
  onClose: () => void
}

// ── Option picker sub-page ───────────────────────────────────────────────────

interface PickerProps {
  label: string
  current: string
  onSave: (v: string) => void
  onBack: () => void
  loading: boolean
}

const OPTIONS = [
  { value: "everybody", label: "Everybody" },
  { value: "contacts", label: "My Contacts" },
  { value: "nobody", label: "Nobody" },
]

function PrivacyPicker({ label, current, onSave, onBack, loading }: PickerProps) {
  const [selected, setSelected] = useState(current)

  return (
    <div className="tg-screen fixed inset-0 z-[95] bg-background flex flex-col">
      <div className="flex items-center gap-3 px-2 py-3 bg-card/95 backdrop-blur border-b border-border/40 sticky top-0">
        <button onClick={onBack} className="p-2 text-foreground">
          <ArrowLeft className="h-6 w-6" />
        </button>
        <h1 className="flex-1 text-lg font-semibold text-foreground">{label}</h1>
        {loading && <Loader2 className="h-5 w-5 text-primary animate-spin mr-2" />}
      </div>

      <div className="flex-1 overflow-y-auto">
        <p className="px-4 pt-5 pb-2 text-sm text-muted-foreground">Who can see this?</p>
        <div className="mx-3 rounded-2xl bg-card border border-border/40 overflow-hidden">
          {OPTIONS.map((opt, i) => (
            <button
              key={opt.value}
              onClick={() => {
                setSelected(opt.value)
                onSave(opt.value)
              }}
              disabled={loading}
              className={cn(
                "w-full flex items-center justify-between px-4 py-3 hover:bg-secondary/30 transition-colors",
                i < OPTIONS.length - 1 && "border-b border-border/30",
              )}
            >
              <span
                className={cn(
                  "text-[15px]",
                  selected === opt.value ? "text-primary font-medium" : "text-foreground",
                )}
              >
                {opt.label}
              </span>
              {selected === opt.value && (
                <span className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
                  <Check className="h-3 w-3" />
                </span>
              )}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Label helpers ────────────────────────────────────────────────────────────

function optionLabel(v: string | undefined): string {
  if (!v || v === "unknown") return "—"
  if (v === "everybody") return "Everybody"
  if (v === "contacts") return "My Contacts"
  if (v === "nobody") return "Nobody"
  return v
}

// ── Main page ────────────────────────────────────────────────────────────────

export function PrivacySecurityPage({ isOpen, onClose }: PrivacySecurityPageProps) {
  const { activeAccount } = useUser()
  const queryClient = useQueryClient()
  const [isSessionsOpen, setIsSessionsOpen] = useState(false)
  const [picker, setPicker] = useState<{ key: keyof PrivacySettings; label: string } | null>(null)

  const qKey = ["privacy", activeAccount?.name]

  const { data, isLoading, isError } = useQuery({
    queryKey: qKey,
    queryFn: () => privacyApi.get(activeAccount!.name),
    enabled: isOpen && !!activeAccount,
    staleTime: 60_000,
  })

  const mutation = useMutation({
    mutationFn: ({ key, value }: { key: string; value: string }) =>
      privacyApi.update(activeAccount!.name, key, value),
    onSuccess: (_, { key, value }) => {
      queryClient.setQueryData(qKey, (old: typeof data) =>
        old ? { ...old, settings: { ...old.settings, [key]: value } } : old,
      )
      toast.success("Privacy setting updated")
      setPicker(null)
    },
    onError: (e) => toast.error(apiErrorMessage(e)),
  })

  const handleSave = useCallback(
    (key: string, value: string) => {
      mutation.mutate({ key, value })
    },
    [mutation],
  )

  const s = data?.settings

  const privacyRows: {
    icon: React.ElementType
    label: string
    key: keyof PrivacySettings
  }[] = [
    { icon: Eye, label: "Last seen and online", key: "last_seen" },
    { icon: Phone, label: "Phone number", key: "phone" },
    { icon: Users, label: "Profile photo", key: "profile_photo" },
    { icon: AtSign, label: "Bio", key: "bio" },
    { icon: Link2, label: "Forwarded messages", key: "forwards" },
    { icon: UserPlus, label: "Who can add me to groups", key: "groups" },
    { icon: PhoneCall, label: "Calls", key: "calls" },
    { icon: Mic, label: "Voice messages", key: "voice_messages" },
  ]

  return (
    <>
      <div
        style={{ zIndex: 85 }}
        className={cn(
          "tg-screen fixed inset-0 flex flex-col bg-background transition-transform duration-300 ease-in-out",
          isOpen ? "translate-x-0" : "translate-x-full",
        )}
      >
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center gap-3 px-2 py-3 bg-card/95 backdrop-blur border-b border-border/40">
          <button onClick={onClose} aria-label="Back" className="p-2 text-foreground">
            <ArrowLeft className="h-6 w-6" />
          </button>
          <h1 className="flex-1 text-[20px] font-semibold text-foreground">Privacy and Security</h1>
        </div>

        <div className="flex-1 overflow-y-auto pb-8">
          {/* No account */}
          {!activeAccount && (
            <div className="mx-4 mt-6 bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4">
              <p className="text-yellow-400 text-sm text-center">Select an active account first</p>
            </div>
          )}

          {/* Loading */}
          {isLoading && activeAccount && (
            <div className="flex justify-center py-20">
              <Loader2 className="h-8 w-8 text-primary animate-spin" />
            </div>
          )}

          {/* Error */}
          {isError && !isLoading && (
            <div className="mx-4 mt-6 flex items-center gap-3 bg-red-500/10 border border-red-500/20 rounded-xl p-4">
              <AlertCircle className="h-5 w-5 text-red-400 flex-shrink-0" />
              <p className="text-red-400 text-sm">
                Could not load privacy settings. Check your connection.
              </p>
            </div>
          )}

          {!isLoading && !isError && s && (
            <>
              {/* Privacy */}
              <div className="mx-3 mt-4">
                <p className="px-4 pb-2 text-[#a3a9b8] text-[13px] font-medium">Privacy</p>
                <div className="overflow-hidden rounded-xl border border-border/50 bg-card">
                  {privacyRows.map(({ icon: Icon, label, key }, i) => (
                    <button
                      key={key}
                      onClick={() => setPicker({ key, label })}
                      className={cn(
                        "w-full flex items-center gap-3 px-4 py-3 hover:bg-secondary/30 transition-colors text-left",
                        i < privacyRows.length - 1 && "border-b border-border/30",
                      )}
                    >
                      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-secondary">
                        <Icon className="h-4 w-4 text-muted-foreground" />
                      </div>
                      <span className="flex-1 text-[15px] text-foreground">{label}</span>
                      <span className="mr-1 text-sm text-muted-foreground">
                        {optionLabel(s[key])}
                      </span>
                      <ChevronRight className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                    </button>
                  ))}
                </div>
                <p className="px-4 pt-2 text-[13px] text-muted-foreground">
                  Change who can see your personal info.
                </p>
              </div>

              {/* Security */}
              <div className="mx-3 mt-4">
                <p className="px-4 pb-2 text-[#a3a9b8] text-[13px] font-medium">Security</p>
                <div className="overflow-hidden rounded-xl border border-border/50 bg-card">
                  <div className="flex items-center gap-3.5 px-4 py-3 border-b border-border/30">
                    <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-secondary">
                      <Key className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <span className="flex-1 text-[15px] text-foreground font-medium">
                      Two-Step Verification
                    </span>
                    <span
                      className={cn(
                        "text-[14px] font-medium",
                        data.twofa_enabled ? "text-emerald-400" : "text-muted-foreground",
                      )}
                    >
                      {data.twofa_enabled ? "On" : "Off"}
                    </span>
                  </div>
                  <button
                    onClick={() => setIsSessionsOpen(true)}
                    className="w-full flex items-center gap-3.5 px-4 py-3 hover:bg-secondary/30 transition-colors text-left"
                  >
                    <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-secondary">
                      <Smartphone className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <span className="flex-1 text-[15px] text-foreground font-medium">
                      Active Sessions
                    </span>
                    <ChevronRight className="h-5 w-5 text-muted-foreground flex-shrink-0" />
                  </button>
                </div>
              </div>

              {/* Danger zone */}
              <div className="mx-3 mt-4">
                <div className="overflow-hidden rounded-xl border border-border/50 bg-card">
                  <button className="w-full flex items-center gap-3.5 px-4 py-3 hover:bg-secondary/30 transition-colors text-left opacity-50 cursor-not-allowed">
                    <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-secondary">
                      <Trash2 className="h-4 w-4 text-red-400" />
                    </div>
                    <div className="flex-1">
                      <p className="text-[15px] text-red-500 font-medium">Delete My Account</p>
                      <p className="text-[13px] text-muted-foreground">
                        Use the official Telegram app
                      </p>
                    </div>
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Option picker overlay */}
      {picker && (
        <PrivacyPicker
          label={picker.label}
          current={s?.[picker.key] ?? "everybody"}
          onSave={(v) => handleSave(picker.key, v)}
          onBack={() => !mutation.isPending && setPicker(null)}
          loading={mutation.isPending}
        />
      )}

      {/* Sessions sub-page */}
      <SessionManagerPage isOpen={isSessionsOpen} onClose={() => setIsSessionsOpen(false)} />
    </>
  )
}
