import { useState } from "react"
import {
  ArrowLeft,
  Users,
  AtSign,
  Loader2,
  Download,
  ChevronRight,
  Bot,
  AlertTriangle,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { spamApi, apiErrorMessage, type ScrapedMember } from "@/lib/api"
import { useUser } from "@/contexts/user-context"
import { toast } from "sonner"

interface SpamMasterPageProps {
  isOpen: boolean
  onClose: () => void
}

type ActiveTool = "none" | "scraper" | "username"

export function SpamMasterPage({ isOpen, onClose }: SpamMasterPageProps) {
  const { activeAccount } = useUser()
  const [activeTool, setActiveTool] = useState<ActiveTool>("none")

  return (
    <div
      style={{ zIndex: 75 }}
      className={cn(
        "fixed inset-0 bg-[#17212b] flex flex-col transition-transform duration-300 ease-in-out",
        isOpen ? "translate-x-0" : "translate-x-full",
      )}
    >
      <header className="flex items-center gap-4 px-4 py-3 bg-[#17212b] border-b border-white/10">
        <button
          onClick={activeTool !== "none" ? () => setActiveTool("none") : onClose}
          className="p-2 -ml-2 text-gray-400 hover:text-white transition-colors"
          aria-label="Go back"
        >
          <ArrowLeft className="h-6 w-6" />
        </button>
        <h1 className="text-xl font-medium text-white">
          {activeTool === "scraper" ? "Contact Scraper" :
           activeTool === "username" ? "Username Checker" :
           "Spam Master"}
        </h1>
      </header>

      <div className="flex-1 overflow-y-auto">
        {activeTool === "none" && (
          <MenuView
            activeAccount={activeAccount?.name ?? null}
            onSelect={setActiveTool}
          />
        )}
        {activeTool === "scraper" && (
          <ScraperTool accountName={activeAccount?.name ?? ""} />
        )}
        {activeTool === "username" && (
          <UsernameTool accountName={activeAccount?.name ?? ""} />
        )}
      </div>
    </div>
  )
}

// ── Menu ────────────────────────────────────────────────────────────────────

function MenuView({
  activeAccount,
  onSelect,
}: {
  activeAccount: string | null
  onSelect: (t: ActiveTool) => void
}) {
  return (
    <div className="p-4 space-y-4">
      {!activeAccount && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4">
          <p className="text-yellow-400 text-sm text-center">Select an active account first</p>
        </div>
      )}

      {/* Web tools */}
      <div className="bg-[#242f3d] rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-white/10">
          <p className="text-sky-400 text-sm font-medium">Available via Dashboard</p>
        </div>
        <button
          disabled={!activeAccount}
          onClick={() => onSelect("scraper")}
          className="w-full flex items-center gap-4 px-4 py-4 hover:bg-white/5 transition-colors disabled:opacity-40 border-b border-white/5"
        >
          <div className="w-10 h-10 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0">
            <Users className="h-5 w-5 text-green-400" />
          </div>
          <div className="flex-1 text-left">
            <p className="text-white text-sm font-medium">Contact Scraper</p>
            <p className="text-gray-500 text-xs mt-0.5">Extract member list from any group/channel</p>
          </div>
          <ChevronRight className="h-4 w-4 text-gray-500" />
        </button>

        <button
          disabled={!activeAccount}
          onClick={() => onSelect("username")}
          className="w-full flex items-center gap-4 px-4 py-4 hover:bg-white/5 transition-colors disabled:opacity-40"
        >
          <div className="w-10 h-10 rounded-full bg-purple-500/20 flex items-center justify-center flex-shrink-0">
            <AtSign className="h-5 w-5 text-purple-400" />
          </div>
          <div className="flex-1 text-left">
            <p className="text-white text-sm font-medium">Username Checker</p>
            <p className="text-gray-500 text-xs mt-0.5">Find available Telegram usernames</p>
          </div>
          <ChevronRight className="h-4 w-4 text-gray-500" />
        </button>
      </div>

      {/* Bot-only tools */}
      <div className="bg-[#242f3d] rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-white/10">
          <div className="flex items-center gap-2">
            <Bot className="h-4 w-4 text-gray-400" />
            <p className="text-gray-400 text-sm font-medium">Bot-only tools</p>
          </div>
          <p className="text-gray-600 text-xs mt-0.5">Use these via the Telegram bot (require ToS acceptance)</p>
        </div>
        {[
          { label: "Mass Inviter",      desc: "Bulk invite scraped users to groups" },
          { label: "Forward Bomber",    desc: "Mass forward messages to users" },
          { label: "Message Flooder",   desc: "Rapid message sending to a target" },
          { label: "Raid Coordinator",  desc: "Multi-account coordinated raids" },
          { label: "Stealth Raid",      desc: "Human-like raid patterns" },
          { label: "Multi-Target Raid", desc: "Simultaneous raids on multiple targets" },
        ].map(({ label, desc }) => (
          <div
            key={label}
            className="flex items-center gap-4 px-4 py-3 border-b border-white/5 opacity-50"
          >
            <Bot className="h-4 w-4 text-gray-500 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-gray-400 text-sm">{label}</p>
              <p className="text-gray-600 text-xs mt-0.5">{desc}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Warning */}
      <div className="flex items-start gap-3 px-4 py-3 bg-orange-500/10 border border-orange-500/20 rounded-xl">
        <AlertTriangle className="h-4 w-4 text-orange-400 flex-shrink-0 mt-0.5" />
        <p className="text-orange-400 text-xs">
          Bot-only tools violate Telegram's ToS and may result in account bans.
          Use only on throwaway accounts.
        </p>
      </div>
    </div>
  )
}

// ── Contact Scraper ──────────────────────────────────────────────────────────

function ScraperTool({ accountName }: { accountName: string }) {
  const [target, setTarget] = useState("")
  const [limit, setLimit] = useState("500")
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ScrapedMember[] | null>(null)
  const [count, setCount] = useState(0)

  const handleScrape = async () => {
    if (!target.trim()) { toast.error("Enter a group or channel"); return }
    setLoading(true)
    setResult(null)
    try {
      const res = await spamApi.scrapeMembers(accountName, target.trim(), parseInt(limit) || 500)
      setResult(res.members)
      setCount(res.count)
      toast.success(`Scraped ${res.count} members`)
    } catch (e) {
      toast.error(apiErrorMessage(e))
    } finally {
      setLoading(false)
    }
  }

  const handleDownloadCSV = () => {
    if (!result) return
    const header = "id,username,first_name,last_name,phone"
    const rows = result.map(m =>
      `${m.id},${m.username ?? ""},${m.first_name},${m.last_name},${m.phone ?? ""}`
    )
    const csv = [header, ...rows].join("\n")
    const blob = new Blob([csv], { type: "text/csv" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `members_${target.replace(/[^a-z0-9]/gi, "_")}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="p-4 space-y-4">
      <div className="space-y-3">
        <div>
          <label className="text-gray-400 text-xs font-medium block mb-1.5">
            Group / Channel
          </label>
          <input
            type="text"
            value={target}
            onChange={e => setTarget(e.target.value)}
            placeholder="@groupname or t.me/group"
            className="w-full bg-[#1e2c3a] border border-white/10 rounded-xl px-4 py-3 text-white text-sm placeholder:text-gray-600 outline-none focus:border-sky-500/50"
          />
        </div>
        <div>
          <label className="text-gray-400 text-xs font-medium block mb-1.5">
            Max members
          </label>
          <input
            type="number"
            value={limit}
            onChange={e => setLimit(e.target.value)}
            min="10"
            max="5000"
            className="w-full bg-[#1e2c3a] border border-white/10 rounded-xl px-4 py-3 text-white text-sm outline-none focus:border-sky-500/50"
          />
        </div>
        <button
          onClick={handleScrape}
          disabled={loading || !accountName || !target.trim()}
          className="w-full flex items-center justify-center gap-2 py-3 bg-sky-500 hover:bg-sky-600 disabled:opacity-50 text-white rounded-xl font-medium text-sm transition-colors"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Users className="h-4 w-4" />}
          {loading ? "Scraping…" : "Scrape Members"}
        </button>
      </div>

      {result && (
        <div className="bg-[#242f3d] rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
            <p className="text-sky-400 text-sm font-medium">{count} members scraped</p>
            <button
              onClick={handleDownloadCSV}
              className="flex items-center gap-1.5 text-sky-400 hover:text-sky-300 text-xs font-medium"
            >
              <Download className="h-3.5 w-3.5" />
              CSV
            </button>
          </div>
          <ul className="divide-y divide-white/5 max-h-80 overflow-y-auto">
            {result.slice(0, 100).map(m => (
              <li key={m.id} className="flex items-center gap-3 px-4 py-2.5">
                <div className="w-8 h-8 rounded-full bg-sky-500/20 flex items-center justify-center flex-shrink-0 text-sky-400 text-xs font-bold">
                  {(m.first_name || m.username || "?").charAt(0).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-white text-sm truncate">
                    {[m.first_name, m.last_name].filter(Boolean).join(" ") || `id:${m.id}`}
                  </p>
                  {m.username && (
                    <p className="text-gray-500 text-xs">@{m.username}</p>
                  )}
                </div>
              </li>
            ))}
            {result.length > 100 && (
              <li className="px-4 py-3 text-center text-gray-500 text-xs">
                … and {result.length - 100} more (download CSV for full list)
              </li>
            )}
          </ul>
        </div>
      )}
    </div>
  )
}

// ── Username Checker ─────────────────────────────────────────────────────────

function UsernameTool({ accountName }: { accountName: string }) {
  const [base, setBase] = useState("")
  const [count, setCount] = useState("30")
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<string[] | null>(null)
  const [checked, setChecked] = useState(0)

  const handleCheck = async () => {
    if (!base.trim()) { toast.error("Enter a base username"); return }
    setLoading(true)
    setResult(null)
    try {
      const res = await spamApi.checkUsernames(accountName, base.trim(), parseInt(count) || 30)
      setResult(res.available)
      setChecked(res.checked)
      toast.success(`${res.available_count} available out of ${res.checked} checked`)
    } catch (e) {
      toast.error(apiErrorMessage(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-4 space-y-4">
      <div className="space-y-3">
        <div>
          <label className="text-gray-400 text-xs font-medium block mb-1.5">
            Base username
          </label>
          <input
            type="text"
            value={base}
            onChange={e => setBase(e.target.value.replace(/[^a-zA-Z0-9]/g, ""))}
            placeholder="e.g. coolname"
            className="w-full bg-[#1e2c3a] border border-white/10 rounded-xl px-4 py-3 text-white text-sm placeholder:text-gray-600 outline-none focus:border-sky-500/50"
          />
          <p className="text-gray-600 text-xs mt-1">
            Checks coolname1, coolname42, coolname7, etc.
          </p>
        </div>
        <div>
          <label className="text-gray-400 text-xs font-medium block mb-1.5">
            How many to find
          </label>
          <input
            type="number"
            value={count}
            onChange={e => setCount(e.target.value)}
            min="5"
            max="100"
            className="w-full bg-[#1e2c3a] border border-white/10 rounded-xl px-4 py-3 text-white text-sm outline-none focus:border-sky-500/50"
          />
        </div>
        <button
          onClick={handleCheck}
          disabled={loading || !accountName || !base.trim()}
          className="w-full flex items-center justify-center gap-2 py-3 bg-purple-500 hover:bg-purple-600 disabled:opacity-50 text-white rounded-xl font-medium text-sm transition-colors"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <AtSign className="h-4 w-4" />}
          {loading ? `Checking… (${checked} done)` : "Check Usernames"}
        </button>
      </div>

      {result && (
        <div className="bg-[#242f3d] rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-white/10">
            <p className="text-purple-400 text-sm font-medium">
              {result.length} available out of {checked} checked
            </p>
          </div>
          {result.length === 0 ? (
            <p className="text-gray-500 text-sm text-center py-6">
              No available usernames found — try a different base
            </p>
          ) : (
            <ul className="divide-y divide-white/5 max-h-80 overflow-y-auto">
              {result.map(u => (
                <li key={u} className="flex items-center gap-3 px-4 py-3">
                  <AtSign className="h-4 w-4 text-purple-400 flex-shrink-0" />
                  <span className="text-white text-sm font-mono">@{u}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
