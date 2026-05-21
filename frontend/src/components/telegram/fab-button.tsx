
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
        "fixed bottom-6 right-6 h-14 w-14 rounded-full bg-primary text-primary-foreground shadow-lg flex items-center justify-center hover:bg-primary/90 transition-colors",
        className
      )}
    >
      <Pencil className="h-6 w-6" />
    </button>
  )
}
