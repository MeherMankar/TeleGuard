
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
        "fixed bottom-20 right-4 h-14 w-14 rounded-full bg-[#2AABEE] text-white shadow-xl flex items-center justify-center hover:bg-[#2AABEE]/90 transition-colors z-20",
        className
      )}
    >
      <Pencil className="h-6 w-6" />
    </button>
  )
}
