import { createContext, useContext, useState, useEffect, ReactNode } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { accountsApi, type Account } from "@/lib/api"
import { authStore } from "@/store/auth"
import { useAuth } from "@/hooks/use-auth"
import { useWsEvent } from "@/hooks/use-ws-event"

export interface UserProfile {
  name: string
  username: string
  phone: string
  bio: string
  avatarUrl: string | null
}

interface UserContextType {
  profile: UserProfile
  accounts: Account[]
  activeAccount: Account | null
  setActiveAccount: (account: Account) => void
  refetchAccounts: () => void
}

const UserContext = createContext<UserContextType | undefined>(undefined)

export function UserProvider({ children }: { children: ReactNode }) {
  const { user, activeAccountName, authenticated } = useAuth()
  const queryClient = useQueryClient()

  const { data: accounts = [] } = useQuery({
    queryKey: ["accounts"],
    queryFn: accountsApi.list,
    enabled: authenticated,
    staleTime: 30_000,
  })

  // When a new account is added via WebSocket, refresh the list
  useWsEvent("account_added", () => {
    queryClient.invalidateQueries({ queryKey: ["accounts"] })
  })

  // When an account is removed via WebSocket, refresh the list
  useWsEvent("account_removed", () => {
    queryClient.invalidateQueries({ queryKey: ["accounts"] })
  })

  const activeAccount =
    accounts.find((a) => a.name === activeAccountName) ?? accounts[0] ?? null

  // Auto-set first account as active if none selected
  useEffect(() => {
    if (accounts.length > 0 && !activeAccountName) {
      authStore.setActiveAccount(accounts[0].name)
    }
  }, [accounts, activeAccountName])

  const profile: UserProfile = {
    name: activeAccount?.name ?? user?.first_name ?? "TeleGuard User",
    username: activeAccount?.username ? `@${activeAccount.username}` : user?.username ? `@${user.username}` : "",
    phone: activeAccount?.phone ?? "",
    bio: "",
    avatarUrl: null,
  }

  return (
    <UserContext.Provider
      value={{
        profile,
        accounts,
        activeAccount,
        setActiveAccount: (acc) => authStore.setActiveAccount(acc.name),
        refetchAccounts: () => queryClient.invalidateQueries({ queryKey: ["accounts"] }),
      }}
    >
      {children}
    </UserContext.Provider>
  )
}

export function useUser() {
  const context = useContext(UserContext)
  if (!context) throw new Error("useUser must be used within a UserProvider")
  return context
}

// Re-export helpers for backward compatibility
export { formatBirthday, calculateAge } from "@/lib/date-utils"
