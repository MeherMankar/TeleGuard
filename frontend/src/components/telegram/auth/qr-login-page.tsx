import { useEffect, useRef, useState } from "react"
import { ArrowLeft, Loader2, RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"
import { accountsApi } from "@/lib/api"
import { toast } from "sonner"

interface QRLoginPageProps {
  isOpen: boolean
  onClose: () => void
  onPhoneLogin: () => void
  onSuccess: () => void
  onRequires2FA: (sessionId: string) => void
}

export function QRLoginPage({ isOpen, onClose, onPhoneLogin, onSuccess, onRequires2FA }: QRLoginPageProps) {
  const [qrUrl, setQrUrl] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [timeLeft, setTimeLeft] = useState(0)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const QR_TTL = 115 // seconds before auto-refresh (QR expires at 120s)

  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null }
  }

  const startQR = async () => {
    stopPolling()
    setLoading(true)
    setError(null)
    setQrUrl(null)
    setSessionId(null)
    setTimeLeft(QR_TTL)

    try {
      const res = await accountsApi.qrLogin()
      setSessionId(res.session_id)
      setQrUrl(res.url)

      // Countdown timer
      timerRef.current = setInterval(() => {
        setTimeLeft((t) => {
          if (t <= 1) {
            // Auto-refresh before expiry
            startQR()
            return 0
          }
          return t - 1
        })
      }, 1000)

      // Poll for scan
      pollRef.current = setInterval(async () => {
        try {
          const status = await accountsApi.qrStatus(res.session_id)
          if (status.status === "success") {
            stopPolling()
            toast.success("Account added successfully")
            onSuccess()
          } else if (status.status === "requires_2fa") {
            // 2FA needed — stop polling, redirect to password screen
            stopPolling()
            onRequires2FA(res.session_id)
          } else if (status.status === "failed") {
            stopPolling()
            if (status.error?.includes("AUTH_TOKEN_EXPIRED")) {
              startQR()
            } else {
              setError(status.error ?? "QR login failed")
            }
          }
        } catch {
          // keep polling
        }
      }, 2000)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (isOpen) {
      startQR()
    } else {
      stopPolling()
      setQrUrl(null)
      setSessionId(null)
      setError(null)
      setTimeLeft(0)
    }
    return stopPolling
  }, [isOpen])

  const qrImageUrl = qrUrl
    ? `https://api.qrserver.com/v1/create-qr-code/?size=220x220&margin=10&data=${encodeURIComponent(qrUrl)}`
    : null

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
        >
          <ArrowLeft className="h-6 w-6" />
        </button>
        <button
          onClick={startQR}
          disabled={loading}
          className="flex items-center gap-1.5 text-primary text-sm font-medium hover:text-primary/80"
        >
          <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
          Refresh
        </button>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center px-6 pb-16">
        {/* QR code display */}
        <div className="relative w-56 h-56 bg-white rounded-2xl flex items-center justify-center mb-6 shadow-lg overflow-hidden">
          {loading && <Loader2 className="h-10 w-10 text-sky-500 animate-spin" />}

          {!loading && qrImageUrl && (
            <img src={qrImageUrl} alt="QR Code" className="w-52 h-52 object-contain" />
          )}

          {!loading && error && (
            <div className="flex flex-col items-center gap-2 p-4 text-center">
              <p className="text-red-500 text-sm">{error}</p>
              <button onClick={startQR} className="flex items-center gap-1 text-sky-500 text-sm">
                <RefreshCw className="h-4 w-4" /> Retry
              </button>
            </div>
          )}

          {/* Countdown ring */}
          {!loading && qrUrl && timeLeft > 0 && (
            <div className="absolute bottom-1.5 right-1.5 bg-black/50 text-white text-[10px] px-1.5 py-0.5 rounded-full">
              {timeLeft}s
            </div>
          )}
        </div>

        <h2 className="text-xl font-semibold text-foreground mb-5 text-center">
          Scan From Mobile Telegram
        </h2>

        <ol className="text-sm text-muted-foreground space-y-2 mb-8 text-left w-full max-w-xs">
          <li><span className="text-foreground font-medium">1.</span> Open Telegram on your phone</li>
          <li><span className="text-foreground font-medium">2.</span> Go to Settings → Devices → Link Desktop Device</li>
          <li><span className="text-foreground font-medium">3.</span> Scan this QR code</li>
        </ol>

        {/* Progress bar */}
        {!loading && qrUrl && (
          <div className="w-full max-w-xs h-1 bg-border/30 rounded-full mb-6 overflow-hidden">
            <div
              className="h-full bg-primary rounded-full transition-all duration-1000"
              style={{ width: `${(timeLeft / QR_TTL) * 100}%` }}
            />
          </div>
        )}

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
