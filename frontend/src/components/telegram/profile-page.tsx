import { useState } from "react"
import {
  X, Pencil, Phone, User, AtSign, Server, Loader2,
  BadgeCheck, Sparkles, Copy, CheckCheck,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useUser } from "@/contexts/user-context"
import { accountsApi, chatsApi } from "@/lib/api"
import { useQuery } from "@tanstack/react-query"
import { toast } from "sonner"

interface ProfilePageProps {
  isOpen: boolean
  onClose: () => void
}

const DC_LOCATIONS: Record<number, string> = {
  1: "Miami, USA",
  2: "Amsterdam, Netherlands",
  3: "Miami, USA",
  4: "Amsterdam, Netherlands",
  5: "Singapore, SG",
}

export function ProfilePage({ isOpen, onClose }: ProfilePageProps) {
  const { activeAccount } = useUser()
  const [copied, setCopied] = useState<string | null>(null)

  const { data: profile, isLoading, error } = useQuery({
    queryKey: ["profile", activeAccount?.name],
    queryFn: () => accountsApi.profile(activeAccount!.name),
    enabled: isOpen && !!activeAccount,
    staleTime: 60_000,
  })

  const photoUrl = profile?.has_photo && activeAccount
    ? chatsApi.photoUrl(activeAccount.name, profile.id)
    : null

  const displayName = profile
    ? `${profile.first_name} ${profile.last_name}`.trim() || profile.username || profile.phone
    : activeAccount?.name ?? "—"

  const copyToClipboard = (value: string, label: string) => {
    navigator.clipboard.writeText(value).then(() => {
      setCopied(label)
      toast.success(`${label} copied`)
      setTimeout(() => setCopied(null), 2000)
    })
  }

  return (
    <div
      style={{ zIndex: 75 }}
      className={cn(
        "fixed inset-0 bg-[#17212b] flex flex-col transition-transform duration-300 ease-in-out overflow-y-auto",
        isOpen ? "translate-x-0" : "translate-x-full",
      )}
    >
      {/* Top bar */}
      <div className="flex items-center justify-between px-4 pt-5 pb-3 sticky top-0 bg-[#17212b] z-10 border-b border-white/10">
        <button onClick={onClose} className="p-2 text-gray-400 hover:text-white transition-colors">
          <X className="h-5 w-5" />
        </button>
        <h1 className="text-white font-medium">My Profile</h1>
        <button className="p-2 text-gray-400 hover:text-white transition-colors opacity-50">
          <Pencil className="h-5 w-5" />
        </button>
      </div>

      {isLoading && (
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="h-8 w-8 text-[#2AABEE] animate-spin" />
        </div>
      )}

      {error && !isLoading && (
        <div className="flex-1 flex flex-col items-center justify-center px-6 text-center">
          <p className="text-gray-400 text-sm">Could not load profile</p>
          <p className="text-gray-600 text-xs mt-1">Ensure the account is connected</p>
        </div>
      )}

      {profile && !isLoading && (
        <>
          {/* Avatar + name */}
          <div className="flex flex-col items-center py-8 bg-[#17212b]">
            <div className="w-28 h-28 rounded-full overflow-hidden mb-4 border-4 border-[#2AABEE]/30">
              {photoUrl ? (
                <img
                  src={photoUrl}
                  alt={displayName}
                  className="w-full h-full object-cover"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none" }}
                />
              ) : (
                <div className="w-full h-full bg-gradient-to-br from-sky-500 to-blue-700 flex items-center justify-center text-4xl font-bold text-white">
                  {displayName.charAt(0).toUpperCase()}
                </div>
              )}
            </div>

            <div className="flex items-center gap-2 mb-1">
              <h1 className="text-xl font-semibold text-white">{displayName}</h1>
              {profile.verified && <BadgeCheck className="h-5 w-5 text-[#2AABEE]" />}
              {profile.premium && <Sparkles className="h-5 w-5 text-amber-400" />}
            </div>

            {profile.username && (
              <p className="text-[#2AABEE] text-sm">@{profile.username}</p>
            )}
          </div>

          {/* Info cards */}
          <div className="px-4 space-y-3 pb-8">
            {/* Phone */}
            {profile.phone && (
              <InfoRow
                icon={<Phone className="h-5 w-5 text-[#2AABEE]" />}
                label="Mobile"
                value={`+${profile.phone}`}
                onCopy={() => copyToClipboard(`+${profile.phone}`, "Phone")}
                copied={copied === "Phone"}
              />
            )}

            {/* Bio */}
            {profile.bio && (
              <InfoRow
                icon={<User className="h-5 w-5 text-[#2AABEE]" />}
                label="Bio"
                value={profile.bio}
                multiline
              />
            )}

            {/* Username */}
            {profile.username && (
              <InfoRow
                icon={<AtSign className="h-5 w-5 text-[#2AABEE]" />}
                label="Username"
                value={`@${profile.username}`}
                onCopy={() => copyToClipboard(`@${profile.username}`, "Username")}
                copied={copied === "Username"}
              />
            )}

            {/* Telegram ID */}
            <InfoRow
              icon={<Server className="h-5 w-5 text-[#2AABEE]" />}
              label={profile.dc_id ? `DC${profile.dc_id} · ${DC_LOCATIONS[profile.dc_id] ?? "Unknown"}` : "Telegram ID"}
              value={String(profile.id)}
              onCopy={() => copyToClipboard(String(profile.id), "ID")}
              copied={copied === "ID"}
            />

            {/* Account status badges */}
            <div className="bg-[#242f3d] rounded-xl p-4 flex flex-wrap gap-2">
              {profile.premium && (
                <span className="flex items-center gap-1 bg-amber-500/20 text-amber-400 text-xs font-medium px-3 py-1.5 rounded-full border border-amber-500/30">
                  <Sparkles className="h-3.5 w-3.5" /> Telegram Premium
                </span>
              )}
              {profile.verified && (
                <span className="flex items-center gap-1 bg-sky-500/20 text-sky-400 text-xs font-medium px-3 py-1.5 rounded-full border border-sky-500/30">
                  <BadgeCheck className="h-3.5 w-3.5" /> Verified
                </span>
              )}
              <span className="flex items-center gap-1 bg-green-500/20 text-green-400 text-xs font-medium px-3 py-1.5 rounded-full border border-green-500/30">
                ● Connected
              </span>
            </div>
          </div>
        </>
      )}

      {/* No account selected */}
      {!activeAccount && !isLoading && (
        <div className="flex-1 flex items-center justify-center px-6 text-center">
          <p className="text-gray-400 text-sm">Select an account from the sidebar to view its profile</p>
        </div>
      )}
    </div>
  )
}

function InfoRow({
  icon,
  label,
  value,
  onCopy,
  copied,
  multiline,
}: {
  icon: React.ReactNode
  label: string
  value: string
  onCopy?: () => void
  copied?: boolean
  multiline?: boolean
}) {
  return (
    <div className="bg-[#242f3d] rounded-xl px-4 py-3.5 flex items-start gap-3">
      <div className="mt-0.5 flex-shrink-0">{icon}</div>
      <div className="flex-1 min-w-0">
        <p className={cn("text-white text-[15px]", multiline ? "whitespace-pre-wrap" : "truncate")}>
          {value}
        </p>
        <p className="text-gray-500 text-xs mt-0.5">{label}</p>
      </div>
      {onCopy && (
        <button
          onClick={onCopy}
          className="p-1 text-gray-500 hover:text-[#2AABEE] transition-colors flex-shrink-0"
        >
          {copied ? <CheckCheck className="h-4 w-4 text-green-400" /> : <Copy className="h-4 w-4" />}
        </button>
      )}
    </div>
  )
}
