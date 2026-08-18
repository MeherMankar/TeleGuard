import { useState, useEffect } from "react"
import {
  ArrowLeft,
  X,
  Camera,
  User,
  Phone,
  AtSign,
  Check,
  Loader2,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { accountsApi, chatsApi, apiErrorMessage } from "@/lib/api"
import { useUser } from "@/contexts/user-context"
import { toast } from "sonner"

interface EditProfilePageProps {
  isOpen: boolean
  onClose: () => void
  onBack: () => void
}

const MAX_BIO = 70

export function EditProfilePage({ isOpen, onClose, onBack }: EditProfilePageProps) {
  const { activeAccount } = useUser()
  const queryClient = useQueryClient()

  // Fetch real profile from Telegram
  const { data: profile, isLoading } = useQuery({
    queryKey: ["profile", activeAccount?.name],
    queryFn: () => accountsApi.profile(activeAccount!.name),
    enabled: isOpen && !!activeAccount,
    staleTime: 30_000,
  })

  // Editable local state — synced when profile loads or page opens
  const [firstName, setFirstName] = useState("")
  const [lastName, setLastName]   = useState("")
  const [username, setUsername]   = useState("")
  const [bio, setBio]             = useState("")

  const [editingField, setEditingField] = useState<string | null>(null)
  const [saving, setSaving] = useState<string | null>(null)

  useEffect(() => {
    if (profile) {
      setFirstName(profile.first_name ?? "")
      setLastName(profile.last_name ?? "")
      setUsername(profile.username ?? "")
      setBio(profile.bio ?? "")
    }
  }, [profile])

  useEffect(() => {
    if (!isOpen) setEditingField(null)
  }, [isOpen])

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["profile", activeAccount?.name] })

  const saveField = async (field: string) => {
    if (!activeAccount) return
    setSaving(field)
    try {
      if (field === "name") {
        const parts = [firstName.trim(), lastName.trim()]
        await accountsApi.updateProfile(activeAccount.name, {
          first_name: parts[0],
          last_name:  parts[1],
        })
      } else if (field === "bio") {
        await accountsApi.updateProfile(activeAccount.name, { bio: bio.trim() })
      } else if (field === "username") {
        await accountsApi.updateProfile(activeAccount.name, { username: username.trim().replace(/^@/, "") })
      }
      toast.success("Saved")
      setEditingField(null)
      invalidate()
    } catch (e) {
      toast.error(apiErrorMessage(e))
    } finally {
      setSaving(null)
    }
  }

  const displayName = profile
    ? [profile.first_name, profile.last_name].filter(Boolean).join(" ") || profile.username || "—"
    : activeAccount?.name ?? "—"

  const photoUrl = profile?.has_photo && activeAccount
    ? chatsApi.photoUrl(activeAccount.name, profile.id)
    : null

  return (
    <div
      style={{ zIndex: 80 }}
      className={cn(
        "fixed inset-0 bg-background flex flex-col transition-transform duration-300 ease-in-out overflow-y-auto",
        isOpen ? "translate-x-0" : "translate-x-full",
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-2 pt-5 pb-3 bg-background sticky top-0 z-10 border-b border-border/30">
        <button
          onClick={onBack}
          aria-label="Go back"
          className="p-2 text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <h1 className="text-base font-semibold text-foreground">Edit Profile</h1>
        <button onClick={onClose} aria-label="Close" className="p-2 text-muted-foreground hover:text-foreground transition-colors">
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 text-primary animate-spin" />
        </div>
      )}

      {!isLoading && (
        <>
          {/* Avatar + name */}
          <div className="flex flex-col items-center pt-8 pb-6 bg-card">
            <div className="relative mb-4">
              <div className="w-28 h-28 rounded-full bg-gradient-to-br from-sky-400 to-blue-600 flex items-center justify-center text-4xl font-bold text-white overflow-hidden border-4 border-card">
                {photoUrl ? (
                  <img src={photoUrl} alt={displayName} className="w-full h-full object-cover" />
                ) : (
                  <span>{displayName.charAt(0).toUpperCase()}</span>
                )}
              </div>
              {/* Camera — photo change is done via bot (/start → Account Settings → Change Photo) */}
              <div className="absolute bottom-1 right-1 w-9 h-9 rounded-full bg-primary/80 flex items-center justify-center cursor-not-allowed opacity-60"
                   title="Change photo via the bot: Account Settings → Change Photo">
                <Camera className="h-4 w-4 text-primary-foreground" />
              </div>
            </div>
            <h2 className="text-xl font-semibold text-foreground">{displayName}</h2>
            {profile?.username && (
              <p className="text-sm text-primary mt-1">@{profile.username}</p>
            )}
          </div>

          {/* Bio */}
          <div className="mt-2 bg-card border-y border-border/30 px-4 py-3">
            <div className="flex items-start justify-between gap-3">
              <textarea
                value={bio}
                onChange={(e) => {
                  if (e.target.value.length <= MAX_BIO) setBio(e.target.value)
                }}
                onFocus={() => setEditingField("bio")}
                onBlur={() => {
                  if (editingField === "bio" && bio !== (profile?.bio ?? "")) {
                    saveField("bio")
                  } else {
                    setEditingField(null)
                  }
                }}
                rows={3}
                className="flex-1 bg-transparent text-[15px] text-foreground resize-none outline-none leading-relaxed focus:ring-1 focus:ring-primary/50 rounded px-1"
                placeholder="Enter your bio…"
              />
              <span className="text-sm text-muted-foreground mt-0.5 flex-shrink-0">
                {MAX_BIO - bio.length}
              </span>
            </div>
            {saving === "bio" && (
              <p className="text-xs text-primary flex items-center gap-1 mt-1">
                <Loader2 className="h-3 w-3 animate-spin" /> Saving…
              </p>
            )}
            <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
              Any details such as age, occupation or city.
            </p>
          </div>

          {/* Info rows */}
          <div className="mt-2 bg-card border-y border-border/30">
            {/* Name */}
            <div className="flex items-center gap-4 px-4 py-4 border-b border-border/20">
              <User className="h-5 w-5 text-muted-foreground flex-shrink-0" />
              <span className="flex-1 text-[15px] text-foreground">Name</span>
              {editingField === "name" ? (
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    placeholder="First"
                    onKeyDown={(e) => e.key === "Enter" && saveField("name")}
                    className="bg-input text-foreground text-[15px] px-2 py-1 rounded outline-none focus:ring-1 focus:ring-primary w-24"
                    autoFocus
                  />
                  <input
                    type="text"
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    placeholder="Last"
                    onKeyDown={(e) => e.key === "Enter" && saveField("name")}
                    className="bg-input text-foreground text-[15px] px-2 py-1 rounded outline-none focus:ring-1 focus:ring-primary w-24"
                  />
                  <button
                    onClick={() => saveField("name")}
                    disabled={saving === "name"}
                    className="text-primary"
                  >
                    {saving === "name"
                      ? <Loader2 className="h-4 w-4 animate-spin" />
                      : <Check className="h-5 w-5" />}
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setEditingField("name")}
                  className="text-[15px] text-primary hover:underline"
                >
                  {displayName}
                </button>
              )}
            </div>

            {/* Phone — display only */}
            <div className="flex items-center gap-4 px-4 py-4 border-b border-border/20">
              <Phone className="h-5 w-5 text-muted-foreground flex-shrink-0" />
              <span className="flex-1 text-[15px] text-foreground">Phone number</span>
              <span className="text-[15px] text-primary">{profile?.phone || activeAccount?.phone || "—"}</span>
            </div>

            {/* Username */}
            <div className="flex items-center gap-4 px-4 py-4">
              <AtSign className="h-5 w-5 text-muted-foreground flex-shrink-0" />
              <span className="flex-1 text-[15px] text-foreground">Username</span>
              {editingField === "username" ? (
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground text-[15px]">@</span>
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value.replace(/[^a-zA-Z0-9_]/g, ""))}
                    onKeyDown={(e) => e.key === "Enter" && saveField("username")}
                    className="bg-input text-foreground text-[15px] px-2 py-1 rounded outline-none focus:ring-1 focus:ring-primary w-32"
                    autoFocus
                  />
                  <button
                    onClick={() => saveField("username")}
                    disabled={saving === "username"}
                    className="text-primary"
                  >
                    {saving === "username"
                      ? <Loader2 className="h-4 w-4 animate-spin" />
                      : <Check className="h-5 w-5" />}
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setEditingField("username")}
                  className="text-[15px] text-primary hover:underline"
                >
                  {profile?.username ? `@${profile.username}` : "set username"}
                </button>
              )}
            </div>
          </div>

          <p className="px-4 pt-3 pb-6 text-sm text-muted-foreground leading-relaxed">
            Username lets people contact you on Telegram without needing your phone number.
          </p>
        </>
      )}
    </div>
  )
}
