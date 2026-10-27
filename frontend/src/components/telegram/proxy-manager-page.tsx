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
  AlertTriangle,
  X,
  Link2,
  Star,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { accountsApi, proxiesApi, type Proxy } from "@/lib/api"
import { toast } from "sonner"

interface ProxyManagerPageProps {
  isOpen: boolean
  onClose: () => void
}

function parseProxyLink(link: string) {
  const value = link.trim()
  let type: string
  let server: string
  let port: number
  let secret: string | undefined
  let username: string | undefined
  let password: string | undefined

  if (value.toLowerCase().startsWith("mtproto://")) {
    const [authority, query = ""] = value.slice("mtproto://".length).split("?")
    const parts = authority.split(":")
    if (parts.length === 3) {
      server = parts[0]
      port = Number(parts[1])
      secret = parts[2]
    } else if (parts.length === 2) {
      server = parts[0]
      port = Number(parts[1])
      secret = new URLSearchParams(query).get("secret") ?? undefined
    } else {
      throw new Error("Use an MTProto link in host:port:secret format")
    }
    type = "mtproto"
  } else {
    const normalized = /^t\.me\//i.test(value) ? `https://${value}` : value
    const parsed = new URL(normalized)
    const route = parsed.pathname.toLowerCase().replace(/\/+$/, "").split("/").pop()
    const tgRoute = parsed.protocol === "tg:" ? parsed.hostname : ""
    if (parsed.protocol === "tg:" && !["proxy", "socks"].includes(tgRoute)) {
      throw new Error("Unsupported Telegram proxy link")
    }
    if (route !== "proxy" && route !== "socks" && parsed.protocol !== "tg:") {
      throw new Error("Paste a Telegram proxy or SOCKS link")
    }
    type = route === "socks" || tgRoute === "socks" ? "socks5" : "mtproto"
    server = parsed.searchParams.get("server") ?? ""
    port = Number(parsed.searchParams.get("port") ?? (type === "mtproto" ? "443" : "1080"))
    secret = parsed.searchParams.get("secret") ?? undefined
    username = parsed.searchParams.get("user") ?? undefined
    password = parsed.searchParams.get("pass") ?? undefined
  }

  if (!server || !Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error("The proxy link must include a valid server and port")
  }
  if (type === "mtproto" && !secret) {
    throw new Error("The MTProto link is missing its secret")
  }
  return { type, server, port, secret, username, password }
}

