import { useState } from "react";
import { ArrowLeft, Smartphone, Laptop, Chrome, Hand, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface DevicesPageProps {
  isOpen: boolean;
  onClose: () => void;
}

interface Device {
  id: string;
  type: "desktop" | "mobile" | "web";
  name: string;
  app: string;
  location: string;
  time: string;
  color: string;
  icon: React.ReactNode;
  isCurrent?: boolean;
}

const currentDevice: Device = {
  id: "current",
  type: "mobile",
  name: "Vivo V2135",
  app: "plus messenger 12.6.4.1",
  location: "Pune, India • online",
  time: "",
  color: "bg-teal-500",
  icon: <Smartphone className="h-5 w-5" />,
  isCurrent: true,
};

const activeSessions: Device[] = [
  {
    id: "1",
    type: "web",
    name: "Chrome 148",
    app: "Telegram Web 12.0.28 A",
    location: "Pune, India • 8:05 PM",
    time: "",
    color: "bg-rose-500",
    icon: <Chrome className="h-5 w-5" />,
  },
  {
    id: "2",
    type: "desktop",
    name: "8A3F",
    app: "Telegram Desktop 6.7.8 x64",
    location: "Parbhani, India • 3:42 PM",
    time: "",
    color: "bg-cyan-500",
    icon: <Laptop className="h-5 w-5" />,
  },
  {
    id: "3",
    type: "mobile",
    name: "Vivo V2135",
    app: "Telegram Android 12.1.1",
    location: "Nanded, India • 10:35 AM",
    time: "",
    color: "bg-green-500",
    icon: <Smartphone className="h-5 w-5" />,
  },
];

function DeviceCard({
  device,
  isCurrentDevice = false,
}: {
  device: Device;
  isCurrentDevice?: boolean;
}) {
  return (
    <div className="flex items-center gap-3.5 px-4 py-3">
      <div
        className={cn(
          "w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0",
          device.color,
        )}
      >
        <div className="text-white">{device.icon}</div>
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[15px] font-semibold text-foreground">{device.name}</p>
        <p className="text-[13px] text-muted-foreground mt-0.5">{device.app}</p>
        <p className="text-[13px] text-muted-foreground mt-0.5">{device.location}</p>
      </div>
    </div>
  );
}

export function DevicesPage({ isOpen, onClose }: DevicesPageProps) {
  const [selectedDevice, setSelectedDevice] = useState<string | null>(null);

  return (
    <div
      style={{ zIndex: 80 }}
      className={cn(
        "fixed inset-0 flex flex-col bg-background transition-transform duration-300 ease-in-out",
        isOpen ? "translate-x-0" : "translate-x-full",
      )}
    >
      {/* Top bar */}
      <div className="sticky top-0 z-10 flex items-center gap-3 px-2 py-3 bg-card/95 backdrop-blur border-b border-border/40">
        <button onClick={onClose} aria-label="Back" className="p-2 text-foreground">
          <ArrowLeft className="h-6 w-6" />
        </button>
        <h1 className="flex-1 text-[20px] font-semibold text-foreground">Devices</h1>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto pb-8">
        {/* Laptop illustration section */}
        <div className="px-6 py-8 flex flex-col items-center">
          <div className="relative w-40 h-32 mb-6">
            {/* Simple laptop SVG illustration */}
            <svg
              viewBox="0 0 200 160"
              className="w-full h-full"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              {/* Laptop body */}
              <rect
                x="20"
                y="20"
                width="160"
                height="90"
                rx="8"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              />
              {/* Screen content - QR code placeholder */}
              <g opacity="0.8">
                <rect
                  x="35"
                  y="35"
                  width="130"
                  height="60"
                  rx="4"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                />
                {/* QR code pattern */}
                <rect x="60" y="45" width="8" height="8" fill="currentColor" />
                <rect x="75" y="45" width="8" height="8" fill="currentColor" />
                <rect x="90" y="45" width="8" height="8" fill="currentColor" />
                <rect x="60" y="60" width="8" height="8" fill="currentColor" />
                <rect x="75" y="60" width="8" height="8" fill="currentColor" />
                <rect x="90" y="60" width="8" height="8" fill="currentColor" />
                <rect x="105" y="55" width="8" height="8" fill="currentColor" />
              </g>
              {/* Laptop base */}
              <rect
                x="30"
                y="110"
                width="140"
                height="8"
                rx="2"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              />
              {/* Laptop stand */}
              <path
                d="M 80 118 L 75 145 M 120 118 L 125 145"
                stroke="currentColor"
                strokeWidth="2"
                fill="none"
              />
            </svg>
          </div>

          <p className="text-[15px] text-foreground text-center mb-1">
            Link <span className="text-sky-400">Telegram Desktop</span> or{" "}
            <span className="text-sky-400">Telegram Web</span> by
          </p>
          <p className="text-[15px] text-foreground text-center">scanning a QR code.</p>
        </div>

        {/* Link Desktop button */}
        <div className="px-4 mb-6">
          <button className="w-full rounded-full bg-sky-500 hover:bg-sky-600 active:bg-sky-700 transition-colors py-3 flex items-center justify-center gap-2">
            <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24">
              <path d="M3 3h4v4H3V3zm6 0h4v4H9V3zm6 0h4v4h-4V3zM3 9h4v4H3V9zm6 0h4v4H9V9zm6 0h4v4h-4V9zM3 15h4v4H3v-4zm6 0h4v4H9v-4zm6 0h4v4h-4v-4z" />
            </svg>
            <span className="text-white font-medium">Link Desktop Device</span>
          </button>
        </div>

        {/* This device section */}
        <div className="mx-3 mt-6 rounded-2xl bg-card overflow-hidden border border-border/40">
          <p className="px-4 pt-3 pb-2 text-sky-400 text-[13px] font-semibold">This device</p>
          <DeviceCard device={currentDevice} isCurrentDevice={true} />

          {/* Terminate button */}
          <button className="w-full flex items-center gap-3.5 px-4 py-3 hover:bg-secondary/30 active:bg-secondary/50 transition-colors text-left border-t border-border/30">
            <div className="w-12 h-12 rounded-full bg-red-500/20 flex items-center justify-center flex-shrink-0">
              <Hand className="h-5 w-5 text-red-500" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[15px] font-semibold text-red-500">Terminate All Other Sessions</p>
            </div>
          </button>

          {/* Description */}
          <p className="text-[13px] text-muted-foreground px-4 py-3 border-t border-border/30">
            Logs out all devices except for this one.
          </p>
        </div>

        {/* Active sessions section */}
        <div className="mx-3 mt-6 rounded-2xl bg-card overflow-hidden border border-border/40">
          <p className="px-4 pt-3 pb-2 text-sky-400 text-[13px] font-semibold">Active sessions</p>
          {activeSessions.map((device, index) => (
            <div key={device.id}>
              <button
                onClick={() => setSelectedDevice(selectedDevice === device.id ? null : device.id)}
                className="w-full flex items-center gap-3.5 px-4 py-3 hover:bg-secondary/30 active:bg-secondary/50 transition-colors text-left"
              >
                <DeviceCard device={device} />
              </button>
              {index < activeSessions.length - 1 && <div className="border-b border-border/30" />}
            </div>
          ))}
        </div>

        {/* Footer text */}
        <div className="text-center mt-6 px-4 pb-6">
          <p className="text-[13px] text-muted-foreground">
            The official Telegram app is available for Android,
          </p>
          <p className="text-[13px] text-muted-foreground">iPhone, iPad, Windows, Mac and Linux.</p>
        </div>
      </div>
    </div>
  );
}
