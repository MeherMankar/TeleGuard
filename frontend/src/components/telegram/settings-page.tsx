import { useRef, useState } from "react";
import {
  ArrowLeft,
  Search,
  MoreVertical,
  Camera,
  ChevronRight,
  Settings as SettingsIcon,
  Users,
  User as UserIcon,
  MessageCircle,
  KeyRound,
  Bell,
  Folder,
  Monitor,
  Globe,
  Star,
  MessageSquare,
  HelpCircle,
  Lightbulb,
  ShieldCheck,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useUser } from "@/contexts/user-context";
import { EditProfilePage } from "./edit-profile-page";
import { DevicesPage } from "./devices-page";
import { PrivacySecurityPage } from "./privacy-security-page";
import { AccountSettingsPage } from "./account-settings-page";

interface SettingsPageProps {
  isOpen: boolean;
  onClose: () => void;
}

type Row = {
  icon: typeof SettingsIcon;
  label: string;
  subtitle?: string;
  iconBg: string;
  iconColor?: string;
};

const plusItems: Row[] = [{ icon: Users, label: "Support group", iconBg: "bg-sky-500" }];

const mainItems: Row[] = [
  { icon: UserIcon, label: "Account", subtitle: "Number, Username, Bio", iconBg: "bg-sky-500" },
  {
    icon: MessageCircle,
    label: "Chat Settings",
    subtitle: "Wallpaper, Night Mode, Animations",
    iconBg: "bg-orange-500",
  },
  {
    icon: KeyRound,
    label: "Privacy & Security",
    subtitle: "Last Seen, Devices, Passkeys",
    iconBg: "bg-emerald-500",
  },
  {
    icon: Folder,
    label: "Chat Folders",
    subtitle: "Sort chats into folders",
    iconBg: "bg-sky-500",
  },
  { icon: Monitor, label: "Devices", subtitle: "Manage connected devices", iconBg: "bg-cyan-500" },
  { icon: Globe, label: "Language", subtitle: "English", iconBg: "bg-violet-500" },
];

const helpItems: Row[] = [
  { icon: MessageSquare, label: "Ask a Question", iconBg: "bg-orange-500" },
  { icon: HelpCircle, label: "Telegram FAQ", iconBg: "bg-sky-500" },
  { icon: Lightbulb, label: "Telegram Features", iconBg: "bg-violet-500" },
  { icon: ShieldCheck, label: "Privacy Policy", iconBg: "bg-emerald-500" },
];

function SectionCard({ children, label }: { children: React.ReactNode; label?: string }) {
  return (
    <div className="mx-3 mt-3 rounded-2xl bg-card overflow-hidden">
      {label && <p className="px-4 pt-3 pb-1 text-sky-400 text-[13px] font-semibold">{label}</p>}
      {children}
    </div>
  );
}

function SettingsRow({ row, last, onClick }: { row: Row; last?: boolean; onClick?: () => void }) {
  const Icon = row.icon;
  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full flex items-center gap-3.5 px-3 py-2.5 hover:bg-secondary/30 active:bg-secondary/50 transition-colors text-left",
        !last && "border-b border-border/30",
      )}
    >
      <div
        className={cn("w-9 h-9 rounded-lg flex items-center justify-center shrink-0", row.iconBg)}
      >
        <Icon
          className={cn("h-5 w-5", row.iconColor ?? "text-white")}
          fill={row.icon === Star ? "currentColor" : "none"}
        />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[15px] text-foreground leading-tight">{row.label}</p>
        {row.subtitle && (
          <p className="text-[13px] text-muted-foreground mt-0.5 truncate">{row.subtitle}</p>
        )}
      </div>
      <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
    </button>
  );
}

function SettingsSubPage({
  title,
  isOpen,
  onClose,
}: {
  title: string;
  isOpen: boolean;
  onClose: () => void;
}) {
  return (
    <div
      style={{ zIndex: 90 }}
      className={cn(
        "fixed inset-0 flex flex-col bg-background transition-transform duration-300 ease-in-out",
        isOpen ? "translate-x-0" : "translate-x-full",
      )}
    >
      <div className="sticky top-0 z-10 flex items-center gap-3 px-2 py-3 bg-card/95 backdrop-blur border-b border-border/40">
        <button onClick={onClose} aria-label="Back" className="p-2 text-foreground">
          <ArrowLeft className="h-6 w-6" />
        </button>
        <h1 className="flex-1 text-[18px] font-semibold text-foreground">{title}</h1>
      </div>
      <div className="flex-1 overflow-y-auto p-6 text-center text-muted-foreground text-sm">
        {title} settings will appear here.
      </div>
    </div>
  );
}

