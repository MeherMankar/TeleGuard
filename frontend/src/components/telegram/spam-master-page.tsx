import { ArrowLeft, Send, Users, AtSign, Forward, Waves, Swords, Ghost, Target } from "lucide-react"
import { cn } from "@/lib/utils"

interface SpamMasterPageProps {
  isOpen: boolean
  onClose: () => void
}

const spamTools = [
  {
    icon: Send,
    label: "Mass Inviter",
    description: "Bulk invite users to groups",
    color: "bg-blue-500",
  },
  {
    icon: Users,
    label: "Contact Scraper",
    description: "Extract contacts from groups",
    color: "bg-green-500",
  },
  {
    icon: AtSign,
    label: "Username Checker",
    description: "Find available usernames",
    color: "bg-purple-500",
  },
  {
    icon: Forward,
    label: "Forward Bomber",
    description: "Mass forward messages",
    color: "bg-orange-500",
  },
  {
    icon: Waves,
    label: "Message Flooder",
    description: "Rapid message flooding",
    color: "bg-cyan-500",
  },
  {
    icon: Swords,
    label: "Raid Coordinator",
    description: "Multi-account raids",
    color: "bg-red-500",
  },
  {
    icon: Ghost,
    label: "Stealth Raid",
    description: "Human-like raid patterns",
    color: "bg-gray-600",
  },
  {
    icon: Target,
    label: "Multi-Target",
    description: "Attack multiple groups",
    color: "bg-pink-500",
  },
]

export function SpamMasterPage({ isOpen, onClose }: SpamMasterPageProps) {
  return (
    <div
      style={{ zIndex: 70 }}
      className={cn(
        "fixed top-0 right-0 h-screen w-full max-w-md bg-[#17212b] flex flex-col transition-transform duration-300 ease-in-out",
        isOpen ? "translate-x-0" : "translate-x-full"
      )}
    >
      {/* Header */}
      <header className="flex items-center gap-4 px-4 py-3 bg-[#17212b] border-b border-white/10">
        <button
          onClick={onClose}
          className="p-2 -ml-2 text-gray-400 hover:text-white transition-colors"
          aria-label="Go back"
        >
          <ArrowLeft className="h-6 w-6" />
        </button>
        <h1 className="text-xl font-medium text-white">Spam Master</h1>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {/* Hero Section */}
        <div className="bg-[#242f3d] rounded-xl p-6 mb-6">
          <div className="w-16 h-16 rounded-full bg-gradient-to-br from-red-600 to-pink-500 flex items-center justify-center mb-4 mx-auto">
            <Swords className="h-8 w-8 text-white" />
          </div>
          <h2 className="text-center text-white font-semibold text-lg mb-2">
            Mass Action Tools
          </h2>
          <p className="text-center text-gray-400 text-sm">
            Powerful tools for bulk messaging and group management
          </p>
        </div>

        {/* Spam Tools */}
        <div className="bg-[#242f3d] rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-white/10">
            <span className="text-sky-400 text-sm font-medium">Available Tools</span>
          </div>
          {spamTools.map((tool, index) => (
            <button
              key={tool.label}
              className={cn(
                "w-full flex items-center gap-4 px-4 py-4 hover:bg-white/5 transition-colors",
                index !== spamTools.length - 1 && "border-b border-white/5"
              )}
            >
              <div className={cn("w-10 h-10 rounded-full flex items-center justify-center", tool.color)}>
                <tool.icon className="h-5 w-5 text-white" />
              </div>
              <div className="flex-1 text-left">
                <p className="text-white font-medium">{tool.label}</p>
                <p className="text-gray-400 text-sm">{tool.description}</p>
              </div>
            </button>
          ))}
        </div>

        {/* Warning */}
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 mt-4">
          <p className="text-red-400 text-xs text-center">
            Warning: These tools are for educational purposes only. Misuse may violate terms of service and result in permanent bans.
          </p>
        </div>
      </div>
    </div>
  )
}
