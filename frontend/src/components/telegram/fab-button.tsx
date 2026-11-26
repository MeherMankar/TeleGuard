import { Pencil } from "lucide-react"
import { cn } from "@/lib/utils"

interface FabButtonProps {
  onClick?: () => void
  className?: string
}

export function FabButton({ onClick, className }: FabButtonProps) {
  return (
    <button
      onClick={onClick}
      aria-label="Compose message"
      className={cn(
        "fixed bottom-20 right-4 z-20 flex h-12 w-12 items-center justify-center rounded-full bg-[#2AABEE] text-white transition-colors hover:bg-[#229ed9] active:scale-[0.98] md:absolute md:bottom-6 md:right-6",
        className,
      )}
    >
      <Pencil className="h-6 w-6" />
    </button>
  )
}
