import { useState } from "react";
import {
  ArrowLeft,
  ChevronRight,
  Eye,
  Phone,
  UserPlus,
  MessageSquare,
  Users,
  AtSign,
  Link2,
  Trash2,
  Lock,
  Key,
  Fingerprint,
  Mail,
  ShieldCheck,
  Smartphone,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { DevicesPage } from "./devices-page";

interface PrivacySecurityPageProps {
  isOpen: boolean;
  onClose: () => void;
}

type PrivacyOption = {
  label: string;
  value: string;
};

type SettingRow = {
  icon: React.ElementType;
  label: string;
  value?: string;
  iconBg: string;
  hasArrow?: boolean;
  isDestructive?: boolean;
};

const privacySettings: SettingRow[] = [
  {
    icon: Eye,
    label: "Last Seen & Online",
    value: "Everybody",
    iconBg: "bg-sky-500",
    hasArrow: true,
  },
  {
    icon: Phone,
    label: "Phone Number",
    value: "My Contacts",
    iconBg: "bg-emerald-500",
    hasArrow: true,
  },
  {
    icon: UserPlus,
    label: "Who can add me to groups",
    value: "Everybody",
    iconBg: "bg-violet-500",
    hasArrow: true,
  },
  {
    icon: MessageSquare,
    label: "Who can send me messages",
    value: "Everybody",
    iconBg: "bg-orange-500",
    hasArrow: true,
  },
  {
    icon: Users,
    label: "Profile Photo",
    value: "Everybody",
    iconBg: "bg-rose-500",
    hasArrow: true,
  },
  {
    icon: AtSign,
    label: "Bio",
    value: "Everybody",
    iconBg: "bg-cyan-500",
    hasArrow: true,
  },
  {
    icon: Link2,
    label: "Forwarded Messages",
    value: "Everybody",
    iconBg: "bg-indigo-500",
    hasArrow: true,
  },
];

const securitySettings: SettingRow[] = [
  {
    icon: Lock,
    label: "Passcode Lock",
    value: "Off",
    iconBg: "bg-sky-500",
    hasArrow: true,
  },
  {
    icon: Key,
    label: "Two-Step Verification",
    value: "Off",
    iconBg: "bg-emerald-500",
    hasArrow: true,
  },
  {
    icon: Fingerprint,
    label: "Passkeys",
    value: "None",
    iconBg: "bg-violet-500",
    hasArrow: true,
  },
  {
    icon: Mail,
    label: "Login Email",
    value: "Set",
    iconBg: "bg-orange-500",
    hasArrow: true,
  },
];

const deviceSettings: SettingRow[] = [
  {
    icon: Smartphone,
    label: "Devices",
    value: "4 devices",
    iconBg: "bg-cyan-500",
    hasArrow: true,
  },
];

const otherSettings: SettingRow[] = [
  {
    icon: ShieldCheck,
    label: "Secret Chats",
    iconBg: "bg-emerald-500",
    hasArrow: true,
  },
  {
    icon: Trash2,
    label: "Delete My Account",
    value: "If away for 6 months",
    iconBg: "bg-red-500",
    hasArrow: true,
    isDestructive: true,
  },
];

function SettingItem({
  setting,
  last,
  onClick,
}: {
  setting: SettingRow;
  last?: boolean;
  onClick?: () => void;
}) {
  const Icon = setting.icon;
  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full flex items-center gap-3.5 px-4 py-3 hover:bg-secondary/30 active:bg-secondary/50 transition-colors text-left",
        !last && "border-b border-border/30"
      )}
    >
      <div
        className={cn(
          "w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0",
          setting.iconBg
        )}
      >
        <Icon className="h-5 w-5 text-white" />
      </div>
      <div className="flex-1 min-w-0">
        <p
          className={cn(
            "text-[15px] font-medium",
            setting.isDestructive ? "text-red-500" : "text-foreground"
          )}
        >
          {setting.label}
        </p>
      </div>
      {setting.value && (
        <span className="text-[14px] text-sky-400 mr-1">{setting.value}</span>
      )}
      {setting.hasArrow && (
        <ChevronRight className="h-5 w-5 text-muted-foreground flex-shrink-0" />
      )}
    </button>
  );
}

function SectionCard({
  children,
  label,
  description,
}: {
  children: React.ReactNode;
  label?: string;
  description?: string;
}) {
  return (
    <div className="mx-3 mt-4">
      {label && (
        <p className="px-4 pb-2 text-sky-400 text-[13px] font-semibold uppercase tracking-wide">
          {label}
        </p>
      )}
      <div className="rounded-2xl bg-card overflow-hidden border border-border/40">
        {children}
      </div>
      {description && (
        <p className="px-4 pt-2 text-[13px] text-muted-foreground">{description}</p>
      )}
    </div>
  );
}

export function PrivacySecurityPage({ isOpen, onClose }: PrivacySecurityPageProps) {
  const [isDevicesOpen, setIsDevicesOpen] = useState(false);

  const handleSettingClick = (label: string) => {
    if (label === "Devices") {
      setIsDevicesOpen(true);
    }
  };

  return (
    <div
      style={{ zIndex: 85 }}
      className={cn(
        "fixed inset-0 flex flex-col bg-background transition-transform duration-300 ease-in-out",
        isOpen ? "translate-x-0" : "translate-x-full"
      )}
    >
      {/* Top bar */}
      <div className="sticky top-0 z-10 flex items-center gap-3 px-2 py-3 bg-card/95 backdrop-blur border-b border-border/40">
        <button onClick={onClose} aria-label="Back" className="p-2 text-foreground">
          <ArrowLeft className="h-6 w-6" />
        </button>
        <h1 className="flex-1 text-[20px] font-semibold text-foreground">
          Privacy and Security
        </h1>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto pb-8">
        {/* Privacy section */}
        <SectionCard
          label="Privacy"
          description="Change who can see your personal info."
        >
          {privacySettings.map((setting, index) => (
            <SettingItem
              key={setting.label}
              setting={setting}
              last={index === privacySettings.length - 1}
              onClick={() => handleSettingClick(setting.label)}
            />
          ))}
        </SectionCard>

        {/* Security section */}
        <SectionCard
          label="Security"
          description="Configure additional security options."
        >
          {securitySettings.map((setting, index) => (
            <SettingItem
              key={setting.label}
              setting={setting}
              last={index === securitySettings.length - 1}
              onClick={() => handleSettingClick(setting.label)}
            />
          ))}
        </SectionCard>

        {/* Devices section */}
        <SectionCard description="Review active sessions and link new devices.">
          {deviceSettings.map((setting, index) => (
            <SettingItem
              key={setting.label}
              setting={setting}
              last={index === deviceSettings.length - 1}
              onClick={() => handleSettingClick(setting.label)}
            />
          ))}
        </SectionCard>

        {/* Other section */}
        <SectionCard label="Other">
          {otherSettings.map((setting, index) => (
            <SettingItem
              key={setting.label}
              setting={setting}
              last={index === otherSettings.length - 1}
              onClick={() => handleSettingClick(setting.label)}
            />
          ))}
        </SectionCard>

        {/* Bot section info */}
        <div className="mx-3 mt-6">
          <p className="px-4 text-[13px] text-muted-foreground text-center">
            Control your privacy and security settings.
          </p>
          <p className="px-4 text-[13px] text-muted-foreground text-center mt-1">
            Tap on any option to configure it.
          </p>
        </div>
      </div>

      {/* Devices sub-page */}
      <DevicesPage isOpen={isDevicesOpen} onClose={() => setIsDevicesOpen(false)} />
    </div>
  );
}
