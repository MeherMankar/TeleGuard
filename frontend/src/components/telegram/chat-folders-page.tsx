import { useState } from "react"
import {
  ArrowLeft, Plus, Trash2, Pencil, Loader2,
  Folder, Users, Radio, Bot, Check, User, UserX,
  VolumeX, MailOpen, Archive, MessageSquare,
  Star, Briefcase, Home, Gamepad2, BookOpen, Music, Bell,
  Crown, FolderPlus, ToggleLeft, ToggleRight,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { chatsApi, type ChatFolder } from "@/lib/api"
import { useUser } from "@/contexts/user-context"
import { toast } from "sonner"

// Icon options for folder customization
const FOLDER_ICONS = [
  { id: "folder",    Icon: Folder,        label: "Folder",   color: "text-sky-400"    },
  { id: "star",      Icon: Star,          label: "Starred",  color: "text-amber-400"  },
  { id: "users",     Icon: Users,         label: "Groups",   color: "text-green-400"  },
  { id: "radio",     Icon: Radio,         label: "Channels", color: "text-blue-400"   },
  { id: "bot",       Icon: Bot,           label: "Bots",     color: "text-red-400"    },
  { id: "chat",      Icon: MessageSquare, label: "Chats",    color: "text-purple-400" },
  { id: "bell",      Icon: Bell,          label: "Unread",   color: "text-orange-400" },
  { id: "crown",     Icon: Crown,         label: "Admin",    color: "text-yellow-400" },
  { id: "briefcase", Icon: Briefcase,     label: "Work",     color: "text-slate-400"  },
  { id: "home",      Icon: Home,          label: "Personal", color: "text-cyan-400"   },
  { id: "music",     Icon: Music,         label: "Music",    color: "text-pink-400"   },
  { id: "book",      Icon: BookOpen,      label: "Reading",  color: "text-lime-400"   },
  { id: "game",      Icon: Gamepad2,      label: "Gaming",   color: "text-indigo-400" },
  { id: "user",      Icon: User,          label: "Contacts", color: "text-teal-400"   },
]

function getIconDef(id: string | null | undefined) {
  return FOLDER_ICONS.find((i) => i.id === id) ?? FOLDER_ICONS[0]
}

// Preset definitions — each creates one separate folder
const PRESETS = [
  { id: 2, title: "Personal",  iconId: "user",      desc: "Direct messages with contacts",      contacts: true,  groups: false, broadcasts: false, bots: false },
  { id: 3, title: "Groups",    iconId: "users",     desc: "All group chats",                     contacts: false, groups: true,  broadcasts: false, bots: false },
  { id: 4, title: "Channels",  iconId: "radio",     desc: "All channels",                        contacts: false, groups: false, broadcasts: true,  bots: false },
  { id: 5, title: "Bots",      iconId: "bot",       desc: "All bot conversations",               contacts: false, groups: false, broadcasts: false, bots: true  },
  { id: 6, title: "Unread",    iconId: "bell",      desc: "All unread chats (excl. archived)",   contacts: true,  groups: true,  broadcasts: true,  bots: true, exclude_read: true, exclude_archived: true },
  { id: 7, title: "Admin",     iconId: "crown",     desc: "Chats where you are admin or owner",  contacts: false, groups: false, broadcasts: false, bots: false, isAdmin: true },
]

interface ChatFoldersPageProps {
  isOpen: boolean
  onClose: () => void
}

const EMPTY_FOLDER: Partial<ChatFolder> & { iconId?: string } = {
  title: "", emoji: null,
  contacts: false, non_contacts: false, groups: false,
  broadcasts: false, bots: false,
  exclude_muted: false, exclude_read: false, exclude_archived: false,
}

export function ChatFoldersPage({ isOpen, onClose }: ChatFoldersPageProps) {
  const { activeAccount } = useUser()
  const qc = useQueryClient()
  const [editingFolder, setEditingFolder] = useState<(Partial<ChatFolder> & { iconId?: string }) | null>(null)
  const [showIconPicker, setShowIconPicker] = useState(false)
  const [creatingPreset, setCreatingPreset] = useState<number | null>(null)

  const { data: folders = [], isLoading } = useQuery({
    queryKey: ["folders", activeAccount?.name],
    queryFn: () => chatsApi.folders(activeAccount!.name),
    enabled: isOpen && !!activeAccount,
    staleTime: 0,
  })

  const existingIds = new Set(folders.filter(f => !f.is_default).map(f => f.id))

  const createMutation = useMutation({
    mutationFn: (folder: Partial<ChatFolder>) =>
      chatsApi.createFolder(activeAccount!.name, folder),
    onSuccess: (res) => {
      toast.success(`"${res.title}" created`)
      setEditingFolder(null)
      setCreatingPreset(null)
      qc.invalidateQueries({ queryKey: ["folders", activeAccount?.name] })
    },
    onError: (e) => {
      toast.error((e as Error).message)
      setCreatingPreset(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => chatsApi.deleteFolder(activeAccount!.name, id),
    onSuccess: () => {
      toast.success("Folder removed")
      qc.invalidateQueries({ queryKey: ["folders", activeAccount?.name] })
    },
    onError: (e) => toast.error((e as Error).message),
  })

  const handleSave = () => {
    if (!editingFolder?.title?.trim()) { toast.error("Name required"); return }
    createMutation.mutate({ ...editingFolder, emoji: editingFolder.iconId ?? null })
  }

  const toggleFlag = (key: keyof ChatFolder) =>
    setEditingFolder((p) => p ? { ...p, [key]: !p[key as keyof typeof p] } : p)

  const addPreset = (preset: typeof PRESETS[0]) => {
    setCreatingPreset(preset.id)
    createMutation.mutate({
      id: preset.id,
      title: preset.title,
      emoji: preset.iconId,
      contacts: (preset as any).contacts ?? false,
      non_contacts: false,
      groups: (preset as any).groups ?? false,
      broadcasts: (preset as any).broadcasts ?? false,
      bots: (preset as any).bots ?? false,
      exclude_muted: false,
      exclude_read: (preset as any).exclude_read ?? false,
      exclude_archived: (preset as any).exclude_archived ?? false,
    })
  }

  const selectedIconDef = getIconDef(editingFolder?.iconId)
  const SelectedIcon = selectedIconDef.Icon

  // ── Editor ────────────────────────────────────────────────────────────────
  if (editingFolder !== null) {
    return (
      <div style={{ zIndex: 80 }} className={cn(
        "fixed inset-0 bg-[#17212b] flex flex-col transition-transform duration-300 ease-in-out",
        isOpen ? "translate-x-0" : "translate-x-full",
      )}>
        <header className="flex items-center gap-4 px-4 py-3 border-b border-white/10">
          <button onClick={() => setEditingFolder(null)} className="p-2 -ml-2 text-gray-400 hover:text-white">
            <ArrowLeft className="h-6 w-6" />
          </button>
          <h1 className="text-xl font-medium text-white flex-1">
            {editingFolder.id ? "Edit Folder" : "New Folder"}
          </h1>
          <button onClick={handleSave} disabled={createMutation.isPending}
            className="px-4 py-1.5 bg-[#2AABEE] text-white rounded-lg text-sm font-medium flex items-center gap-1.5 disabled:opacity-50">
            {createMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
            Save
          </button>
        </header>
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Name + icon */}
          <div className="bg-[#242f3d] rounded-xl p-4">
            <p className="text-sky-400 text-xs font-medium uppercase tracking-wider mb-3">Folder Name</p>
            <div className="flex items-center gap-3">
              <div className="relative">
                <button onClick={() => setShowIconPicker(!showIconPicker)}
                  className={cn("w-12 h-12 rounded-xl bg-[#17212b] flex items-center justify-center border transition-colors",
                    showIconPicker ? "border-[#2AABEE]" : "border-white/10 hover:border-[#2AABEE]/50")}>
                  <SelectedIcon className={cn("h-5 w-5", selectedIconDef.color)} />
                </button>
                {showIconPicker && (
                  <div className="absolute top-14 left-0 bg-[#1c2b3a] border border-white/10 rounded-xl p-3 grid grid-cols-7 gap-2 z-10 shadow-xl w-64">
                    {FOLDER_ICONS.map(({ id, Icon, label, color }) => (
                      <button key={id} title={label}
                        onClick={() => { setEditingFolder(p => p ? { ...p, iconId: id } : p); setShowIconPicker(false) }}
                        className={cn("w-8 h-8 rounded-lg flex items-center justify-center hover:bg-white/10 transition-colors",
                          editingFolder?.iconId === id && "bg-white/20")}>
                        <Icon className={cn("h-4 w-4", color)} />
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <input value={editingFolder.title || ""} autoFocus maxLength={12}
                onChange={e => setEditingFolder(p => p ? { ...p, title: e.target.value } : p)}
                placeholder="Folder name"
                className="flex-1 bg-[#17212b] text-white rounded-xl px-4 py-3 border border-white/10 focus:border-[#2AABEE] focus:outline-none text-[15px]" />
            </div>
          </div>
          {/* Include types */}
          <div className="bg-[#242f3d] rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-white/10">
              <p className="text-sky-400 text-xs font-medium uppercase tracking-wider">Include</p>
            </div>
            {([
              { key: "contacts"     as const, label: "Contacts",     Icon: User,    color: "text-blue-400"   },
              { key: "non_contacts" as const, label: "Non-Contacts", Icon: UserX,   color: "text-purple-400" },
              { key: "groups"       as const, label: "Groups",       Icon: Users,   color: "text-green-400"  },
              { key: "broadcasts"   as const, label: "Channels",     Icon: Radio,   color: "text-amber-400"  },
              { key: "bots"         as const, label: "Bots",         Icon: Bot,     color: "text-red-400"    },
            ]).map(({ key, label, Icon: I, color }, i, arr) => (
              <button key={key} onClick={() => toggleFlag(key)}
                className={cn("w-full flex items-center gap-4 px-4 py-3.5 hover:bg-white/5 transition-colors", i < arr.length - 1 && "border-b border-white/5")}>
                <I className={cn("h-5 w-5 flex-shrink-0", color)} />
                <span className="flex-1 text-white text-[15px] text-left">{label}</span>
                {editingFolder[key] ? <ToggleRight className="h-6 w-6 text-[#2AABEE]" /> : <ToggleLeft className="h-6 w-6 text-gray-600" />}
              </button>
            ))}
          </div>
          {/* Exclude */}
          <div className="bg-[#242f3d] rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-white/10">
              <p className="text-sky-400 text-xs font-medium uppercase tracking-wider">Exclude</p>
            </div>
            {([
              { key: "exclude_muted"    as const, label: "Muted",    Icon: VolumeX  },
              { key: "exclude_read"     as const, label: "Read",     Icon: MailOpen },
              { key: "exclude_archived" as const, label: "Archived", Icon: Archive  },
            ]).map(({ key, label, Icon: I }, i, arr) => (
              <button key={key} onClick={() => toggleFlag(key)}
                className={cn("w-full flex items-center gap-4 px-4 py-3.5 hover:bg-white/5 transition-colors", i < arr.length - 1 && "border-b border-white/5")}>
                <I className="h-5 w-5 text-gray-400 flex-shrink-0" />
                <span className="flex-1 text-white text-[15px] text-left">{label}</span>
                {editingFolder[key] ? <ToggleRight className="h-6 w-6 text-[#2AABEE]" /> : <ToggleLeft className="h-6 w-6 text-gray-600" />}
              </button>
            ))}
          </div>
        </div>
      </div>
    )
  }

  // ── List view ─────────────────────────────────────────────────────────────
  return (
    <div style={{ zIndex: 75 }} className={cn(
      "fixed inset-0 bg-[#17212b] flex flex-col transition-transform duration-300 ease-in-out",
      isOpen ? "translate-x-0" : "translate-x-full",
    )}>
      <header className="flex items-center gap-4 px-4 py-3 border-b border-white/10">
        <button onClick={onClose} className="p-2 -ml-2 text-gray-400 hover:text-white">
          <ArrowLeft className="h-6 w-6" />
        </button>
        <h1 className="text-xl font-medium text-white flex-1">Chat Folders</h1>
      </header>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {!activeAccount && <p className="text-gray-400 text-sm text-center py-8">Select an account first</p>}
        {isLoading && <div className="flex justify-center py-8"><Loader2 className="h-6 w-6 text-[#2AABEE] animate-spin" /></div>}

        {/* Preset folders — individual toggles */}
        {activeAccount && (
          <div className="bg-[#242f3d] rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-white/10">
              <p className="text-sky-400 text-sm font-medium">Preset Folders</p>
              <p className="text-gray-500 text-xs mt-0.5">Tap to add or remove each folder</p>
            </div>
            {PRESETS.map((preset, i) => {
              const iconDef = getIconDef(preset.iconId)
              const PresetIcon = iconDef.Icon
              const isAdded = existingIds.has(preset.id)
              const isCreating = creatingPreset === preset.id && createMutation.isPending
              const isDeleting = deleteMutation.isPending

              return (
                <div key={preset.id} className={cn(
                  "flex items-center gap-3 px-4 py-3.5",
                  i < PRESETS.length - 1 && "border-b border-white/5",
                )}>
                  <div className={cn(
                    "w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0",
                    isAdded ? "bg-[#2AABEE]/20" : "bg-white/5",
                  )}>
                    <PresetIcon className={cn("h-5 w-5", isAdded ? iconDef.color : "text-gray-500")} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className={cn("font-medium text-[15px]", isAdded ? "text-white" : "text-gray-400")}>
                      {preset.title}
                    </p>
                    <p className="text-gray-600 text-xs mt-0.5 truncate">{preset.desc}</p>
                  </div>
                  <button
                    onClick={() => isAdded ? deleteMutation.mutate(preset.id) : addPreset(preset)}
                    disabled={isCreating || isDeleting}
                    className={cn(
                      "flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
                      isAdded
                        ? "bg-red-500/20 text-red-400 hover:bg-red-500/30"
                        : "bg-[#2AABEE]/20 text-[#2AABEE] hover:bg-[#2AABEE]/30",
                    )}
                  >
                    {isCreating ? <Loader2 className="h-4 w-4 animate-spin" /> : isAdded ? "Remove" : "Add"}
                  </button>
                </div>
              )
            })}
          </div>
        )}

        {/* Existing custom folders */}
        {!isLoading && folders.filter(f => !f.is_default && !PRESETS.find(p => p.id === f.id)).length > 0 && (
          <div className="bg-[#242f3d] rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-white/10">
              <p className="text-sky-400 text-sm font-medium">Custom Folders</p>
            </div>
            {folders.filter(f => !f.is_default && !PRESETS.find(p => p.id === f.id)).map((folder, i, arr) => {
              const iconDef = getIconDef(folder.emoji)
              const FolderIcon = iconDef.Icon
              return (
                <li key={folder.id} className={cn(
                  "flex items-center gap-3 px-4 py-3.5 list-none",
                  i < arr.length - 1 && "border-b border-white/5",
                )}>
                  <div className="w-9 h-9 rounded-full bg-white/5 flex items-center justify-center flex-shrink-0">
                    <FolderIcon className={cn("h-5 w-5", iconDef.color)} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-white font-medium text-[15px] truncate">{folder.title}</p>
                    <p className="text-gray-500 text-xs mt-0.5">
                      {[folder.contacts && "Contacts", folder.groups && "Groups",
                        folder.broadcasts && "Channels", folder.bots && "Bots"].filter(Boolean).join(", ") || "Custom"}
                    </p>
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <button onClick={() => setEditingFolder({ ...folder, iconId: folder.emoji ?? undefined })}
                      className="p-2 text-gray-400 hover:text-[#2AABEE] transition-colors">
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button onClick={() => deleteMutation.mutate(folder.id)}
                      disabled={deleteMutation.isPending}
                      className="p-2 text-red-400 hover:text-red-300 transition-colors">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </li>
              )
            })}
          </div>
        )}

        {/* Create custom */}
        {activeAccount && (
          <button onClick={() => setEditingFolder({ ...EMPTY_FOLDER })}
            className="w-full flex items-center gap-4 px-4 py-4 bg-[#242f3d] rounded-xl hover:bg-[#2a3548] transition-colors">
            <div className="w-10 h-10 rounded-full bg-[#2AABEE]/20 flex items-center justify-center flex-shrink-0">
              <FolderPlus className="h-5 w-5 text-[#2AABEE]" />
            </div>
            <span className="text-[#2AABEE] font-medium text-[15px]">Create Custom Folder</span>
          </button>
        )}

        <p className="text-gray-600 text-xs text-center px-4">
          Folders sync with your Telegram account.
        </p>
      </div>
    </div>
  )
}
