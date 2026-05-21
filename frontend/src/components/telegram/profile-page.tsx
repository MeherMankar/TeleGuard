
import { useState } from "react"
import {
  X,
  Pencil,
  Star,
  Phone,
  User,
  AtSign,
  Cake,
  Server,
  PlayCircle,
  RotateCcw,
  Forward,
  Users,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { EditProfilePage } from "@/components/telegram/edit-profile-page"
import { useUser, formatBirthday, calculateAge } from "@/contexts/user-context"

interface ProfilePageProps {
  isOpen: boolean
  onClose: () => void
}


const mediaItems = [
  { id: "1", type: "video", duration: "00:11", color: "bg-amber-800" },
  { id: "2", type: "video", duration: "00:24", color: "bg-stone-700" },
  { id: "3", type: "video", duration: "00:08", color: "bg-teal-800" },
]

export function ProfilePage({ isOpen, onClose }: ProfilePageProps) {
  const [isEditOpen, setIsEditOpen] = useState(false)
  const { profile } = useUser()

  return (
    <>
      {/* Edit Profile — slides over the top */}
      <EditProfilePage
        isOpen={isEditOpen}
        onClose={onClose}
        onBack={() => setIsEditOpen(false)}
      />

      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{ zIndex: 60 }}
        className={cn(
          "fixed inset-0 bg-black/70 transition-opacity duration-300",
          isOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        )}
        aria-hidden="true"
      />

      {/* Slide-in panel from right */}
      <div
        style={{ zIndex: 70 }}
        className={cn(
          "fixed top-0 right-0 h-screen w-full max-w-md bg-background flex flex-col transition-transform duration-300 ease-in-out overflow-y-auto",
          isOpen ? "translate-x-0" : "translate-x-full"
        )}
      >
        {/* Top action buttons */}
        <div className="flex items-center justify-end gap-4 px-4 pt-5 pb-3 absolute top-0 right-0 z-10">
          <button
            onClick={() => setIsEditOpen(true)}
            aria-label="Edit profile"
            className="p-2 text-muted-foreground hover:text-foreground transition-colors"
          >
            <Pencil className="h-5 w-5" />
          </button>
          <button
            onClick={onClose}
            aria-label="Close profile"
            className="p-2 text-muted-foreground hover:text-foreground transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Avatar section */}
        <div className="flex flex-col items-center pt-14 pb-6 bg-card">
          <div className="w-28 h-28 rounded-full bg-gradient-to-br from-green-400 to-green-700 flex items-center justify-center text-4xl font-bold text-white overflow-hidden mb-4 border-4 border-card">
            {profile.avatarUrl ? (
              <img src={profile.avatarUrl} alt="Avatar" className="w-full h-full object-cover" />
            ) : (
              <span>{profile.name.charAt(0)}</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold text-foreground">{profile.name}</h1>
            <Star className="h-5 w-5 fill-sky-400 text-sky-400" />
          </div>
          <p className="text-sm text-muted-foreground mt-1">last seen today at 09:45 AM</p>
        </div>

        {/* Channel card */}
        <div className="mx-0 mt-2 bg-card border-y border-border/40">
          <div className="flex items-start gap-3 px-4 py-3">
            {/* Channel avatar */}
            <div className="w-12 h-12 rounded-full bg-gradient-to-br from-fuchsia-500 to-indigo-600 flex items-center justify-center flex-shrink-0">
              <span className="text-white text-xs font-bold">LL</span>
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between gap-2">
                <p className="text-[15px] font-medium text-foreground leading-tight">
                  Lossless music collection [Waiting ...
                </p>
                <span className="text-xs text-muted-foreground whitespace-nowrap flex-shrink-0 pt-0.5">
                  11-01-2026
                </span>
              </div>
              <div className="flex items-center gap-1 mt-0.5">
                <Forward className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">Dm @meher_mankar</span>
              </div>
              <div className="flex items-center gap-1.5 mt-1">
                <Users className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">Channel · 194 subscribers</span>
              </div>
            </div>
          </div>
        </div>

        {/* Info rows */}
        <div className="mt-2 bg-card border-y border-border/40">
          {/* Phone */}
          <div className="flex items-center gap-4 px-4 py-3.5 border-b border-border/30">
            <Phone className="h-5 w-5 text-muted-foreground flex-shrink-0" />
            <div className="flex-1">
              <p className="text-[15px] text-foreground">{profile.phone}</p>
              <p className="text-xs text-muted-foreground mt-0.5">Mobile</p>
            </div>
          </div>

          {/* Bio */}
          <div className="flex items-start gap-4 px-4 py-3.5 border-b border-border/30">
            <User className="h-5 w-5 text-muted-foreground flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-[15px] text-foreground leading-relaxed">
                {profile.bio}
              </p>
              <p className="text-xs text-muted-foreground mt-0.5">Bio</p>
            </div>
          </div>

          {/* Username */}
          <div className="flex items-center gap-4 px-4 py-3.5 border-b border-border/30">
            <AtSign className="h-5 w-5 text-muted-foreground flex-shrink-0" />
            <div className="flex-1">
              <p className="text-[15px] text-foreground">{profile.username}</p>
              <p className="text-xs text-muted-foreground mt-0.5">Username</p>
            </div>
            {/* QR grid icon */}
            <div className="grid grid-cols-2 gap-0.5 w-6 h-6 flex-shrink-0">
              <div className="bg-muted-foreground rounded-sm" />
              <div className="bg-muted-foreground rounded-sm" />
              <div className="bg-muted-foreground rounded-sm" />
              <div className="bg-muted-foreground rounded-sm" />
            </div>
          </div>

          {/* Birthday */}
          <div className="flex items-center gap-4 px-4 py-3.5 border-b border-border/30">
            <Cake className="h-5 w-5 text-muted-foreground flex-shrink-0" />
            <div className="flex-1">
              <p className="text-[15px] text-foreground">
                {formatBirthday(profile.birthday)}{" "}
                <span className="text-primary">({calculateAge(profile.birthday)} years old)</span>
              </p>
              <p className="text-xs text-muted-foreground mt-0.5">Birthday</p>
            </div>
          </div>

          {/* DC / Telegram ID */}
          <div className="flex items-center gap-4 px-4 py-3.5">
            <Server className="h-5 w-5 text-muted-foreground flex-shrink-0" />
            <div className="flex-1">
              <p className="text-[15px] text-foreground">6121637257</p>
              <p className="text-xs text-muted-foreground mt-0.5">DC5, Singapore, SG</p>
            </div>
            {/* Calendar-like icon */}
            <div className="w-8 h-8 rounded border border-border flex flex-col overflow-hidden flex-shrink-0">
              <div className="bg-primary h-2" />
              <div className="flex-1 flex items-center justify-center">
                <span className="text-[10px] text-muted-foreground font-bold">DC</span>
              </div>
            </div>
          </div>
        </div>

        {/* Story Archive */}
        <div className="mt-2 bg-card border-y border-border/40">
          <div className="flex items-center gap-4 px-4 py-3.5">
            <RotateCcw className="h-5 w-5 text-muted-foreground flex-shrink-0" />
            <span className="flex-1 text-[15px] text-foreground">Story Archive</span>
            <span className="text-[15px] text-primary font-medium">1</span>
          </div>
        </div>

        {/* Media thumbnails */}
        <div className="mt-2 grid grid-cols-3 gap-0.5 flex-1">
          {mediaItems.map((item) => (
            <div
              key={item.id}
              className={cn(
                "relative aspect-square",
                item.color
              )}
            >
              {item.type === "video" && (
                <>
                  <PlayCircle className="absolute inset-0 m-auto h-8 w-8 text-white/80" />
                  <span className="absolute bottom-1.5 left-1.5 text-[11px] text-white font-medium bg-black/40 px-1 rounded">
                    {item.duration}
                  </span>
                </>
              )}
            </div>
          ))}
          {/* Empty fill cells */}
          <div className="aspect-square bg-card" />
          <div className="aspect-square bg-card" />
          <div className="aspect-square bg-card" />
        </div>
      </div>
    </>
  )
}
