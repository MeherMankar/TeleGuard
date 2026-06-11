import { useState } from "react"
import {
  ArrowLeft, Plus, Trash2, Pencil, Loader2, Folder, Users,
  Radio, Bot, Check, X, User, UserX, VolumeX, MailOpen, Archive,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { chatsApi, type ChatFolder } from "@/lib/api"
import { useUser } from "@/contexts/user-context"
import { toast } from "sonner"

// Telegram folder emojis
const FOLDER_EMOJIS = ["📁", "⭐", "👥", "📢", "🤖", "❤️", "💼", "🏠", "🎮", "📚", "🎵", "💬", "🔔", "🌍"]

interface ChatFoldersPageProps {
  isOpen: boolean
  onClose: () => void
}

const DEFAULT_FOLDER: Partial<ChatFolder> = {
  title: "",
  emoji: null,
  contacts: false,
  non_contacts: false,
  groups: false,
  broadcasts: false,
  bots: false,
  exclude_muted: false,
  exclude_read: false,
  exclude_archived: false,
}

export function ChatFoldersPage({ isOpen, onClose }: ChatFoldersPageProps) {
  const { activeAccount } = useUser()
  const qc = useQueryClient()
  const [editingFolder, setEditingFolder] = useState<Partial<ChatFolder> | null>(null)
  const [showEmojiPicker, setShowEmojiPicker] = useState(false)

  const { data: folders = [], isLoading } = useQuery({
    queryKey: ["folders", activeAccount?.name],
    queryFn: () => chatsApi.folders(activeAccount!.name),
    enabled: isOpen && !!activeAccount,
    staleTime: 30_000,
  })

  const createMutation = useMutation({
    mutationFn: (folder: Partial<ChatFolder>) =>
      chatsApi.createFolder(activeAccount!.name, folder),
    onSuccess: (res) => {
      toast.success(`Folder "${res.title}" saved`)
      setEditingFolder(null)
      qc.invalidateQueries({ queryKey: ["folders", activeAccount?.name] })
    },
    onError: (e) => toast.error((e as Error).message),
  })

  const presetMutation = useMutation({
    mutationFn: () => chatsApi.createPresetFolders(activeAccount!.name),
    onSuccess: (res) => {
      toast.success(`Created: ${res.created.join(", ")}`)
      qc.invalidateQueries({ queryKey: ["folders", activeAccount?.name] })
    },
    onError: (e) => toast.error((e as Error).message),
  })

  const deleteMutation = useMutation({
    mutationFn: (folderId: number) =>
      chatsApi.deleteFolder(activeAccount!.name, folderId),
    onSuccess: () => {
      toast.success("Folder deleted")
      qc.invalidateQueries({ queryKey: ["folders", activeAccount?.name] })
    },
    onError: (e) => toast.error((e as Error).message),
  })

  const handleSave = () => {
    if (!editingFolder?.title?.trim()) {
      toast.error("Folder name is required")
      return
    }
    createMutation.mutate(editingFolder)
  }

  const toggleFlag = (key: keyof ChatFolder) => {
    setEditingFolder((prev) => prev ? { ...prev, [key]: !prev[key] } : prev)
  }

  // If editing — show editor view
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
          <button
            onClick={handleSave}
            disabled={createMutation.isPending}
            className="px-4 py-1.5 bg-[#2AABEE] text-white rounded-lg text-sm font-medium flex items-center gap-1.5 disabled:opacity-50"
          >
            {createMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
            Save
          </button>
        </header>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Folder name */}
          <div className="bg-[#242f3d] rounded-xl p-4">
            <p className="text-sky-400 text-xs font-medium uppercase tracking-wider mb-3">Folder Name</p>
            <div className="flex items-center gap-3">
              {/* Emoji button */}
              <div className="relative">
                <button
                  onClick={() => setShowEmojiPicker(!showEmojiPicker)}
                  className="w-12 h-12 rounded-xl bg-[#17212b] flex items-center justify-center text-2xl border border-white/10 hover:border-[#2AABEE] transition-colors"
                >
                  {editingFolder.emoji || <Folder className="h-5 w-5 text-gray-400" />}
                </button>
                {showEmojiPicker && (
                  <div className="absolute top-14 left-0 bg-[#1c2b3a] border border-white/10 rounded-xl p-3 grid grid-cols-7 gap-2 z-10 shadow-xl">
                    {FOLDER_EMOJIS.map((emoji) => (
                      <button
                        key={emoji}
                        onClick={() => {
                          setEditingFolder((p) => p ? { ...p, emoji } : p)
                          setShowEmojiPicker(false)
                        }}
                        className="text-xl hover:bg-white/10 rounded p-1"
                      >
                        {emoji}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <input
                value={editingFolder.title || ""}
                onChange={(e) => setEditingFolder((p) => p ? { ...p, title: e.target.value } : p)}
                placeholder="Folder name"
                maxLength={12}
                className="flex-1 bg-[#17212b] text-white rounded-xl px-4 py-3 border border-white/10 focus:border-[#2AABEE] focus:outline-none text-[15px]"
                autoFocus
              />
            </div>
          </div>

          {/* Include chat types */}
          <div className="bg-[#242f3d] rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-white/10">
              <p className="text-sky-400 text-xs font-medium uppercase tracking-wider">Include Chat Types</p>
              <p className="text-gray-500 text-xs mt-0.5">Chats of these types will appear in this folder</p>
            </div>
            {[
              { key: "contacts" as const, label: "Contacts", icon: User, color: "text-blue-400" },
              { key: "non_contacts" as const, label: "Non-Contacts", icon: UserX, color: "text-purple-400" },
              { key: "groups" as const, label: "Groups", icon: Users, color: "text-green-400" },
              { key: "broadcasts" as const, label: "Channels", icon: Radio, color: "text-amber-400" },
              { key: "bots" as const, label: "Bots", icon: Bot, color: "text-red-400" },
            ].map(({ key, label, icon: Icon, color }, i, arr) => (
              <button
                key={key}
                onClick={() => toggleFlag(key)}
                className={cn("w-full flex items-center gap-4 px-4 py-3.5 hover:bg-white/5 transition-colors",
                  i < arr.length - 1 && "border-b border-white/5")}
              >
                <Icon className={cn("h-5 w-5 flex-shrink-0", color)} />
                <span className="flex-1 text-white text-[15px] text-left">{label}</span>
                {editingFolder[key] && <Check className="h-5 w-5 text-[#2AABEE]" />}
              </button>
            ))}
          </div>

          {/* Exclude options */}
          <div className="bg-[#242f3d] rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-white/10">
              <p className="text-sky-400 text-xs font-medium uppercase tracking-wider">Exclude Options</p>
            </div>
            {[
              { key: "exclude_muted" as const, label: "Exclude Muted", icon: VolumeX },
              { key: "exclude_read" as const, label: "Exclude Read", icon: MailOpen },
              { key: "exclude_archived" as const, label: "Exclude Archived", icon: Archive },
            ].map(({ key, label, icon: Icon }, i, arr) => (
              <button
                key={key}
                onClick={() => toggleFlag(key)}
                className={cn("w-full flex items-center gap-4 px-4 py-3.5 hover:bg-white/5 transition-colors",
                  i < arr.length - 1 && "border-b border-white/5")}
              >
                <Icon className="h-5 w-5 text-gray-400 flex-shrink-0" />
                <span className="flex-1 text-white text-[15px] text-left">{label}</span>
                {editingFolder[key] && <Check className="h-5 w-5 text-[#2AABEE]" />}
              </button>
            ))}
          </div>
        </div>
      </div>
    )
  }

  // Folder list view
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
        {!activeAccount && (
          <p className="text-gray-400 text-sm text-center py-8">Select an account first</p>
        )}

        {isLoading && (
          <div className="flex justify-center py-8"><Loader2 className="h-6 w-6 text-[#2AABEE] animate-spin" /></div>
        )}

        {!isLoading && folders.length > 0 && (
          <div className="bg-[#242f3d] rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-white/10">
              <span className="text-sky-400 text-sm font-medium">Your Folders ({folders.length})</span>
            </div>
            <ul role="list">
              {folders.map((folder, i) => (
                <li key={folder.id} className={cn("flex items-center gap-3 px-4 py-3.5", i < folders.length - 1 && "border-b border-white/5")}>
                  <span className="text-xl w-8 text-center flex-shrink-0">
                    {folder.emoji || (folder.is_default ? "💬" : "📁")}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-white font-medium text-[15px] truncate">{folder.title}</p>
                    <p className="text-gray-500 text-xs mt-0.5">
                      {folder.is_default
                        ? "Default — all chats"
                        : [
                            folder.contacts && "Contacts",
                            folder.non_contacts && "Non-Contacts",
                            folder.groups && "Groups",
                            folder.broadcasts && "Channels",
                            folder.bots && "Bots",
                          ].filter(Boolean).join(", ") || "Custom folder"}
                    </p>
                  </div>
                  {!folder.is_default && (
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <button
                        onClick={() => setEditingFolder({ ...folder })}
                        className="p-2 text-gray-400 hover:text-[#2AABEE] transition-colors"
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => deleteMutation.mutate(folder.id)}
                        disabled={deleteMutation.isPending}
                        className="p-2 text-red-400 hover:text-red-300 transition-colors"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Create new folder */}
        {activeAccount && (
          <div className="space-y-2">
            {/* Add smart preset folders */}
            <button
              onClick={() => presetMutation.mutate()}
              disabled={presetMutation.isPending}
              className="w-full flex items-center gap-4 px-4 py-4 bg-[#242f3d] rounded-xl hover:bg-[#2a3548] transition-colors"
            >
              <div className="w-10 h-10 rounded-full bg-amber-500/20 flex items-center justify-center flex-shrink-0">
                {presetMutation.isPending
                  ? <Loader2 className="h-5 w-5 text-amber-400 animate-spin" />
                  : <span className="text-lg">⚡</span>
                }
              </div>
              <div className="text-left">
                <p className="text-amber-400 font-medium text-[15px]">Add Preset Folders</p>
                <p className="text-gray-500 text-xs">Personal · Groups · Channels · Bots · Admin · Unread</p>
              </div>
            </button>

            <button
              onClick={() => setEditingFolder({ ...DEFAULT_FOLDER })}
              className="w-full flex items-center gap-4 px-4 py-4 bg-[#242f3d] rounded-xl hover:bg-[#2a3548] transition-colors"
            >
              <div className="w-10 h-10 rounded-full bg-[#2AABEE]/20 flex items-center justify-center flex-shrink-0">
                <Plus className="h-5 w-5 text-[#2AABEE]" />
              </div>
              <span className="text-[#2AABEE] font-medium text-[15px]">Create Custom Folder</span>
            </button>
          </div>
        )}

        <p className="text-gray-600 text-xs text-center px-4">
          Folders sync with your Telegram account — visible on all your devices.
        </p>
      </div>
    </div>
  )
}
