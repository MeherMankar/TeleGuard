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
      className={cn(
        "fixed bottom-20 right-4 z-20 flex h-14 w-14 items-center justify-center rounded-full bg-[#2AABEE] text-white shadow-lg shadow-black/20 transition-colors hover:bg-[#229ed9] md:absolute md:bottom-6 md:right-6",
        className,
      )}
    >
      <Pencil className="h-6 w-6" />
    </button>
  )
}
