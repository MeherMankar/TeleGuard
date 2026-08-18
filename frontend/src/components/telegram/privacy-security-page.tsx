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
  { value: "contacts",  label: "My Contacts" },
  { value: "nobody",    label: "Nobody" },
]

function PrivacyPicker({ label, current, onSave, onBack, loading }: PickerProps) {
  const [selected, setSelected] = useState(current)

  return (
    <div className="fixed inset-0 z-[95] bg-background flex flex-col">
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
              <span className={cn("text-[15px]", selected === opt.value ? "text-primary font-medium" : "text-foreground")}>
                {opt.label}
              </span>
              {selected === opt.value && (
                <span className="w-5 h-5 rounded-full bg-primary flex items-center justify-center flex-shrink-0">
                  <span className="w-2 h-2 rounded-full bg-white" />
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
  if (v === "contacts")  return "My Contacts"
  if (v === "nobody")    return "Nobody"
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

  const handleSave = useCallback((key: string, value: string) => {
    mutation.mutate({ key, value })
  }, [mutation])

  const s = data?.settings

  const privacyRows: { icon: React.ElementType; label: string; key: keyof PrivacySettings; iconBg: string }[] = [
    { icon: Eye,       label: "Last Seen & Online",      key: "last_seen",      iconBg: "bg-sky-500" },
    { icon: Phone,     label: "Phone Number",             key: "phone",          iconBg: "bg-emerald-500" },
    { icon: Users,     label: "Profile Photo",            key: "profile_photo",  iconBg: "bg-rose-500" },
    { icon: AtSign,    label: "Bio",                      key: "bio",            iconBg: "bg-cyan-500" },
    { icon: Link2,     label: "Forwarded Messages",       key: "forwards",       iconBg: "bg-indigo-500" },
    { icon: UserPlus,  label: "Who can add me to groups", key: "groups",         iconBg: "bg-violet-500" },
    { icon: PhoneCall, label: "Calls",                    key: "calls",          iconBg: "bg-orange-500" },
    { icon: Mic,       label: "Voice Messages",           key: "voice_messages", iconBg: "bg-teal-500" },
  ]

  return (
    <>
      <div
        style={{ zIndex: 85 }}
        className={cn(
          "fixed inset-0 flex flex-col bg-background transition-transform duration-300 ease-in-out",
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
              <p className="text-red-400 text-sm">Failed to load privacy settings. Is the bot running?</p>
            </div>
          )}

          {!isLoading && !isError && s && (
            <>
              {/* Privacy */}
              <div className="mx-3 mt-4">
                <p className="px-4 pb-2 text-sky-400 text-[13px] font-semibold uppercase tracking-wide">Privacy</p>
                <div className="rounded-2xl bg-card overflow-hidden border border-border/40">
                  {privacyRows.map(({ icon: Icon, label, key, iconBg }, i) => (
                    <button
                      key={key}
                      onClick={() => setPicker({ key, label })}
                      className={cn(
                        "w-full flex items-center gap-3.5 px-4 py-3 hover:bg-secondary/30 transition-colors text-left",
                        i < privacyRows.length - 1 && "border-b border-border/30",
                      )}
                    >
                      <div className={cn("w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0", iconBg)}>
                        <Icon className="h-5 w-5 text-white" />
                      </div>
                      <span className="flex-1 text-[15px] text-foreground font-medium">{label}</span>
                      <span className="text-[14px] text-sky-400 mr-1">{optionLabel(s[key])}</span>
                      <ChevronRight className="h-5 w-5 text-muted-foreground flex-shrink-0" />
                    </button>
                  ))}
                </div>
                <p className="px-4 pt-2 text-[13px] text-muted-foreground">Change who can see your personal info.</p>
              </div>

              {/* Security */}
              <div className="mx-3 mt-4">
                <p className="px-4 pb-2 text-sky-400 text-[13px] font-semibold uppercase tracking-wide">Security</p>
                <div className="rounded-2xl bg-card overflow-hidden border border-border/40">
                  <div className="flex items-center gap-3.5 px-4 py-3 border-b border-border/30">
                    <div className="w-10 h-10 rounded-full bg-emerald-500 flex items-center justify-center flex-shrink-0">
                      <Key className="h-5 w-5 text-white" />
                    </div>
                    <span className="flex-1 text-[15px] text-foreground font-medium">Two-Step Verification</span>
                    <span className={cn(
                      "text-[14px] font-medium",
                      data.twofa_enabled ? "text-emerald-400" : "text-muted-foreground",
                    )}>
                      {data.twofa_enabled ? "On" : "Off"}
                    </span>
                  </div>
                  <button
                    onClick={() => setIsSessionsOpen(true)}
                    className="w-full flex items-center gap-3.5 px-4 py-3 hover:bg-secondary/30 transition-colors text-left"
                  >
                    <div className="w-10 h-10 rounded-full bg-cyan-500 flex items-center justify-center flex-shrink-0">
                      <Smartphone className="h-5 w-5 text-white" />
                    </div>
                    <span className="flex-1 text-[15px] text-foreground font-medium">Active Sessions</span>
                    <ChevronRight className="h-5 w-5 text-muted-foreground flex-shrink-0" />
                  </button>
                </div>
              </div>

              {/* Danger zone */}
              <div className="mx-3 mt-4">
                <div className="rounded-2xl bg-card overflow-hidden border border-border/40">
                  <button className="w-full flex items-center gap-3.5 px-4 py-3 hover:bg-secondary/30 transition-colors text-left opacity-50 cursor-not-allowed">
                    <div className="w-10 h-10 rounded-full bg-red-500 flex items-center justify-center flex-shrink-0">
                      <Trash2 className="h-5 w-5 text-white" />
                    </div>
                    <div className="flex-1">
                      <p className="text-[15px] text-red-500 font-medium">Delete My Account</p>
                      <p className="text-[13px] text-muted-foreground">Use the official Telegram app</p>
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
      <SessionManagerPage
        isOpen={isSessionsOpen}
        onClose={() => setIsSessionsOpen(false)}
      />
    </>
  )
}
