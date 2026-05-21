import { useState, useRef, useEffect } from "react"
import { Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { accountsApi } from "@/lib/api"
import { toast } from "sonner"

interface OTPPageProps {
  isOpen: boolean
  phoneNumber: string
  sessionId: string
  onSuccess: () => void
  onRequires2FA: () => void
}

export function OTPPage({ isOpen, phoneNumber, sessionId, onSuccess, onRequires2FA }: OTPPageProps) {
  const [otp, setOtp] = useState(["", "", "", "", "", ""])
  const [loading, setLoading] = useState(false)
  const inputRefs = useRef<(HTMLInputElement | null)[]>([])

  useEffect(() => {
    if (isOpen && inputRefs.current[0]) {
      inputRefs.current[0].focus()
    }
    if (!isOpen) {
      setOtp(["", "", "", "", "", ""])
    }
  }, [isOpen])

  const handleChange = (index: number, value: string) => {
    if (value.length > 1) {
      const digits = value.replace(/\D/g, "").slice(0, 6).split("")
      const newOtp = [...otp]
      digits.forEach((digit, i) => {
        if (index + i < 6) newOtp[index + i] = digit
      })
      setOtp(newOtp)
      const nextIndex = Math.min(index + digits.length, 5)
      inputRefs.current[nextIndex]?.focus()
      return
    }
    if (!/^\d*$/.test(value)) return
    const newOtp = [...otp]
    newOtp[index] = value
    setOtp(newOtp)
    if (value && index < 5) inputRefs.current[index + 1]?.focus()
  }

  const handleKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === "Backspace" && !otp[index] && index > 0) {
      inputRefs.current[index - 1]?.focus()
    }
  }

  const isComplete = otp.every((d) => d !== "")

  const handleSubmit = async () => {
    if (!isComplete || loading) return
    setLoading(true)
    try {
      const code = otp.join("")
      const res = await accountsApi.verifyCode(sessionId, code)
      if (res.status === "success") {
        toast.success("Account added successfully")
        onSuccess()
      } else if (res.status === "requires_2fa") {
        onRequires2FA()
      }
    } catch (e) {
      toast.error((e as Error).message)
      setOtp(["", "", "", "", "", ""])
      inputRefs.current[0]?.focus()
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
        <h1 className="text-xl font-semibold text-foreground mb-3">{phoneNumber}</h1>
        <p className="text-muted-foreground text-sm mb-10 leading-relaxed">
          A code was sent <span className="text-foreground font-medium">via Telegram</span> to
          your other devices, if you have any connected.
        </p>

        <div className="flex gap-3 mb-6">
          {otp.map((digit, index) => (
            <input
              key={index}
              ref={(el) => {
                inputRefs.current[index] = el
              }}
              type="text"
              inputMode="numeric"
              maxLength={6}
              value={digit}
              onChange={(e) => handleChange(index, e.target.value)}
              onKeyDown={(e) => handleKeyDown(index, e)}
              className={cn(
                "w-12 h-14 text-center text-xl font-medium rounded-lg border-2 bg-transparent text-foreground transition-all focus:outline-none",
                digit
                  ? "border-primary"
                  : index === otp.findIndex((d) => d === "")
                    ? "border-primary"
                    : "border-border/50",
              )}
            />
          ))}
        </div>

        <button
          onClick={handleSubmit}
          disabled={!isComplete || loading}
          className={cn(
            "w-full py-4 rounded-lg font-medium text-base transition-all flex items-center justify-center gap-2",
            isComplete && !loading
              ? "bg-primary text-primary-foreground hover:bg-primary/90"
              : "bg-primary/50 text-primary-foreground/70 cursor-not-allowed",
          )}
        >
          {loading && <Loader2 className="h-4 w-4 animate-spin" />}
          Next
        </button>
      </div>
    </div>
  )
}
