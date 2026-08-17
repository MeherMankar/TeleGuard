import { useState, useRef, useEffect } from "react"
import { Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { accountsApi } from "@/lib/api"
import { toast } from "sonner"

// Telegram sends 5-digit codes normally, but sometimes 6. Support both.
const OTP_MIN = 5
const OTP_MAX = 6

interface OTPPageProps {
  isOpen: boolean
  phoneNumber: string
  sessionId: string
  onSuccess: () => void
  onRequires2FA: () => void
}

export function OTPPage({ isOpen, phoneNumber, sessionId, onSuccess, onRequires2FA }: OTPPageProps) {
  const [otp, setOtp] = useState<string[]>(Array(OTP_MAX).fill(""))
  const [loading, setLoading] = useState(false)
  const inputRefs = useRef<(HTMLInputElement | null)[]>([])

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRefs.current[0]?.focus(), 100)
    } else {
      setOtp(Array(OTP_MAX).fill(""))
    }
  }, [isOpen])

  const handleChange = (index: number, value: string) => {
    // Handle paste of full code
    if (value.length > 1) {
      const digits = value.replace(/\D/g, "").slice(0, OTP_MAX).split("")
      const newOtp = Array(OTP_MAX).fill("")
      digits.forEach((d, i) => { if (i < OTP_MAX) newOtp[i] = d })
      setOtp(newOtp)
      const nextIndex = Math.min(digits.length, OTP_MAX - 1)
      inputRefs.current[nextIndex]?.focus()
      // Auto-submit if we have at least OTP_MIN digits
      if (digits.length >= OTP_MIN) {
        setTimeout(() => submitCode(digits.join("")), 100)
      }
      return
    }

    if (!/^\d*$/.test(value)) return

    const newOtp = [...otp]
    newOtp[index] = value
    setOtp(newOtp)

    // Move to next
    if (value && index < OTP_MAX - 1) {
      inputRefs.current[index + 1]?.focus()
    }

    // Auto-submit when all 6 filled, or after 1s pause at 5 digits
    const filled = newOtp.filter((d) => d !== "")
    if (filled.length === OTP_MAX) {
      setTimeout(() => submitCode(newOtp.join("")), 100)
    } else if (filled.length === OTP_MIN) {
      // Wait briefly in case a 6th digit is coming
      setTimeout(() => {
        const current = newOtp.filter((d) => d !== "")
        if (current.length === OTP_MIN) submitCode(current.join(""))
      }, 800)
    }
  }

  const handleKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === "Backspace" && !otp[index] && index > 0) {
      inputRefs.current[index - 1]?.focus()
    }
  }

  const isComplete = otp.filter((d) => d !== "").length >= OTP_MIN

  const submitCode = async (code: string) => {
    if (loading) return
    setLoading(true)
    try {
      const res = await accountsApi.verifyCode(sessionId, code)
      if (res.status === "success") {
        toast.success("Account added successfully")
        onSuccess()
      } else if (res.status === "requires_2fa") {
        onRequires2FA()
      }
    } catch (e) {
      toast.error((e as Error).message)
      setOtp(Array(OTP_LENGTH).fill(""))
      inputRefs.current[0]?.focus()
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = () => {
    if (!isComplete || loading) return
    submitCode(otp.join(""))
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
        <h1 className="text-xl font-semibold text-foreground mb-3">{phoneNumber}</h1>
        <p className="text-muted-foreground text-sm mb-10 leading-relaxed">
          Enter the code sent <span className="text-foreground font-medium">via Telegram</span> to
          your other devices.
        </p>

        {/* OTP boxes — 5 digits */}
        <div className="flex gap-3 mb-6 justify-center">
          {otp.map((digit, index) => (
            <input
              key={index}
              ref={(el) => { inputRefs.current[index] = el }}
              type="text"
              inputMode="numeric"
              maxLength={1}
              value={digit}
              onChange={(e) => handleChange(index, e.target.value)}
              onKeyDown={(e) => handleKeyDown(index, e)}
              className={cn(
                "w-12 h-14 text-center text-xl font-bold rounded-xl border-2 bg-transparent text-foreground transition-all focus:outline-none",
                digit ? "border-primary bg-primary/10" : "border-border/50",
                loading && "opacity-50",
              )}
            />
          ))}
        </div>

        <p className="text-muted-foreground text-xs text-center mb-8">
          Code auto-submits when complete
        </p>

        <button
          onClick={handleSubmit}
          disabled={!isComplete || loading}
          className={cn(
            "w-full py-4 rounded-xl font-medium text-base transition-all flex items-center justify-center gap-2",
            isComplete && !loading
              ? "bg-primary text-primary-foreground hover:bg-primary/90"
              : "bg-primary/40 text-primary-foreground/60 cursor-not-allowed",
          )}
        >
          {loading && <Loader2 className="h-4 w-4 animate-spin" />}
          {loading ? "Verifying..." : "Next"}
        </button>
      </div>
    </div>
  )
}