export function SettingsPage({ isOpen, onClose }: SettingsPageProps) {
  const { profile, setAvatarUrl } = useUser();
  const avatarInputRef = useRef<HTMLInputElement>(null);
  const [scrolled, setScrolled] = useState(false);
  const [activeSub, setActiveSub] = useState<string | null>(null);
  const [isEditProfileOpen, setEditProfileOpen] = useState(false);
  const [isDevicesOpen, setIsDevicesOpen] = useState(false);
  const [isPrivacySecurityOpen, setIsPrivacySecurityOpen] = useState(false);
  const [isAccountSettingsOpen, setIsAccountSettingsOpen] = useState(false);

  function openRow(label: string) {
    if (label === "Account") {
      setIsAccountSettingsOpen(true);
    } else if (label === "Devices") {
      setIsDevicesOpen(true);
    } else if (label === "Privacy & Security") {
      setIsPrivacySecurityOpen(true);
    } else {
      setActiveSub(label);
    }
  }

  function handleAvatarChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setAvatarUrl(URL.createObjectURL(file));
  }

  return (
    <div
      style={{ zIndex: 80 }}
      className={cn(
        "fixed inset-0 flex flex-col bg-background transition-transform duration-300 ease-in-out",
        isOpen ? "translate-x-0" : "translate-x-full",
      )}
    >
      {/* Top bar */}
      <div
        className={cn(
          "sticky top-0 z-10 flex items-center gap-3 px-2 py-3 transition-colors",
          scrolled ? "bg-card/95 backdrop-blur border-b border-border/40" : "bg-background",
        )}
      >
        <button onClick={onClose} aria-label="Back" className="p-2 text-foreground">
          <ArrowLeft className="h-6 w-6" />
        </button>
        {scrolled && <h1 className="flex-1 text-[20px] font-semibold text-foreground">Settings</h1>}
        {!scrolled && <div className="flex-1" />}
        <button aria-label="Search" className="p-2 text-foreground">
          <Search className="h-5 w-5" />
        </button>
        <button aria-label="More" className="p-2 text-foreground">
          <MoreVertical className="h-5 w-5" />
        </button>
      </div>

      {/* Scrollable content */}
      <div
        className="flex-1 overflow-y-auto pb-8"
        onScroll={(e) => setScrolled((e.target as HTMLDivElement).scrollTop > 120)}
      >
        {/* Profile hero */}
        <div className="flex flex-col items-center pt-2 pb-6">
          <div className="relative">
            <div className="w-28 h-28 rounded-full overflow-hidden bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center text-white text-4xl font-bold">
              {profile.avatarUrl ? (
                <img src={profile.avatarUrl} alt="Avatar" className="w-full h-full object-cover" />
              ) : (
                <span>{profile.name.charAt(0)}</span>
              )}
            </div>
            <button
              onClick={() => avatarInputRef.current?.click()}
              aria-label="Change avatar"
              className="absolute -bottom-1 right-0 w-9 h-9 rounded-full bg-sky-500 border-[3px] border-background flex items-center justify-center"
            >
              <Camera className="h-4 w-4 text-white" />
            </button>
            <input
              ref={avatarInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={handleAvatarChange}
            />
          </div>
          <h2 className="mt-4 text-[22px] font-bold text-foreground">{profile.name}</h2>
          <p className="text-[15px] text-muted-foreground mt-0.5">{profile.username}</p>
        </div>

        {/* Accounts */}
        <SectionCard label="Accounts">
          <button className="w-full flex items-center gap-3.5 px-3 py-2.5 hover:bg-secondary/30 active:bg-secondary/50 transition-colors text-left">
            <div className="w-9 h-9 rounded-full overflow-hidden bg-gradient-to-br from-rose-400 to-rose-700 shrink-0" />
            <span className="flex-1 text-[15px] text-foreground">.</span>
            <span className="min-w-[28px] h-[22px] rounded-full bg-sky-500 text-white text-xs font-medium flex items-center justify-center px-2">
              61
            </span>
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          </button>
        </SectionCard>

        {/* Plus group */}
        <SectionCard>
          {plusItems.map((r, i) => (
            <SettingsRow
              key={r.label}
              row={r}
              last={i === plusItems.length - 1}
              onClick={() => openRow(r.label)}
            />
          ))}
        </SectionCard>

        {/* Main settings */}
        <SectionCard>
          {mainItems.map((r, i) => (
            <SettingsRow
              key={r.label}
              row={r}
              last={i === mainItems.length - 1}
              onClick={() => openRow(r.label)}
            />
          ))}
        </SectionCard>

        {/* Help */}
        <SectionCard label="Help">
          {helpItems.map((r, i) => (
            <SettingsRow
              key={r.label}
              row={r}
              last={i === helpItems.length - 1}
              onClick={() => openRow(r.label)}
            />
          ))}
        </SectionCard>

        {/* Footer */}
        <div className="text-center mt-6 px-4">
          <p className="text-[13px] text-muted-foreground">Plus Messenger for Android</p>
          <p className="text-[13px] text-muted-foreground">v12.6.4.1 (2218) universal arm64-v8a</p>
        </div>
      </div>

      <EditProfilePage
        isOpen={isEditProfileOpen}
        onClose={() => setEditProfileOpen(false)}
        onBack={() => setEditProfileOpen(false)}
      />
      <AccountSettingsPage
        isOpen={isAccountSettingsOpen}
        onClose={() => setIsAccountSettingsOpen(false)}
      />
      <DevicesPage isOpen={isDevicesOpen} onClose={() => setIsDevicesOpen(false)} />
      <PrivacySecurityPage
        isOpen={isPrivacySecurityOpen}
        onClose={() => setIsPrivacySecurityOpen(false)}
      />
      <SettingsSubPage
        title={activeSub ?? ""}
        isOpen={activeSub !== null}
        onClose={() => setActiveSub(null)}
      />
    </div>
  );
}
