import { useEffect, useState } from "react"
import { QRLoginPage } from "./qr-login-page"
import { PhoneLoginPage } from "./phone-login-page"
import { OTPPage } from "./otp-page"
import { CloudPasswordPage } from "./cloud-password-page"

type AuthStep = "qr" | "phone" | "otp" | "password" | "qr_password" | null

interface AuthFlowProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
}

export function AuthFlow({ isOpen, onClose, onSuccess }: AuthFlowProps) {
  const [step, setStep] = useState<AuthStep>(null)
  const [phoneNumber, setPhoneNumber] = useState("")
  const [sessionId, setSessionId] = useState("")

  useEffect(() => {
    if (isOpen && step === null) setStep("qr")
  }, [isOpen, step])

  const handleClose = () => {
    setStep(null)
    setPhoneNumber("")
    setSessionId("")
    onClose()
  }

  const handleSuccess = () => {
    setStep(null)
    setPhoneNumber("")
    setSessionId("")
    onSuccess()
  }

  return (
    <>
      {/* QR Login — also handles QR → 2FA redirect */}
      <QRLoginPage
        isOpen={isOpen && step === "qr"}
        onClose={handleClose}
        onPhoneLogin={() => setStep("phone")}
        onSuccess={handleSuccess}
        onRequires2FA={(sid) => {
          setSessionId(sid)
          setStep("qr_password")
        }}
      />

      {/* Phone login */}
      <PhoneLoginPage
        isOpen={isOpen && step === "phone"}
        onBack={() => setStep("qr")}
        onNext={(phone, sid) => {
          setPhoneNumber(phone)
          setSessionId(sid)
          setStep("otp")
        }}
        onQRLogin={() => setStep("qr")}
      />

      {/* OTP verification */}
      <OTPPage
        isOpen={isOpen && step === "otp"}
        phoneNumber={phoneNumber}
        sessionId={sessionId}
        onSuccess={handleSuccess}
        onRequires2FA={() => setStep("password")}
      />

      {/* 2FA after phone+OTP */}
      <CloudPasswordPage
        isOpen={isOpen && step === "password"}
        sessionId={sessionId}
        onSuccess={handleSuccess}
        mode="phone"
      />

      {/* 2FA after QR scan */}
      <CloudPasswordPage
        isOpen={isOpen && step === "qr_password"}
        sessionId={sessionId}
        onSuccess={handleSuccess}
        mode="qr"
      />
    </>
  )
}
