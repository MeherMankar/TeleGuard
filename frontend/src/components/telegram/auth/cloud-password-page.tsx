import { useState } from "react"
import { Eye, EyeOff, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { accountsApi } from "@/lib/api"
import { toast } from "sonner"

interface CloudPasswordPageProps {
  isOpen: boolean
  sessionId: string
  onSuccess: () => void
  /** "phone" = after phone+OTP, "qr" = after QR scan with 2FA */
  mode?: "phone" | "qr"
}

export function CloudPasswordPage({
  isOpen,
  sessionId,
  onSuccess,
  mode = "phone",
}: CloudPasswordPageProps) {
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async () => {
    if (!password || loading) return
    setLoading(true)
    try {
      if (mode === "qr") {
        await accountsApi.qrPassword(sessionId, password)
      } else {
        await accountsApi.verifyPassword(sessionId, password)
      }
      toast.success("Account added successfully")
      onSuccess()
    } catch (e) {
      toast.error((e as Error).message)
      setPassword("")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{ zIndex: 80 }}
      className={cn(
        "fixed inset-0 bg-background flex flex-col transition-transform duration-300 ease-in-out",
        isOpen ? "translate-x-0" : "translate-x-full",
      )}
    >
      <div className="flex-1 flex flex-col justify-center px-6 max-w-md mx-auto w-full">
        <h1 className="text-2xl font-semibold text-foreground mb-3">
          Two-step verification
        </h1>
        <p className="text-muted-foreground text-sm mb-8">
          {mode === "qr"
            ? "Your account has two-step verification enabled. Please enter your cloud password to continue."
            : "Please enter your cloud password."}
        </p>

        <div className="mb-6">
          <label className="text-primary text-sm font-medium mb-2 block">
            Password
          </label>
          <div className="relative">
            <input
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
              className="w-full bg-transparent text-foreground border-b-2 border-primary pb-2 focus:outline-none pr-10"
              autoFocus
              placeholder="Enter your 2FA password"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-0 bottom-2 text-muted-foreground hover:text-foreground transition-colors"
            >
              {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
            </button>
          </div>
        </div>

        <button
          onClick={handleSubmit}
          disabled={password.length === 0 || loading}
          className={cn(
            "w-full py-4 rounded-xl font-medium text-base transition-all flex items-center justify-center gap-2",
            password.length > 0 && !loading
              ? "bg-primary text-primary-foreground hover:bg-primary/90"
              : "bg-primary/50 text-primary-foreground/70 cursor-not-allowed",
          )}
        >
          {loading && <Loader2 className="h-4 w-4 animate-spin" />}
          {loading ? "Verifying..." : "Submit"}
        </button>
      </div>
    </div>
  )
}
