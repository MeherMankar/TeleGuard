
import { useState, useRef, useEffect } from "react"
import {
  ArrowLeft,
  X,
  QrCode,
  Camera,
  User,
  Phone,
  AtSign,
  Megaphone,
  Palette,
  Gift,
  Plus,
  Check,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useUser } from "@/contexts/user-context"
import { formatBirthday } from "@/lib/date-utils"

interface EditProfilePageProps {
  isOpen: boolean
  onClose: () => void
  onBack: () => void
}

const MAX_BIO = 70

export function EditProfilePage({ isOpen, onClose, onBack }: EditProfilePageProps) {
  const { profile, updateProfile, setAvatarUrl } = useUser()
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Local form state
  const [name, setName] = useState(profile.name)
  const [username, setUsername] = useState(profile.username)
  const [bio, setBio] = useState(profile.bio)
  const [birthday, setBirthday] = useState(profile.birthday)
  const [nameColor, setNameColor] = useState(profile.nameColor)

  // Editing state
  const [editingField, setEditingField] = useState<string | null>(null)

  // Sync local state when profile changes or panel opens
  useEffect(() => {
    if (isOpen) {
      setName(profile.name)
      setUsername(profile.username)
      setBio(profile.bio)
      setBirthday(profile.birthday)
      setNameColor(profile.nameColor)
      setEditingField(null)
    }
  }, [isOpen, profile])

  const handleSaveField = (field: string) => {
    switch (field) {
      case "name":
        updateProfile({ name })
        break
      case "username":
        updateProfile({ username })
        break
      case "bio":
        updateProfile({ bio })
        break
      case "birthday":
        updateProfile({ birthday })
        break
      case "nameColor":
        updateProfile({ nameColor })
        break
    }
    setEditingField(null)
  }

  const handleAvatarChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      const url = URL.createObjectURL(file)
      setAvatarUrl(url)
    }
  }

  const colorOptions = ["#ff6b9d", "#a855f7", "#3b82f6", "#22c55e", "#f97316", "#ef4444"]

  return (
    <div
      style={{ zIndex: 80 }}
      className={cn(
        "fixed inset-0 bg-background flex flex-col transition-transform duration-300 ease-in-out overflow-y-auto",
        isOpen ? "translate-x-0" : "translate-x-full"
      )}
    >
      {/* Hidden file input for avatar */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        onChange={handleAvatarChange}
        className="hidden"
      />

      {/* Header */}
      <div className="flex items-center justify-between px-2 pt-5 pb-3 bg-background sticky top-0 z-10 border-b border-border/30">
        <button
          onClick={onBack}
          aria-label="Go back"
          className="p-2 text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <h1 className="text-base font-semibold text-foreground">Info</h1>
        <div className="flex items-center gap-1">
          <button aria-label="QR code" className="p-2 text-muted-foreground hover:text-foreground transition-colors">
            <QrCode className="h-5 w-5" />
          </button>
          <button onClick={onClose} aria-label="Close" className="p-2 text-muted-foreground hover:text-foreground transition-colors">
            <X className="h-5 w-5" />
          </button>
        </div>
      </div>

      {/* Avatar + Name + Status */}
      <div className="flex flex-col items-center pt-8 pb-6 bg-card">
        <div className="relative mb-4">
          <div className="w-28 h-28 rounded-full bg-gradient-to-br from-green-400 to-green-700 flex items-center justify-center text-4xl font-bold text-white overflow-hidden border-4 border-card">
            {profile.avatarUrl ? (
              <img src={profile.avatarUrl} alt="Avatar" className="w-full h-full object-cover" />
            ) : (
              <span>{profile.name.charAt(0)}</span>
            )}
          </div>
          {/* Camera button overlay */}
          <button
            onClick={() => fileInputRef.current?.click()}
            aria-label="Change photo"
            className="absolute bottom-1 right-1 w-9 h-9 rounded-full bg-primary flex items-center justify-center shadow-lg hover:bg-primary/90 transition-colors"
          >
            <Camera className="h-4 w-4 text-primary-foreground" />
          </button>
        </div>
        <h2 className="text-xl font-semibold text-foreground">{profile.name}</h2>
        <p className="text-sm text-primary mt-1">online</p>
      </div>

      {/* Bio section */}
      <div className="mt-2 bg-card border-y border-border/30 px-4 py-3">
        <div className="flex items-start justify-between gap-3">
          <textarea
            value={bio}
            onChange={(e) => {
              if (e.target.value.length <= MAX_BIO) setBio(e.target.value)
            }}
            onBlur={() => handleSaveField("bio")}
            rows={3}
            className="flex-1 bg-transparent text-[15px] text-foreground resize-none outline-none leading-relaxed focus:ring-1 focus:ring-primary/50 rounded px-1"
            aria-label="Bio"
            placeholder="Enter your bio..."
          />
          <span className="text-sm text-muted-foreground mt-0.5 flex-shrink-0">
            {MAX_BIO - bio.length}
          </span>
        </div>
        <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
          Any details such as age, occupation or city.{"\n"}
          Example: 23 y.o. designer from San Francisco
        </p>
      </div>

      {/* Info rows group 1 */}
      <div className="mt-2 bg-card border-y border-border/30">
        {/* Name - Editable */}
        <div className="flex items-center gap-4 px-4 py-4 border-b border-border/20">
          <User className="h-5 w-5 text-muted-foreground flex-shrink-0" />
          <span className="flex-1 text-[15px] text-foreground">Name</span>
          {editingField === "name" ? (
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSaveField("name")}
                className="bg-input text-foreground text-[15px] px-2 py-1 rounded outline-none focus:ring-1 focus:ring-primary w-32"
                autoFocus
              />
              <button onClick={() => handleSaveField("name")} className="text-primary">
                <Check className="h-5 w-5" />
              </button>
            </div>
          ) : (
            <button onClick={() => setEditingField("name")} className="text-[15px] text-primary hover:underline">
              {profile.name}
            </button>
          )}
        </div>

        {/* Phone number - Display only */}
        <div className="flex items-center gap-4 px-4 py-4 border-b border-border/20">
          <Phone className="h-5 w-5 text-muted-foreground flex-shrink-0" />
          <span className="flex-1 text-[15px] text-foreground">Phone number</span>
          <span className="text-[15px] text-primary">{profile.phone}</span>
        </div>

        {/* Username - Editable */}
        <div className="flex items-center gap-4 px-4 py-4">
          <AtSign className="h-5 w-5 text-muted-foreground flex-shrink-0" />
          <span className="flex-1 text-[15px] text-foreground">Username</span>
          {editingField === "username" ? (
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSaveField("username")}
                className="bg-input text-foreground text-[15px] px-2 py-1 rounded outline-none focus:ring-1 focus:ring-primary w-32"
                autoFocus
              />
              <button onClick={() => handleSaveField("username")} className="text-primary">
                <Check className="h-5 w-5" />
              </button>
            </div>
          ) : (
            <button onClick={() => setEditingField("username")} className="text-[15px] text-primary hover:underline">
              {profile.username}
            </button>
          )}
        </div>
      </div>

      {/* Username hint */}
      <p className="px-4 pt-3 pb-1 text-sm text-muted-foreground leading-relaxed">
        Username lets people contact you on Telegram without needing your phone number.
      </p>

      {/* Info rows group 2 */}
      <div className="mt-2 bg-card border-y border-border/30">
        {/* Personal channel */}
        <div className="flex items-center gap-4 px-4 py-4 border-b border-border/20">
          <Megaphone className="h-5 w-5 text-muted-foreground flex-shrink-0" />
          <span className="flex-1 text-[15px] text-foreground">Personal channel</span>
          <span className="text-[15px] text-primary truncate max-w-[140px] text-right">
            {profile.personalChannel}
          </span>
        </div>

        {/* Your name color - Editable */}
        <div className="flex flex-col gap-3 px-4 py-4">
          <div className="flex items-center gap-4">
            <Palette className="h-5 w-5 text-muted-foreground flex-shrink-0" />
            <span className="flex-1 text-[15px] text-foreground">Your name color</span>
            <span className="text-[10px] font-bold bg-primary text-primary-foreground px-1.5 py-0.5 rounded-sm">
              NEW
            </span>
            <span
              className="text-sm font-semibold px-2 py-0.5 rounded ml-2"
              style={{ color: nameColor }}
            >
              {profile.name.split(" ")[0]}
            </span>
          </div>
          {/* Color picker */}
          <div className="flex items-center gap-2 ml-9">
            {colorOptions.map((color) => (
              <button
                key={color}
                onClick={() => {
                  setNameColor(color)
                  updateProfile({ nameColor: color })
                }}
                className={cn(
                  "w-7 h-7 rounded-full transition-transform hover:scale-110",
                  nameColor === color && "ring-2 ring-offset-2 ring-offset-background ring-primary"
                )}
                style={{ backgroundColor: color }}
                aria-label={`Select color ${color}`}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Birthday section - Editable */}
      <div className="mt-2 bg-card border-y border-border/30">
        <div className="flex items-center gap-4 px-4 py-4">
          <Gift className="h-5 w-5 text-muted-foreground flex-shrink-0" />
          <span className="flex-1 text-[15px] text-foreground">Birthday</span>
          {editingField === "birthday" ? (
            <div className="flex items-center gap-2">
              <input
                type="date"
                value={birthday}
                onChange={(e) => setBirthday(e.target.value)}
                className="bg-input text-foreground text-[15px] px-2 py-1 rounded outline-none focus:ring-1 focus:ring-primary"
                autoFocus
              />
              <button onClick={() => handleSaveField("birthday")} className="text-primary">
                <Check className="h-5 w-5" />
              </button>
            </div>
          ) : (
            <button onClick={() => setEditingField("birthday")} className="text-[15px] text-primary hover:underline">
              {formatBirthday(profile.birthday)}
            </button>
          )}
        </div>
      </div>

      {/* Birthday hint */}
      <p className="px-4 pt-3 pb-1 text-sm text-muted-foreground leading-relaxed">
        Choose who can see your birthday in{" "}
        <span className="text-primary cursor-pointer hover:underline">Settings</span>.
      </p>

      {/* Add Account */}
      <div className="mt-2 bg-card border-y border-border/30">
        <button className="w-full flex items-center gap-4 px-4 py-4 hover:bg-secondary/50 transition-colors">
          <div className="w-5 h-5 rounded-full border-2 border-muted-foreground flex items-center justify-center flex-shrink-0">
            <Plus className="h-3 w-3 text-muted-foreground" />
          </div>
          <span className="text-[15px] text-foreground">Add Account</span>
        </button>
      </div>

      {/* Bottom safe area */}
      <div className="h-8" />
    </div>
  )
}

