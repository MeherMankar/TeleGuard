import { useState } from "react";
import {
  ArrowLeft,
  Phone,
  AtSign,
  Cake,
  ChevronRight,
  UserPlus,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useUser, formatBirthday } from "@/contexts/user-context";

interface AccountSettingsPageProps {
  isOpen: boolean;
  onClose: () => void;
}

const BIO_MAX = 70;

function SectionCard({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("mx-3 mt-3 rounded-2xl bg-card overflow-hidden border border-border/40", className)}>
      {children}
    </div>
  );
}

function InfoRow({
  icon: Icon,
  iconBg,
  primary,
  secondary,
  last,
  onClick,
}: {
  icon: React.ElementType;
  iconBg: string;
  primary: string;
  secondary: string;
  last?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full flex items-center gap-3.5 px-4 py-3 hover:bg-secondary/30 active:bg-secondary/50 transition-colors text-left",
        !last && "border-b border-border/30",
      )}
    >
      <div
        className={cn(
          "w-10 h-10 rounded-full flex items-center justify-center shrink-0",
          iconBg,
        )}
      >
        <Icon className="h-5 w-5 text-white" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[15px] text-foreground leading-tight">{primary}</p>
        <p className="text-[13px] text-muted-foreground mt-0.5">{secondary}</p>
      </div>
    </button>
  );
}

export function AccountSettingsPage({ isOpen, onClose }: AccountSettingsPageProps) {
  const { profile, updateProfile } = useUser();

  const [firstName, setFirstName] = useState(() => profile.name.split(" ")[0] ?? "");
  const [lastName, setLastName] = useState(() => profile.name.split(" ").slice(1).join(" ") ?? "");
  const [bio, setBio] = useState(profile.bio);

  // Persist name changes on blur
  function handleNameBlur() {
    const combined = [firstName, lastName].filter(Boolean).join(" ");
    if (combined !== profile.name) {
      updateProfile({ name: combined });
    }
  }

  // Persist bio on blur
  function handleBioBlur() {
    if (bio !== profile.bio) {
      updateProfile({ bio });
    }
  }

  const bioRemaining = BIO_MAX - bio.length;

  return (
    <div
      style={{ zIndex: 85 }}
      className={cn(
        "fixed inset-0 flex flex-col bg-background transition-transform duration-300 ease-in-out",
        isOpen ? "translate-x-0" : "translate-x-full",
      )}
    >
      {/* Header */}
      <div className="sticky top-0 z-10 flex items-center gap-3 px-2 py-3 bg-card/95 backdrop-blur border-b border-border/40">
        <button onClick={onClose} aria-label="Back" className="p-2 text-foreground">
          <ArrowLeft className="h-6 w-6" />
        </button>
        <h1 className="flex-1 text-[20px] font-semibold text-foreground">Account</h1>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto pb-8">

        {/* Your Info */}
        <SectionCard className="mt-4">
          <p className="px-4 pt-3 pb-1 text-sky-400 text-[13px] font-semibold">Your Info</p>
          <InfoRow
            icon={Phone}
            iconBg="bg-sky-500"
            primary={profile.phone}
            secondary="Tap to change phone number"
          />
          <InfoRow
            icon={AtSign}
            iconBg="bg-sky-500"
            primary={profile.username}
            secondary="Username"
          />
          <InfoRow
            icon={Cake}
            iconBg="bg-orange-400"
            primary={formatBirthday(profile.birthday)}
            secondary="Birthday"
            last
          />
        </SectionCard>

        {/* Birthday visibility note */}
        <p className="px-5 mt-2 text-[13px] text-muted-foreground">
          Only your contacts can see your birthday.{" "}
          <button className="text-sky-400 inline-flex items-center gap-0.5">
            Change <ChevronRight className="h-3 w-3" />
          </button>
        </p>

        {/* Your name */}
        <SectionCard className="mt-3">
          <p className="px-4 pt-3 pb-1 text-sky-400 text-[13px] font-semibold">Your name</p>
          <div className="border-b border-border/30">
            <input
              type="text"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              onBlur={handleNameBlur}
              placeholder="First name"
              className="w-full px-4 py-3 bg-transparent text-[17px] text-foreground placeholder:text-muted-foreground outline-none"
            />
          </div>
          <input
            type="text"
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            onBlur={handleNameBlur}
            placeholder="Last name"
            className="w-full px-4 py-3 bg-transparent text-[17px] text-foreground placeholder:text-muted-foreground outline-none"
          />
        </SectionCard>

        {/* Your bio */}
        <SectionCard className="mt-3">
          <p className="px-4 pt-3 pb-1 text-sky-400 text-[13px] font-semibold">Your bio</p>
          <div className="relative px-4 pb-3">
            <textarea
              value={bio}
              onChange={(e) => {
                if (e.target.value.length <= BIO_MAX) setBio(e.target.value);
              }}
              onBlur={handleBioBlur}
              rows={3}
              placeholder="Add a few lines about yourself..."
              className="w-full bg-transparent text-[15px] text-foreground placeholder:text-muted-foreground outline-none resize-none leading-relaxed pr-8"
            />
            {bioRemaining <= 20 && (
              <span
                className={cn(
                  "absolute bottom-4 right-4 text-[13px] tabular-nums",
                  bioRemaining <= 5 ? "text-red-400" : "text-muted-foreground",
                )}
              >
                {bioRemaining}
              </span>
            )}
          </div>
        </SectionCard>

        {/* Bio helper text */}
        <p className="px-5 mt-2 text-[13px] text-muted-foreground">
          You can add a few lines about yourself. Choose who can see your bio in{" "}
          <button className="text-sky-400">Settings</button>.
        </p>

        {/* Personal channel */}
        <SectionCard className="mt-3">
          <button className="w-full flex items-center justify-between px-4 py-3 hover:bg-secondary/30 active:bg-secondary/50 transition-colors text-left">
            <span className="text-[15px] text-foreground">Personal channel</span>
            <span className="text-[15px] text-sky-400 truncate max-w-[180px] text-right">
              {profile.personalChannel}
            </span>
          </button>
        </SectionCard>

        {/* Add Account */}
        <SectionCard className="mt-3">
          <button className="w-full flex items-center gap-3.5 px-4 py-3 hover:bg-secondary/30 active:bg-secondary/50 transition-colors text-left">
            <div className="w-10 h-10 rounded-full bg-sky-500/20 border-2 border-sky-500/40 flex items-center justify-center shrink-0">
              <UserPlus className="h-5 w-5 text-sky-400" />
            </div>
            <span className="text-[15px] text-sky-400 font-medium">Add Account</span>
          </button>
        </SectionCard>

        {/* Bottom profile row */}
        <SectionCard className="mt-3">
          <button className="w-full flex items-center gap-3.5 px-4 py-3 hover:bg-secondary/30 active:bg-secondary/50 transition-colors text-left">
            <div className="w-10 h-10 rounded-full overflow-hidden bg-gradient-to-br from-rose-400 to-rose-700 shrink-0 flex items-center justify-center text-white font-bold text-lg">
              {profile.avatarUrl ? (
                <img src={profile.avatarUrl} alt="Profile" className="w-full h-full object-cover" />
              ) : (
                <span>{profile.name.charAt(0)}</span>
              )}
            </div>
            <span className="flex-1 text-[15px] text-foreground">.</span>
            <span className="min-w-[28px] h-[22px] rounded-full bg-sky-500 text-white text-xs font-medium flex items-center justify-center px-2">
              67
            </span>
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          </button>
        </SectionCard>

      </div>
    </div>
  );
}
