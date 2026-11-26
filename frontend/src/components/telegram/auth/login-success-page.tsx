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
        "tg-screen tg-screen-narrow fixed inset-0 bg-background flex flex-col items-center justify-center transition-transform duration-300 ease-in-out",
        isOpen ? "translate-x-0" : "translate-x-full",
      )}
    >
      <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-[#4cc38a]/15 text-[#4cc38a]">
        <Check className="h-8 w-8" strokeWidth={2} />
      </div>

      <h1 className="mb-2 text-2xl font-medium text-foreground">Signed in</h1>
      <p className="text-sm text-muted-foreground">Opening your chats</p>
    </div>
  )
}
