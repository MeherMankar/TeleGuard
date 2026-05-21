import { useState } from "react"
import {
  ArrowLeft,
  Plus,
  Trash2,
  Loader2,
  Wifi,
  WifiOff,
  CheckCircle2,
  XCircle,
  Globe,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { proxiesApi, type Proxy } from "@/lib/api"
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

interface ProxyManagerPageProps {
  isOpen: boolean
  onClose: () => void
}

export function ProxyManagerPage({ isOpen, onClose }: ProxyManagerPageProps) {
  const queryClient = useQueryClient()
  const [showAddForm, setShowAddForm] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)
  const [testResults, setTestResults] = useState<Record<string, { status: string; latency: number }>>({})
  const [form, setForm] = useState({
    name: "",
    type: "socks5",
    server: "",
    port: "",
    username: "",
    password: "",
  })

  const { data: proxies = [], isLoading } = useQuery({
    queryKey: ["proxies"],
    queryFn: proxiesApi.list,
    enabled: isOpen,
  })

  const addMutation = useMutation({
    mutationFn: () =>
      proxiesApi.add({
        name: form.name || undefined,
        type: form.type,
        server: form.server,
        port: parseInt(form.port),
        username: form.username || undefined,
        password: form.password || undefined,
      }),
    onSuccess: () => {
      toast.success("Proxy added")
      setShowAddForm(false)
      setForm({ name: "", type: "socks5", server: "", port: "", username: "", password: "" })
      queryClient.invalidateQueries({ queryKey: ["proxies"] })
    },
    onError: (e) => toast.error((e as Error).message),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => proxiesApi.delete(id),
    onSuccess: () => {
      toast.success("Proxy deleted")
      setDeleteTarget(null)
      queryClient.invalidateQueries({ queryKey: ["proxies"] })
    },
    onError: (e) => toast.error((e as Error).message),
  })

  const testProxy = async (proxy: Proxy) => {
    try {
      const res = await proxiesApi.test(proxy.id)
      setTestResults((prev) => ({
        ...prev,
        [proxy.id]: { status: res.status, latency: res.latency },
      }))
      toast.success(`${res.status === "working" ? "✓" : "✗"} ${res.message}`)
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  return (
    <>
      <div
        style={{ zIndex: 70 }}
        className={cn(
          "fixed top-0 right-0 h-screen w-full max-w-md bg-[#17212b] flex flex-col transition-transform duration-300 ease-in-out",
          isOpen ? "translate-x-0" : "translate-x-full",
        )}
      >
        <header className="flex items-center gap-4 px-4 py-3 bg-[#17212b] border-b border-white/10">
          <button
            onClick={onClose}
            className="p-2 -ml-2 text-gray-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="h-6 w-6" />
          </button>
          <h1 className="text-xl font-medium text-white flex-1">Proxy Manager</h1>
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="p-2 text-[#2AABEE] hover:text-white transition-colors"
          >
            <Plus className="h-5 w-5" />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Add Form */}
          {showAddForm && (
            <div className="bg-[#242f3d] rounded-xl p-4 space-y-3">
              <p className="text-sky-400 text-sm font-medium">Add New Proxy</p>
              <input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Name (optional)"
                className="w-full bg-[#17212b] text-white text-sm rounded-lg px-3 py-2 border border-white/10 focus:border-[#2AABEE] focus:outline-none"
              />
              <select
                value={form.type}
                onChange={(e) => setForm((f) => ({ ...f, type: e.target.value }))}
                className="w-full bg-[#17212b] text-white text-sm rounded-lg px-3 py-2 border border-white/10 focus:border-[#2AABEE] focus:outline-none"
              >
                <option value="socks5">SOCKS5</option>
                <option value="http">HTTP</option>
                <option value="mtproto">MTProto</option>
              </select>
              <div className="flex gap-2">
                <input
                  value={form.server}
                  onChange={(e) => setForm((f) => ({ ...f, server: e.target.value }))}
                  placeholder="Server"
                  className="flex-1 bg-[#17212b] text-white text-sm rounded-lg px-3 py-2 border border-white/10 focus:border-[#2AABEE] focus:outline-none"
                />
                <input
                  value={form.port}
                  onChange={(e) => setForm((f) => ({ ...f, port: e.target.value }))}
                  placeholder="Port"
                  type="number"
                  className="w-24 bg-[#17212b] text-white text-sm rounded-lg px-3 py-2 border border-white/10 focus:border-[#2AABEE] focus:outline-none"
                />
              </div>
              <input
                value={form.username}
                onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
                placeholder="Username (optional)"
                className="w-full bg-[#17212b] text-white text-sm rounded-lg px-3 py-2 border border-white/10 focus:border-[#2AABEE] focus:outline-none"
              />
              <input
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                placeholder="Password (optional)"
                type="password"
                className="w-full bg-[#17212b] text-white text-sm rounded-lg px-3 py-2 border border-white/10 focus:border-[#2AABEE] focus:outline-none"
              />
              <button
                onClick={() => addMutation.mutate()}
                disabled={!form.server || !form.port || addMutation.isPending}
                className="w-full py-2 bg-[#2AABEE] text-white rounded-lg text-sm font-medium disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {addMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Add Proxy
              </button>
            </div>
          )}

          {isLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-6 w-6 text-[#2AABEE] animate-spin" />
            </div>
          ) : proxies.length === 0 ? (
            <div className="text-center py-12">
              <Globe className="h-12 w-12 text-gray-600 mx-auto mb-3" />
              <p className="text-gray-400 text-sm">No proxies configured</p>
              <button
                onClick={() => setShowAddForm(true)}
                className="mt-3 text-[#2AABEE] text-sm"
              >
                Add your first proxy
              </button>
            </div>
          ) : (
            <div className="bg-[#242f3d] rounded-xl overflow-hidden">
              <div className="px-4 py-3 border-b border-white/10">
                <span className="text-sky-400 text-sm font-medium">
                  Proxies ({proxies.length})
                </span>
              </div>
              <ul role="list">
                {proxies.map((proxy, i) => {
                  const result = testResults[proxy.id]
                  return (
                    <li
                      key={proxy.id}
                      className={cn(
                        "px-4 py-3",
                        i < proxies.length - 1 && "border-b border-white/5",
                      )}
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-[#2AABEE]/20 flex items-center justify-center flex-shrink-0">
                          {result?.status === "working" ? (
                            <CheckCircle2 className="h-4 w-4 text-green-400" />
                          ) : result?.status === "failed" ? (
                            <XCircle className="h-4 w-4 text-red-400" />
                          ) : (
                            <Wifi className="h-4 w-4 text-[#2AABEE]" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-white text-sm font-medium truncate">
                            {proxy.name ?? `${proxy.type.toUpperCase()} Proxy`}
                          </p>
                          <p className="text-gray-400 text-xs">
                            {proxy.server}:{proxy.port}
                            {result?.latency != null && (
                              <span className="ml-2 text-green-400">{result.latency}ms</span>
                            )}
                          </p>
                        </div>
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => testProxy(proxy)}
                            className="p-1.5 text-[#2AABEE] hover:text-white transition-colors text-xs"
                            title="Test proxy"
                          >
                            <WifiOff className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => setDeleteTarget(proxy.id)}
                            className="p-1.5 text-red-400 hover:text-red-300 transition-colors"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                    </li>
                  )
                })}
              </ul>
            </div>
          )}
        </div>
      </div>

      <AlertDialog open={!!deleteTarget} onOpenChange={() => setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Proxy</AlertDialogTitle>
            <AlertDialogDescription>
              Remove this proxy configuration? This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget)}
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
