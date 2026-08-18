/**
 * AccountSettingsPage — thin wrapper that opens EditProfilePage.
 * The original version used local-state-only saves (lost on refresh).
 * EditProfilePage calls the real Telegram API via PATCH /api/accounts/profile.
 */
import { EditProfilePage } from "./edit-profile-page"

interface AccountSettingsPageProps {
  isOpen: boolean
  onClose: () => void
}

export function AccountSettingsPage({ isOpen, onClose }: AccountSettingsPageProps) {
  return (
    <EditProfilePage
      isOpen={isOpen}
      onClose={onClose}
      onBack={onClose}
    />
  )
}
