
import { useEffect } from "react"
import { Check } from "lucide-react"
import { cn } from "@/lib/utils"

interface LoginSuccessPageProps {
  isOpen: boolean
  onComplete: () => void
}

export function LoginSuccessPage({ isOpen, onComplete }: LoginSuccessPageProps) {
  useEffect(() => {
    if (isOpen) {
      const timer = setTimeout(() => {
        onComplete()
      }, 2000)
      return () => clearTimeout(timer)
    }
  }, [isOpen, onComplete])

  return (
    <div
      style={{ zIndex: 80 }}
      className={cn(
        "fixed inset-0 bg-background flex flex-col items-center justify-center transition-transform duration-300 ease-in-out",
        isOpen ? "translate-x-0" : "translate-x-full"
      )}
    >
      {/* Success Icon */}
      <div className="w-24 h-24 rounded-full bg-green-500 flex items-center justify-center mb-6 animate-bounce">
        <Check className="h-12 w-12 text-white" strokeWidth={3} />
      </div>

      {/* Success Text */}
      <h1 className="text-2xl font-semibold text-foreground mb-2">Login Successful!</h1>
      <p className="text-muted-foreground text-sm">Redirecting to your chats...</p>

      {/* Loading dots */}
      <div className="flex gap-1 mt-8">
        <div className="w-2 h-2 rounded-full bg-primary animate-pulse" style={{ animationDelay: "0ms" }} />
        <div className="w-2 h-2 rounded-full bg-primary animate-pulse" style={{ animationDelay: "150ms" }} />
        <div className="w-2 h-2 rounded-full bg-primary animate-pulse" style={{ animationDelay: "300ms" }} />
      </div>
    </div>
  )
}
