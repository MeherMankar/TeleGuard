import { useState, useCallback } from "react"
import {
  ArrowLeft,
  Zap,
  MessageSquareReply,
  Plus,
  Trash2,
  Loader2,
  Bot,
  Send,
  Users,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { autoReplyApi, messagingApi, apiErrorMessage } from "@/lib/api"
import { useUser } from "@/contexts/user-context"
import { useWsEvent } from "@/hooks/use-ws-event"
import { toast } from "sonner"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"

interface AutomationPageProps {
  isOpen: boolean
  onClose: () => void
}

export function AutomationPage({ isOpen, onClose }: AutomationPageProps) {
  const { activeAccount, accounts } = useUser()
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<"keywords" | "jobs" | "bulk">("keywords")
  const [newKeyword, setNewKeyword] = useState("")
  const [newReply, setNewReply] = useState("")
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)

  // Create Job state
  const [showCreateJob, setShowCreateJob] = useState(false)
  const [jobType, setJobType] = useState("send_message")
  const [jobInterval, setJobInterval] = useState("3600")
  const [jobTarget, setJobTarget] = useState("")
  const [jobMessage, setJobMessage] = useState("")

  // Bulk send state
  const [bulkTargets, setBulkTargets] = useState("")
  const [bulkMessage, setBulkMessage] = useState("")

  // WS: refresh jobs when automation_log arrives
  useWsEvent("automation_log", useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["jobs"] })
  }, [queryClient]))

  const { data: arSettings, isLoading: arLoading } = useQuery({
    queryKey: ["auto-reply"],
    queryFn: autoReplyApi.settings,
    enabled: isOpen,
  })

  const { data: jobs = [], isLoading: jobsLoading } = useQuery({
    queryKey: ["jobs"],
    queryFn: messagingApi.jobs,
    enabled: isOpen && activeTab === "jobs",
  })

  const addKeywordMutation = useMutation({
    mutationFn: () => autoReplyApi.addKeyword(newKeyword.trim(), newReply.trim()),
    onSuccess: () => {
      toast.success("Keyword added")
      setNewKeyword("")
      setNewReply("")
      queryClient.invalidateQueries({ queryKey: ["auto-reply"] })
    },
    onError: (e) => toast.error((e as Error).message),
  })

  const deleteKeywordMutation = useMutation({
    mutationFn: (keyword: string) => autoReplyApi.deleteKeyword(keyword),
    onSuccess: () => {
      toast.success("Keyword deleted")
      setDeleteTarget(null)
      queryClient.invalidateQueries({ queryKey: ["auto-reply"] })
    },
    onError: (e) => toast.error((e as Error).message),
  })

  const deleteJobMutation = useMutation({
    mutationFn: (job_id: string) => messagingApi.deleteJob(job_id),
    onSuccess: () => {
      toast.success("Job deleted")
      queryClient.invalidateQueries({ queryKey: ["jobs"] })
    },
    onError: (e) => toast.error((e as Error).message),
  })

  const createJobMutation = useMutation({
    mutationFn: () => messagingApi.createJob({
      account_id: activeAccount?.id ?? "",
      job_type: jobType,
      job_config: { target: jobTarget, message: jobMessage },
      interval_seconds: parseInt(jobInterval) || 3600,
    }),
    onSuccess: () => {
      toast.success("Job created")
      setShowCreateJob(false)
      setJobTarget(""); setJobMessage("")
      queryClient.invalidateQueries({ queryKey: ["jobs"] })
    },
    onError: (e) => toast.error(apiErrorMessage(e)),
  })

  const bulkMutation = useMutation({
    mutationFn: () => {
      const targets = bulkTargets.split("\n").map(t => t.trim()).filter(Boolean)
      return messagingApi.bulk(activeAccount!.name, targets, bulkMessage.trim())
    },
    onSuccess: (res) => {
      toast.success(res.message || "Bulk message queued")
      setBulkTargets(""); setBulkMessage("")
    },
    onError: (e) => toast.error(apiErrorMessage(e)),
  })

  const keywords = arSettings?.keywords ?? {}

  return (
    <>
      <div
        style={{ zIndex: 75 }}
        className={cn(
          "fixed inset-0 bg-[#17212b] flex flex-col transition-transform duration-300 ease-in-out",
          isOpen ? "translate-x-0" : "translate-x-full",
        )}
      >
        <header className="flex items-center gap-4 px-4 py-3 bg-[#17212b] border-b border-white/10">
          <button
            onClick={onClose}
            className="p-2 -ml-2 text-gray-400 hover:text-white transition-colors"
            aria-label="Go back"
          >
            <ArrowLeft className="h-6 w-6" />
          </button>
          <h1 className="text-xl font-medium text-white">Automation</h1>
        </header>

        {/* Tabs */}
        <div className="flex border-b border-white/10">
          {(["keywords", "jobs", "bulk"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                "flex-1 py-3 text-sm font-medium capitalize transition-colors",
                activeTab === tab
                  ? "text-[#2AABEE] border-b-2 border-[#2AABEE]"
                  : "text-gray-400 hover:text-white",
              )}
            >
              {tab === "keywords" ? "Auto Reply" : tab === "bulk" ? "Bulk Send" : "Jobs"}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto">
          {activeTab === "keywords" && (
            <div className="p-4 space-y-4">
              {/* Add keyword form */}
              <div className="bg-[#242f3d] rounded-xl p-4 space-y-3">
                <p className="text-sky-400 text-sm font-medium flex items-center gap-2">
                  <MessageSquareReply className="h-4 w-4" /> Add Auto-Reply Keyword
                </p>
                <input
                  value={newKeyword}
                  onChange={(e) => setNewKeyword(e.target.value)}
                  placeholder="Keyword (e.g. hello)"
                  className="w-full bg-[#17212b] text-white text-sm rounded-lg px-3 py-2 border border-white/10 focus:border-[#2AABEE] focus:outline-none"
                />
                <input
                  value={newReply}
                  onChange={(e) => setNewReply(e.target.value)}
                  placeholder="Reply message"
                  className="w-full bg-[#17212b] text-white text-sm rounded-lg px-3 py-2 border border-white/10 focus:border-[#2AABEE] focus:outline-none"
                />
                <button
                  onClick={() => addKeywordMutation.mutate()}
                  disabled={!newKeyword.trim() || !newReply.trim() || addKeywordMutation.isPending}
                  className="w-full py-2 bg-[#2AABEE] text-white rounded-lg text-sm font-medium disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {addKeywordMutation.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Plus className="h-4 w-4" />
                  )}
                  Add Keyword
                </button>
              </div>

              {/* Keywords list */}
              {arLoading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="h-6 w-6 text-[#2AABEE] animate-spin" />
                </div>
              ) : Object.keys(keywords).length === 0 ? (
                <p className="text-gray-400 text-sm text-center py-8">
                  No keywords yet. Add one above.
                </p>
              ) : (
                <div className="bg-[#242f3d] rounded-xl overflow-hidden">
                  <div className="px-4 py-3 border-b border-white/10">
                    <span className="text-sky-400 text-sm font-medium">
                      Active Keywords ({Object.keys(keywords).length})
                    </span>
                  </div>
                  <ul role="list">
                    {Object.entries(keywords).map(([kw, reply], i) => (
                      <li
                        key={kw}
                        className={cn(
                          "flex items-center gap-3 px-4 py-3",
                          i < Object.keys(keywords).length - 1 && "border-b border-white/5",
                        )}
                      >
                        <div className="flex-1 min-w-0">
                          <p className="text-white text-sm font-medium truncate">{kw}</p>
                          <p className="text-gray-400 text-xs truncate">{reply}</p>
                        </div>
                        <button
                          onClick={() => setDeleteTarget(kw)}
                          className="p-1.5 text-red-400 hover:text-red-300 transition-colors"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {activeTab === "jobs" && (
            <div className="p-4 space-y-4">
              {!activeAccount && (
                <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4">
                  <p className="text-yellow-400 text-sm text-center">
                    Select an active account to manage jobs
                  </p>
                </div>
              )}

              {/* Create Job button */}
              {activeAccount && (
                <button
                  onClick={() => setShowCreateJob(true)}
                  className="w-full flex items-center justify-center gap-2 py-2.5 bg-[#2AABEE]/10 border border-[#2AABEE]/30 text-[#2AABEE] rounded-xl text-sm font-medium hover:bg-[#2AABEE]/20 transition-colors"
                >
                  <Plus className="h-4 w-4" /> Create Automation Job
                </button>
              )}

              {jobsLoading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="h-6 w-6 text-[#2AABEE] animate-spin" />
                </div>
              ) : jobs.length === 0 ? (
                <div className="text-center py-12">
                  <Bot className="h-12 w-12 text-gray-600 mx-auto mb-3" />
                  <p className="text-gray-400 text-sm">No automation jobs configured</p>
                </div>
              ) : (
                <div className="bg-[#242f3d] rounded-xl overflow-hidden">
                  <div className="px-4 py-3 border-b border-white/10">
                    <span className="text-sky-400 text-sm font-medium">
                      Jobs ({jobs.length})
                    </span>
                  </div>
                  <ul role="list">
                    {jobs.map((job, i) => (
                      <li
                        key={job.id}
                        className={cn(
                          "flex items-center gap-3 px-4 py-3",
                          i < jobs.length - 1 && "border-b border-white/5",
                        )}
                      >
                        <div className="w-8 h-8 rounded-full bg-[#2AABEE]/20 flex items-center justify-center flex-shrink-0">
                          <Zap className="h-4 w-4 text-[#2AABEE]" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-white text-sm font-medium capitalize">
                            {job.job_type.replace(/_/g, " ")}
                          </p>
                          <p className="text-gray-400 text-xs">
                            Every {job.interval_seconds}s ·{" "}
                            {job.enabled ? (
                              <span className="text-green-400">Active</span>
                            ) : (
                              <span className="text-gray-500">Paused</span>
                            )}
                          </p>
                        </div>
                        <button
                          onClick={() => deleteJobMutation.mutate(job.id)}
                          disabled={deleteJobMutation.isPending}
                          className="p-1.5 text-red-400 hover:text-red-300 transition-colors"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* ── Bulk Send tab ────────────────────────────────────────── */}
          {activeTab === "bulk" && (
            <div className="p-4 space-y-4">
              {!activeAccount && (
                <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4">
                  <p className="text-yellow-400 text-sm text-center">Select an active account first</p>
                </div>
              )}
              <div className="bg-[#242f3d] rounded-xl p-4 space-y-3">
                <p className="text-sky-400 text-sm font-medium flex items-center gap-2">
                  <Users className="h-4 w-4" /> Bulk Message
                </p>
                <div>
                  <label className="text-gray-400 text-xs block mb-1">Targets (one per line — @username, +phone, or chat ID)</label>
                  <textarea
                    value={bulkTargets}
                    onChange={e => setBulkTargets(e.target.value)}
                    rows={4}
                    placeholder={"@user1\n@user2\n+1234567890"}
                    className="w-full bg-[#17212b] text-white text-sm rounded-lg px-3 py-2 border border-white/10 focus:border-[#2AABEE] focus:outline-none resize-none"
                  />
                </div>
                <div>
                  <label className="text-gray-400 text-xs block mb-1">Message</label>
                  <textarea
                    value={bulkMessage}
                    onChange={e => setBulkMessage(e.target.value)}
                    rows={3}
                    placeholder="Your message..."
                    className="w-full bg-[#17212b] text-white text-sm rounded-lg px-3 py-2 border border-white/10 focus:border-[#2AABEE] focus:outline-none resize-none"
                  />
                </div>
                <button
                  onClick={() => bulkMutation.mutate()}
                  disabled={!activeAccount || !bulkTargets.trim() || !bulkMessage.trim() || bulkMutation.isPending}
                  className="w-full flex items-center justify-center gap-2 py-2.5 bg-[#2AABEE] hover:bg-[#2AABEE]/90 disabled:opacity-50 text-white rounded-xl text-sm font-medium transition-colors"
                >
                  {bulkMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                  {bulkMutation.isPending ? "Sending…" : "Send to All"}
                </button>
              </div>
              <p className="text-gray-600 text-xs text-center">
                Messages are sent in the background. Flood limits are respected automatically.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Create Job modal */}
      {showCreateJob && (
        <div className="fixed inset-0 z-[85] bg-black/70 flex items-end justify-center" onClick={() => setShowCreateJob(false)}>
          <div className="bg-[#17212b] w-full max-w-md rounded-t-2xl p-5 space-y-4" onClick={e => e.stopPropagation()}>
            <h2 className="text-white font-semibold text-lg">Create Automation Job</h2>
            <div>
              <label className="text-gray-400 text-xs block mb-1">Job Type</label>
              <select
                value={jobType}
                onChange={e => setJobType(e.target.value)}
                className="w-full bg-[#242f3d] text-white text-sm rounded-lg px-3 py-2 border border-white/10 focus:outline-none"
              >
                <option value="send_message">Send Message</option>
                <option value="forward_message">Forward Message</option>
                <option value="bulk_invite">Bulk Invite</option>
              </select>
            </div>
            <div>
              <label className="text-gray-400 text-xs block mb-1">Target (chat / @username)</label>
              <input
                type="text"
                value={jobTarget}
                onChange={e => setJobTarget(e.target.value)}
                placeholder="@channel or chat ID"
                className="w-full bg-[#242f3d] text-white text-sm rounded-lg px-3 py-2 border border-white/10 focus:border-[#2AABEE] focus:outline-none"
              />
            </div>
            <div>
              <label className="text-gray-400 text-xs block mb-1">Message</label>
              <textarea
                value={jobMessage}
                onChange={e => setJobMessage(e.target.value)}
                rows={2}
                placeholder="Message to send…"
                className="w-full bg-[#242f3d] text-white text-sm rounded-lg px-3 py-2 border border-white/10 focus:border-[#2AABEE] focus:outline-none resize-none"
              />
            </div>
            <div>
              <label className="text-gray-400 text-xs block mb-1">Interval (seconds)</label>
              <input
                type="number"
                value={jobInterval}
                onChange={e => setJobInterval(e.target.value)}
                min="60"
                className="w-full bg-[#242f3d] text-white text-sm rounded-lg px-3 py-2 border border-white/10 focus:border-[#2AABEE] focus:outline-none"
              />
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setShowCreateJob(false)}
                className="flex-1 py-2.5 border border-white/20 text-gray-400 rounded-xl text-sm"
              >Cancel</button>
              <button
                onClick={() => createJobMutation.mutate()}
                disabled={!activeAccount || !jobTarget.trim() || createJobMutation.isPending}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-[#2AABEE] text-white rounded-xl text-sm font-medium disabled:opacity-50"
              >
                {createJobMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                Create
              </button>
            </div>
          </div>
        </div>
      )}

      <AlertDialog open={!!deleteTarget} onOpenChange={() => setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Keyword</AlertDialogTitle>
            <AlertDialogDescription>
              Remove auto-reply for keyword <strong>"{deleteTarget}"</strong>?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteTarget && deleteKeywordMutation.mutate(deleteTarget)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}


