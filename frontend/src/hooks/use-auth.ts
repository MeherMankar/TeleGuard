import { useEffect, useState } from "react"
import { authStore } from "@/store/auth"

export function useAuth() {
  const [state, setState] = useState(() => authStore.getState())

  useEffect(() => {
    return authStore.subscribe(setState)
  }, [])

  return state
}
