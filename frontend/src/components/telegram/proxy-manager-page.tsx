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
  const [testingProxyId, setTestingProxyId] = useState<string | null>(null)
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
    setTestingProxyId(proxy.id)
    try {
      const res = await proxiesApi.test(proxy.id)
      setTestResults((prev) => ({
        ...prev,
        [proxy.id]: { status: res.status, latency: res.latency },
      }))
      toast.success(`${res.status === "working" ? "✓" : "✗"} ${res.message}`)
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setTestingProxyId(null)
    }
  }

  return (
    // z-index 75 — above sidebar (50) and its backdrop (40), above other panels (70)
    <div
      style={{ zIndex: 75 }}
      className={cn(
        "tg-screen fixed inset-0 flex flex-col bg-[#17212b] text-white transition-transform duration-300 ease-in-out",
        isOpen ? "translate-x-0" : "translate-x-full",
      )}
    >
      <header className="border-b border-white/[0.08]">
        <div className="mx-auto flex w-full max-w-3xl items-center gap-3 px-4 py-3">
          <button
            onClick={() => {
              setWebshareApiKey("")
              setShowWebshareForm(false)
              onClose()
            }}
            className="-ml-2 rounded-full p-2 text-gray-400 transition-colors hover:bg-white/[0.06] hover:text-white"
            aria-label="Go back"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div className="min-w-0 flex-1">
            <h1 className="text-[17px] font-semibold tracking-tight">Proxy settings</h1>
            <p className="mt-0.5 text-xs text-gray-400">Manage how your accounts connect</p>
          </div>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto">
        <main className="mx-auto w-full max-w-3xl space-y-7 px-4 py-5 pb-10 sm:px-6">
          <section aria-label="Add a proxy">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-[13px] font-semibold text-white">Add proxy</h2>
              <span className="text-xs text-gray-500">Choose a setup method</span>
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              <button
                onClick={() => {
                  setShowAddForm((value) => !value)
                  setShowLinkForm(false)
                  setShowWebshareForm(false)
                }}
                aria-expanded={showAddForm}
                className="flex items-center gap-3 rounded-lg border border-white/[0.08] bg-[#1d2935] px-3 py-3 text-left transition-colors hover:border-white/15 hover:bg-[#222f3d]"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#2AABEE]/15 text-[#55b8ee]">
                  <Plus className="h-[18px] w-[18px]" />
                </span>
                <span>
                  <span className="block text-[13px] font-medium">Enter details</span>
                  <span className="mt-0.5 block text-[11px] text-gray-400">SOCKS, HTTP, MTProto</span>
                </span>
              </button>
              <button
                onClick={() => {
                  setShowLinkForm((value) => !value)
                  setShowAddForm(false)
                  setShowWebshareForm(false)
                }}
                aria-expanded={showLinkForm}
                className="flex items-center gap-3 rounded-lg border border-white/[0.08] bg-[#1d2935] px-3 py-3 text-left transition-colors hover:border-white/15 hover:bg-[#222f3d]"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#2AABEE]/15 text-[#55b8ee]">
                  <Link2 className="h-[18px] w-[18px]" />
                </span>
                <span>
                  <span className="block text-[13px] font-medium">Paste a link</span>
                  <span className="mt-0.5 block text-[11px] text-gray-400">Telegram proxy link</span>
                </span>
              </button>
              <button
                onClick={() => {
                  setShowWebshareForm((value) => !value)
                  setShowAddForm(false)
                  setShowLinkForm(false)
                }}
                aria-expanded={showWebshareForm}
                className="flex items-center gap-3 rounded-lg border border-white/[0.08] bg-[#1d2935] px-3 py-3 text-left transition-colors hover:border-white/15 hover:bg-[#222f3d]"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#2AABEE]/15 text-[#55b8ee]">
                  <Globe className="h-[18px] w-[18px]" />
                </span>
                <span>
                  <span className="block text-[13px] font-medium">Import list</span>
                  <span className="mt-0.5 block text-[11px] text-gray-400">From Webshare</span>
                </span>
              </button>
            </div>
          </section>

        {showLinkForm && (
          <div className="space-y-3 rounded-lg border border-white/[0.08] bg-[#1d2935] p-4">
            <h3 className="text-sm font-semibold">Telegram proxy link</h3>
            <p className="mb-3 mt-1 text-xs leading-relaxed text-gray-400">
              Paste a t.me/proxy, tg://proxy, SOCKS, or MTProto link.
            </p>
            <input
              value={proxyLink}
              onChange={(e) => setProxyLink(e.target.value)}
              placeholder="Telegram proxy link"
              type="url"
              autoComplete="off"
              className="w-full rounded-md border border-white/[0.12] bg-[#17212b] px-3 py-2.5 text-sm text-white outline-none transition-colors placeholder:text-gray-500 focus:border-[#2AABEE]"
            />
            <div className="mt-3 flex justify-end gap-2">
              <button
                onClick={() => {
                  setShowLinkForm(false)
                  setProxyLink("")
                }}
                className="rounded-md px-3 py-2 text-sm text-gray-300 transition-colors hover:bg-white/[0.06]"
              >
                Cancel
              </button>
              <button
                onClick={() => importLinkMutation.mutate()}
                disabled={!proxyLink.trim() || importLinkMutation.isPending}
                className="flex items-center justify-center gap-2 rounded-md bg-[#2AABEE] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#229ed9] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {importLinkMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Add Proxy
              </button>
            </div>
          </div>
        )}

        {showWebshareForm && (
          <div className="rounded-lg border border-white/[0.08] bg-[#1d2935] p-4">
            <h3 className="text-sm font-semibold">Import from Webshare</h3>
            <p className="mb-3 mt-1 text-xs leading-relaxed text-gray-400">
              The API key is used only to fetch your proxy list and is not saved.
            </p>
            <input
              value={webshareApiKey}
              onChange={(e) => setWebshareApiKey(e.target.value)}
              placeholder="Webshare API key"
              type="password"
              autoComplete="off"
              className="w-full rounded-md border border-white/[0.12] bg-[#17212b] px-3 py-2.5 text-sm text-white outline-none transition-colors placeholder:text-gray-500 focus:border-[#2AABEE]"
            />
            <div className="mt-3 flex justify-end gap-2">
              <button
                onClick={() => {
                  setShowWebshareForm(false)
                  setWebshareApiKey("")
                }}
                className="rounded-md px-3 py-2 text-sm text-gray-300 transition-colors hover:bg-white/[0.06]"
              >
                Cancel
              </button>
              <button
                onClick={() => webshareMutation.mutate()}
                disabled={!webshareApiKey.trim() || webshareMutation.isPending}
                className="flex items-center justify-center gap-2 rounded-md bg-[#2AABEE] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#229ed9] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {webshareMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Import Proxies
              </button>
            </div>
          </div>
        )}

        {/* Add Form */}
        {showAddForm && (
          <div className="rounded-lg border border-white/[0.08] bg-[#1d2935] p-4">
            <h3 className="mb-3 text-sm font-semibold">Proxy details</h3>
            <input
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="Name (optional)"
              className="w-full rounded-md border border-white/[0.12] bg-[#17212b] px-3 py-2.5 text-sm text-white outline-none transition-colors placeholder:text-gray-500 focus:border-[#2AABEE]"
            />
            <select
              value={form.type}
              onChange={(e) => setForm((f) => ({ ...f, type: e.target.value }))}
              className="w-full rounded-md border border-white/[0.12] bg-[#17212b] px-3 py-2.5 text-sm text-white outline-none focus:border-[#2AABEE]"
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
                className="min-w-0 flex-1 rounded-md border border-white/[0.12] bg-[#17212b] px-3 py-2.5 text-sm text-white outline-none placeholder:text-gray-500 focus:border-[#2AABEE]"
              />
              <input
                value={form.port}
                onChange={(e) => setForm((f) => ({ ...f, port: e.target.value }))}
                placeholder="Port"
                type="number"
                className="w-24 rounded-md border border-white/[0.12] bg-[#17212b] px-3 py-2.5 text-sm text-white outline-none placeholder:text-gray-500 focus:border-[#2AABEE]"
              />
            </div>
            <input
              value={form.username}
              onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
              placeholder="Username (optional)"
              className="w-full rounded-md border border-white/[0.12] bg-[#17212b] px-3 py-2.5 text-sm text-white outline-none placeholder:text-gray-500 focus:border-[#2AABEE]"
            />
            {form.type === "mtproto" ? (
              <input
                value={form.secret}
                onChange={(e) => setForm((f) => ({ ...f, secret: e.target.value }))}
                placeholder="MTProto secret"
                type="password"
                autoComplete="off"
                className="w-full rounded-md border border-white/[0.12] bg-[#17212b] px-3 py-2.5 text-sm text-white outline-none placeholder:text-gray-500 focus:border-[#2AABEE]"
              />
            ) : (
              <input
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                placeholder="Password (optional)"
                type="password"
                autoComplete="new-password"
                className="w-full rounded-md border border-white/[0.12] bg-[#17212b] px-3 py-2.5 text-sm text-white outline-none placeholder:text-gray-500 focus:border-[#2AABEE]"
              />
            )}
            <div className="mt-3 flex justify-end gap-2">
              <button
                onClick={() => { setShowAddForm(false); setForm({ name: "", type: "socks5", server: "", port: "", username: "", password: "", secret: "" }) }}
                className="rounded-md px-3 py-2 text-sm text-gray-300 transition-colors hover:bg-white/[0.06]"
              >
                Cancel
              </button>
              <button
                onClick={() => addMutation.mutate()}
                disabled={!form.server || !form.port || (form.type === "mtproto" && !form.secret.trim()) || addMutation.isPending}
                className="flex items-center justify-center gap-2 rounded-md bg-[#2AABEE] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#229ed9] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {addMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Add Proxy
              </button>
            </div>
          </div>
        )}

        {/* States */}
        {isLoading && (
          <div className="flex items-center justify-center gap-2 py-10 text-sm text-gray-400">
            <Loader2 className="h-6 w-6 text-[#2AABEE] animate-spin" />
            Loading proxies
          </div>
        )}

        {isError && !isLoading && (
          <div className="rounded-lg border border-red-400/20 bg-red-400/[0.06] px-4 py-4">
            <p className="text-sm font-medium text-red-200">Couldn’t load proxies</p>
            <p className="mt-1 text-xs text-gray-400">Check your connection and try again.</p>
          </div>
        )}

        {!isLoading && !isError && proxies.length === 0 && (
          <div className="border-y border-white/[0.08] py-6">
            <p className="text-sm font-medium">No proxies added</p>
            <p className="mt-1 text-xs text-gray-400">
              Add a proxy above to route one or more accounts through it.
            </p>
          </div>
        )}

        {!isLoading && !isError && proxies.length > 0 && (
          <>
          {accounts.length > 0 && (
            <section>
              <div className="mb-3">
                <h2 className="text-[13px] font-semibold">Account routing</h2>
                <p className="mt-1 text-xs text-gray-400">
                  Choose a specific proxy, or use the default for this account.
                </p>
              </div>
              <ul className="divide-y divide-white/[0.07] border-y border-white/[0.07]">
                {accounts.map((account) => (
                  <li key={account.id} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between">
                    <span className="min-w-0 truncate text-sm font-medium">{account.name}</span>
                    <select
                      id={`proxy-${account.id}`}
                      value={account.proxy_id ?? ""}
                      aria-label={`Proxy for ${account.name}`}
                      onChange={(event) => {
                        if (event.target.value) {
                          assignProxyMutation.mutate({ accountId: account.id, proxyId: event.target.value })
                        } else if (account.proxy_id) {
                          removeProxyMutation.mutate(account.id)
                        }
                      }}
                      disabled={assignProxyMutation.isPending || removeProxyMutation.isPending}
                      className="w-full rounded-md border border-white/[0.12] bg-[#1d2935] px-3 py-2 text-sm text-white outline-none focus:border-[#2AABEE] disabled:opacity-50 sm:w-64"
                    >
                      <option value="">{defaultProxyId ? "Use default proxy" : "No proxy"}</option>
                      {proxies.map((proxy) => (
                        <option key={proxy.id} value={proxy.id}>
                          {proxy.name ?? `${proxy.type.toUpperCase()} · ${proxy.server}:${proxy.port}`}
                        </option>
                      ))}
                    </select>
                  </li>
                ))}
              </ul>
            </section>
          )}
          <section>
            <div className="mb-3 flex items-end justify-between gap-3">
              <div>
                <h2 className="text-[13px] font-semibold">Saved proxies</h2>
                <p className="mt-1 text-xs text-gray-400">
                  {proxies.length} {proxies.length === 1 ? "proxy" : "proxies"}
                  {defaultProxyId ? " · Default selected" : ""}
                </p>
              </div>
            </div>
            <ul role="list" className="divide-y divide-white/[0.07] border-y border-white/[0.07]">
              {proxies.map((proxy, i) => {
                const result = testResults[proxy.id]
                const isDeleteConfirm = deleteTarget === proxy.id
                return (
                  <li key={proxy.id} className={cn("py-3", i < proxies.length - 1 && "border-b border-white/[0.07]")}>
                    {/* Normal row */}
                    {!isDeleteConfirm && (
                      <div className="flex items-center gap-3">
                        <div className={cn(
                          "flex h-9 w-9 shrink-0 items-center justify-center rounded-full",
                          result?.status === "working"
                            ? "bg-emerald-400/10 text-emerald-300"
                            : result?.status === "failed"
                              ? "bg-red-400/10 text-red-300"
                              : "bg-white/[0.06] text-gray-300",
                        )}>
                          {result?.status === "working" ? (
                            <CheckCircle2 className="h-[18px] w-[18px]" />
                          ) : result?.status === "failed" ? (
                            <XCircle className="h-[18px] w-[18px]" />
                          ) : (
                            <Wifi className="h-[18px] w-[18px]" />
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
                          <p className="mt-0.5 truncate text-xs text-gray-400">
                            {proxy.server}:{proxy.port}
                            {result?.latency != null && (
                              <span className="ml-2 text-emerald-300">{result.latency} ms</span>
                            )}
                          </p>
                        </div>
                        <div className="flex items-center gap-1 flex-shrink-0">
                          {defaultProxyId !== proxy.id && (
                            <button
                              onClick={() => setDefaultMutation.mutate(proxy.id)}
                              disabled={setDefaultMutation.isPending}
                              className="rounded-full p-2 text-gray-400 transition-colors hover:bg-white/[0.06] hover:text-amber-200 disabled:opacity-50"
                              title="Set as default proxy"
                              aria-label={`Set ${proxy.name ?? proxy.type} as default proxy`}
                            >
                              <Star className="h-4 w-4" />
                            </button>
                          )}
                          <button
                            onClick={() => testProxy(proxy)}
                            disabled={testingProxyId === proxy.id}
                            className="flex items-center gap-1.5 rounded-md px-2.5 py-2 text-xs text-gray-300 transition-colors hover:bg-white/[0.06] hover:text-white disabled:opacity-50"
                            title="Test proxy"
                          >
                            {testingProxyId === proxy.id
                              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              : <WifiOff className="h-3.5 w-3.5" />}
                            <span className="hidden sm:inline">Test</span>
                          </button>
                          <button
                            onClick={() => setDeleteTarget(proxy.id)}
                            className="rounded-full p-2 text-gray-500 transition-colors hover:bg-red-400/10 hover:text-red-300"
                            title="Delete proxy"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Inline delete confirmation — no portal, stays inside panel */}
                    {isDeleteConfirm && (
                      <div className="flex items-center gap-3 rounded-md border border-red-400/20 bg-red-400/[0.06] px-3 py-2">
                        <AlertTriangle className="h-4 w-4 text-red-400 flex-shrink-0" />
                        <p className="text-red-300 text-xs flex-1">Delete this proxy?</p>
                        <button
                          onClick={() => setDeleteTarget(null)}
                          className="rounded px-2 py-1 text-xs text-gray-300 hover:bg-white/[0.06]"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={() => deleteMutation.mutate(proxy.id)}
                          disabled={deleteMutation.isPending}
                          className="flex items-center gap-1 rounded bg-red-500 px-2 py-1 text-xs text-white"
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
          </section>
          </>
        )}
        </main>
      </div>
    </div>
  )
}
