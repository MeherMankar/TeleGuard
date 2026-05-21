import { useEffect, useRef, useState } from "react"
import { ArrowLeft, Loader2, RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"
import { accountsApi } from "@/lib/api"
import { authStore } from "@/store/auth"
import { toast } from "sonner"

interface QRLoginPageProps {
  isOpen: boolean
  onClose: () => void
  onPhoneLogin: () => void
  onSuccess: () => void
}

export function QRLoginPage({ isOpen, onClose, onPhoneLogin, onSuccess }: QRLoginPageProps) {
  const [qrUrl, setQrUrl] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const startQR = async () => {
    setLoading(true)
    setError(null)
    setQrUrl(null)
    try {
      const res = await accountsApi.qrLogin()
      setSessionId(res.session_id)
      setQrUrl(res.url)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  // Poll for QR status
  useEffect(() => {
    if (!sessionId || !isOpen) return

    pollRef.current = setInterval(async () => {
      try {
        const res = await accountsApi.qrStatus(sessionId)
        if (res.status === "success") {
          clearInterval(pollRef.current!)
          toast.success("Account added successfully")
          onSuccess()
        } else if (res.status === "failed") {
          clearInterval(pollRef.current!)
          setError(res.error ?? "QR login failed")
          setSessionId(null)
        }
      } catch {
        // keep polling
      }
    }, 2000)

    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [sessionId, isOpen, onSuccess])

  useEffect(() => {
    if (isOpen) {
      startQR()
    } else {
      if (pollRef.current) clearInterval(pollRef.current)
      setQrUrl(null)
      setSessionId(null)
      setError(null)
    }
  }, [isOpen])

  return (
    <div
      style={{ zIndex: 80 }}
      className={cn(
        "fixed inset-0 bg-background flex flex-col transition-transform duration-300 ease-in-out",
        isOpen ? "translate-x-0" : "translate-x-full",
      )}
    >
      <div className="flex items-center justify-between px-4 py-3">
        <button
          onClick={onClose}
          className="p-2 text-muted-foreground hover:text-foreground transition-colors"
          aria-label="Go back"
        >
          <ArrowLeft className="h-6 w-6" />
        </button>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center px-6 pb-20">
        {/* QR Code display */}
        <div className="relative w-52 h-52 bg-white rounded-xl flex items-center justify-center mb-8 shadow-lg">
          {loading && (
            <Loader2 className="h-10 w-10 text-sky-500 animate-spin" />
          )}
          {!loading && qrUrl && (
            <img
              src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(qrUrl)}`}
              alt="QR Code"
              className="w-44 h-44 rounded"
            />
          )}
          {!loading && error && (
            <div className="flex flex-col items-center gap-2 p-4 text-center">
              <p className="text-destructive text-sm">{error}</p>
              <button
                onClick={startQR}
                className="flex items-center gap-1 text-primary text-sm"
              >
                <RefreshCw className="h-4 w-4" /> Retry
              </button>
            </div>
          )}
        </div>

        <h2 className="text-xl font-semibold text-foreground mb-6 text-center">
          Scan From Mobile Telegram
        </h2>

        <ol className="text-sm text-muted-foreground space-y-2 mb-10 text-left">
          <li>
            <span className="text-foreground font-medium">1.</span> Open Telegram on your phone
          </li>
          <li>
            <span className="text-foreground font-medium">2.</span> Go to Settings {">"} Devices{" "}
            {">"} Link Desktop Device
          </li>
          <li>
            <span className="text-foreground font-medium">3.</span> Scan this image to Log In
          </li>
        </ol>

        <button
          onClick={onPhoneLogin}
          className="text-primary hover:text-primary/80 transition-colors text-sm font-medium"
        >
          Log in using phone number
        </button>
      </div>

      <div className="py-4 text-center">
        <p className="text-xs text-muted-foreground">TeleGuard v1.0</p>
      </div>
    </div>
  )
}