export function ProxyManagerPage({ isOpen, onClose }: ProxyManagerPageProps) {
  const queryClient = useQueryClient()
  const [showAddForm, setShowAddForm] = useState(false)
  const [showWebshareForm, setShowWebshareForm] = useState(false)
  const [showLinkForm, setShowLinkForm] = useState(false)
  const [webshareApiKey, setWebshareApiKey] = useState("")
  const [proxyLink, setProxyLink] = useState("")
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)
  const [testResults, setTestResults] = useState<Record<string, { status: string; latency: number }>>({})
  const [form, setForm] = useState({
    name: "",
    type: "socks5",
    server: "",
    port: "",
    username: "",
    password: "",
    secret: "",
  })

  const { data: proxies = [], isLoading, isError } = useQuery({
    queryKey: ["proxies"],
    queryFn: proxiesApi.list,
    enabled: isOpen,
    retry: 1,
  })

  const { data: accounts = [] } = useQuery({
    queryKey: ["accounts"],
    queryFn: accountsApi.list,
    enabled: isOpen,
  })

  const { data: defaultProxy } = useQuery({
    queryKey: ["proxies", "default"],
    queryFn: proxiesApi.getDefault,
    enabled: isOpen,
  })
  const defaultProxyId = defaultProxy && "id" in defaultProxy ? defaultProxy.id : null

  const addMutation = useMutation({
    mutationFn: () =>
      proxiesApi.add({
        name: form.name || undefined,
        type: form.type,
        server: form.server,
        port: parseInt(form.port),
        username: form.username || undefined,
        password: form.password || undefined,
        secret: form.type === "mtproto" ? form.secret.trim() || undefined : undefined,
      }),
    onSuccess: () => {
      toast.success("Proxy added")
      setShowAddForm(false)
      setForm({ name: "", type: "socks5", server: "", port: "", username: "", password: "", secret: "" })
      queryClient.invalidateQueries({ queryKey: ["proxies"] })
    },
    onError: (e) => toast.error((e as Error).message),
  })

  const webshareMutation = useMutation({
    mutationFn: () => proxiesApi.importWebshare(webshareApiKey),
    onSuccess: (result) => {
      toast.success(
        `Imported ${result.imported} Webshare proxies; skipped ${result.skipped}, failed ${result.failed}`,
      )
      setWebshareApiKey("")
      setShowWebshareForm(false)
      queryClient.invalidateQueries({ queryKey: ["proxies"] })
    },
    onError: (e) => toast.error((e as Error).message),
  })

  const importLinkMutation = useMutation({
    mutationFn: () => proxiesApi.add(parseProxyLink(proxyLink)),
    onSuccess: () => {
      toast.success("Telegram proxy added")
      setProxyLink("")
      setShowLinkForm(false)
      queryClient.invalidateQueries({ queryKey: ["proxies"] })
    },
    onError: (e) => toast.error((e as Error).message),
  })

  const setDefaultMutation = useMutation({
    mutationFn: (proxyId: string) => proxiesApi.setDefault(proxyId),
    onSuccess: () => {
      toast.success("Default proxy updated")
      queryClient.invalidateQueries({ queryKey: ["proxies", "default"] })
    },
    onError: (e) => toast.error((e as Error).message),
  })

  const assignProxyMutation = useMutation({
    mutationFn: ({ accountId, proxyId }: { accountId: string; proxyId: string }) =>
      proxiesApi.assign(accountId, proxyId),
    onSuccess: (_, variables) => {
      toast.success("Proxy assigned to account")
      queryClient.setQueryData(
        ["accounts"],
        (current: typeof accounts | undefined) =>
          current?.map((account) =>
            account.id === variables.accountId
              ? { ...account, proxy_id: variables.proxyId }
              : account,
          ),
      )
    },
    onError: (e) => toast.error((e as Error).message),
  })

  const removeProxyMutation = useMutation({
    mutationFn: (accountId: string) => proxiesApi.remove(accountId),
    onSuccess: (_, accountId) => {
      toast.success("Proxy removed from account")
      queryClient.setQueryData(
        ["accounts"],
        (current: typeof accounts | undefined) =>
          current?.map((account) =>
            account.id === accountId ? { ...account, proxy_id: undefined } : account,
          ),
      )
    },
    onError: (e) => toast.error((e as Error).message),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => proxiesApi.delete(id),
    onSuccess: () => {
      toast.success("Proxy deleted")
      setDeleteTarget(null)
      queryClient.invalidateQueries({ queryKey: ["proxies"] })
      queryClient.invalidateQueries({ queryKey: ["accounts"] })
    },
    onError: (e) => {
      toast.error((e as Error).message)
      setDeleteTarget(null)
    },
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
    // z-index 75 — above sidebar (50) and its backdrop (40), above other panels (70)
    <div
      style={{ zIndex: 75 }}
      className={cn(
        "fixed inset-0 bg-[#17212b] flex flex-col transition-transform duration-300 ease-in-out",
        isOpen ? "translate-x-0" : "translate-x-full",
      )}
    >
      <header className="flex items-center gap-4 px-4 py-3 border-b border-white/10">
        <button
          onClick={() => {
            setWebshareApiKey("")
            setShowWebshareForm(false)
            onClose()
          }}
          className="p-2 -ml-2 text-gray-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="h-6 w-6" />
        </button>
        <h1 className="text-xl font-medium text-white flex-1">Proxy Manager</h1>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="p-2 text-[#2AABEE] hover:text-white transition-colors"
          title="Add a proxy manually"
        >
          <Plus className="h-5 w-5" />
        </button>
        <button
          onClick={() => setShowLinkForm(!showLinkForm)}
          className="p-2 text-[#2AABEE] hover:text-white transition-colors"
          title="Add a Telegram proxy link"
          aria-label="Add a Telegram proxy link"
        >
          <Link2 className="h-5 w-5" />
        </button>
        <button
          onClick={() => {
            if (showWebshareForm) setWebshareApiKey("")
            setShowWebshareForm(!showWebshareForm)
          }}
          className="p-2 text-[#2AABEE] hover:text-white transition-colors"
          title="Import Webshare proxies"
        >
          <Globe className="h-5 w-5" />
        </button>
      </header>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {showLinkForm && (
          <div className="bg-[#242f3d] rounded-xl p-4 space-y-3">
            <p className="text-sky-400 text-sm font-medium">Add Telegram proxy link</p>
            <p className="text-gray-400 text-xs">
              Paste a t.me/proxy, tg://proxy, SOCKS, or MTProto link.
            </p>
            <input
              value={proxyLink}
              onChange={(e) => setProxyLink(e.target.value)}
              placeholder="Telegram proxy link"
              type="url"
              autoComplete="off"
              className="w-full bg-[#17212b] text-white text-sm rounded-lg px-3 py-2 border border-white/10 focus:border-[#2AABEE] focus:outline-none"
            />
            <div className="flex gap-2">
              <button
                onClick={() => {
                  setShowLinkForm(false)
                  setProxyLink("")
                }}
                className="flex-1 py-2 border border-white/20 text-gray-300 rounded-lg text-sm"
              >
                Cancel
              </button>
              <button
                onClick={() => importLinkMutation.mutate()}
                disabled={!proxyLink.trim() || importLinkMutation.isPending}
                className="flex-1 py-2 bg-[#2AABEE] text-white rounded-lg text-sm font-medium disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {importLinkMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Add Proxy
              </button>
            </div>
          </div>
        )}

        {showWebshareForm && (
          <div className="bg-[#242f3d] rounded-xl p-4 space-y-3">
            <p className="text-sky-400 text-sm font-medium">Import from Webshare</p>
            <p className="text-gray-400 text-xs">
              The API key is used only to fetch your proxy list and is not saved.
            </p>
            <input
              value={webshareApiKey}
              onChange={(e) => setWebshareApiKey(e.target.value)}
              placeholder="Webshare API key"
              type="password"
              autoComplete="off"
              className="w-full bg-[#17212b] text-white text-sm rounded-lg px-3 py-2 border border-white/10 focus:border-[#2AABEE] focus:outline-none"
            />
            <div className="flex gap-2">
              <button
                onClick={() => {
                  setShowWebshareForm(false)
                  setWebshareApiKey("")
                }}
                className="flex-1 py-2 border border-white/20 text-gray-300 rounded-lg text-sm"
              >
                Cancel
              </button>
              <button
                onClick={() => webshareMutation.mutate()}
                disabled={!webshareApiKey.trim() || webshareMutation.isPending}
                className="flex-1 py-2 bg-[#2AABEE] text-white rounded-lg text-sm font-medium disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {webshareMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Import Proxies
              </button>
            </div>
          </div>
        )}

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
                placeholder="Server / Host"
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
            {form.type === "mtproto" ? (
              <input
                value={form.secret}
                onChange={(e) => setForm((f) => ({ ...f, secret: e.target.value }))}
                placeholder="MTProto secret"
                type="password"
                autoComplete="off"
                className="w-full bg-[#17212b] text-white text-sm rounded-lg px-3 py-2 border border-white/10 focus:border-[#2AABEE] focus:outline-none"
              />
            ) : (
              <input
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                placeholder="Password (optional)"
                type="password"
                autoComplete="new-password"
                className="w-full bg-[#17212b] text-white text-sm rounded-lg px-3 py-2 border border-white/10 focus:border-[#2AABEE] focus:outline-none"
              />
            )}
            <div className="flex gap-2">
              <button
                onClick={() => { setShowAddForm(false); setForm({ name: "", type: "socks5", server: "", port: "", username: "", password: "", secret: "" }) }}
                className="flex-1 py-2 border border-white/20 text-gray-300 rounded-lg text-sm"
              >
                Cancel
              </button>
              <button
                onClick={() => addMutation.mutate()}
                disabled={!form.server || !form.port || (form.type === "mtproto" && !form.secret.trim()) || addMutation.isPending}
                className="flex-1 py-2 bg-[#2AABEE] text-white rounded-lg text-sm font-medium disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {addMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Add Proxy
              </button>
            </div>
          </div>
        )}

        {/* States */}
        {isLoading && (
          <div className="flex justify-center py-8">
            <Loader2 className="h-6 w-6 text-[#2AABEE] animate-spin" />
          </div>
        )}

        {isError && !isLoading && (
          <div className="text-center py-12">
            <Globe className="h-12 w-12 text-gray-600 mx-auto mb-3" />
            <p className="text-gray-400 text-sm">Could not load proxies</p>
            <p className="text-gray-600 text-xs mt-1">Check your backend connection</p>
            <button onClick={() => setShowAddForm(true)} className="mt-3 text-[#2AABEE] text-sm">
              Add a proxy anyway
            </button>
          </div>
        )}

        {!isLoading && !isError && proxies.length === 0 && (
          <div className="text-center py-12">
            <Globe className="h-12 w-12 text-gray-600 mx-auto mb-3" />
            <p className="text-gray-400 text-sm">No proxies configured</p>
            <button onClick={() => setShowAddForm(true)} className="mt-3 text-[#2AABEE] text-sm">
              Add your first proxy
            </button>
          </div>
        )}

        {!isLoading && !isError && proxies.length > 0 && (
          <>
          {accounts.length > 0 && (
            <section className="bg-[#242f3d] rounded-xl overflow-hidden">
              <div className="px-4 py-3 border-b border-white/10">
                <span className="text-sky-400 text-sm font-medium">Account routing</span>
              </div>
              <ul>
                {accounts.map((account) => (
                  <li key={account.id} className="px-4 py-3 border-b border-white/5 last:border-0">
                    <label className="block text-white text-sm mb-2" htmlFor={`proxy-${account.id}`}>
                      {account.name}
                    </label>
                    <select
                      id={`proxy-${account.id}`}
                      value={account.proxy_id ?? ""}
                      onChange={(event) => {
                        if (event.target.value) {
                          assignProxyMutation.mutate({
                            accountId: account.id,
                            proxyId: event.target.value,
                          })
                        } else if (account.proxy_id) {
                          removeProxyMutation.mutate(account.id)
                        }
                      }}
                      disabled={assignProxyMutation.isPending || removeProxyMutation.isPending}
                      className="w-full bg-[#17212b] text-white text-sm rounded-lg px-3 py-2 border border-white/10 focus:border-[#2AABEE] focus:outline-none disabled:opacity-50"
                    >
                      <option value="">Use default / no account proxy</option>
                      {proxies.map((proxy) => (
                        <option key={proxy.id} value={proxy.id}>
                          {proxy.name ?? `${proxy.type.toUpperCase()} ${proxy.server}:${proxy.port}`}
                        </option>
                      ))}
                    </select>
                  </li>
                ))}
              </ul>
            </section>
          )}
          <div className="bg-[#242f3d] rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-white/10">
              <span className="text-sky-400 text-sm font-medium">Proxies ({proxies.length})</span>
            </div>
            <ul role="list">
              {proxies.map((proxy, i) => {
                const result = testResults[proxy.id]
                const isDeleteConfirm = deleteTarget === proxy.id
                return (
                  <li key={proxy.id} className={cn("px-4 py-3", i < proxies.length - 1 && "border-b border-white/5")}>
                    {/* Normal row */}
                    {!isDeleteConfirm && (
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
                            {defaultProxyId === proxy.id && (
                              <span className="ml-2 inline-flex items-center gap-1 text-amber-300 text-xs">
                                <Star className="h-3 w-3 fill-current" /> Default
                              </span>
                            )}
                          </p>
                          <p className="text-gray-400 text-xs truncate">
                            {proxy.server}:{proxy.port}
                            {result?.latency != null && (
                              <span className="ml-2 text-green-400">{result.latency}ms</span>
                            )}
                          </p>
                        </div>
                        <div className="flex items-center gap-1 flex-shrink-0">
                          {defaultProxyId !== proxy.id && (
                            <button
                              onClick={() => setDefaultMutation.mutate(proxy.id)}
                              disabled={setDefaultMutation.isPending}
                              className="p-1.5 text-amber-300 hover:text-white transition-colors disabled:opacity-50"
                              title="Set as default proxy"
                              aria-label={`Set ${proxy.name ?? proxy.type} as default proxy`}
                            >
                              <Star className="h-4 w-4" />
                            </button>
                          )}
                          <button
                            onClick={() => testProxy(proxy)}
                            className="p-1.5 text-[#2AABEE] hover:text-white transition-colors"
                            title="Test proxy"
                          >
                            <WifiOff className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => setDeleteTarget(proxy.id)}
                            className="p-1.5 text-red-400 hover:text-red-300 transition-colors"
                            title="Delete proxy"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Inline delete confirmation — no portal, stays inside panel */}
                    {isDeleteConfirm && (
                      <div className="flex items-center gap-3 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
                        <AlertTriangle className="h-4 w-4 text-red-400 flex-shrink-0" />
                        <p className="text-red-300 text-xs flex-1">Delete this proxy?</p>
                        <button
                          onClick={() => setDeleteTarget(null)}
                          className="px-2 py-1 text-gray-400 hover:text-white text-xs border border-white/20 rounded"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={() => deleteMutation.mutate(proxy.id)}
                          disabled={deleteMutation.isPending}
                          className="px-2 py-1 bg-red-500 text-white text-xs rounded flex items-center gap-1"
                        >
                          {deleteMutation.isPending ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            "Delete"
                          )}
                        </button>
                      </div>
                    )}
                  </li>
                )
              })}
            </ul>
          </div>
          </>
        )}
      </div>
    </div>
  )
}
