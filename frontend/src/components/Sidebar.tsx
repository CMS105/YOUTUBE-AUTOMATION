"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Film,
  Radio,
  Users,
  Video,
  SlidersHorizontal,
  Layers,
  BarChart3,
  ShieldCheck,
  HardDrive,
  Settings,
  Flame,
  CheckCircle2,
} from "lucide-react";

const NAV_ITEMS = [
  { label: "Overview", href: "/", icon: Flame },
  { label: "Stream Monitor", href: "/stream-monitor", icon: Radio },
  { label: "Streamers", href: "/streamers", icon: Users },
  { label: "Clip Library", href: "/clips", icon: Film },
  { label: "Clip Editor", href: "/editor", icon: Video },
  { label: "Processing Queue", href: "/queue", icon: Layers },
  { label: "Analytics", href: "/analytics", icon: BarChart3 },
  { label: "Permissions", href: "/permissions", icon: ShieldCheck },
  { label: "Storage", href: "/storage", icon: HardDrive },
  { label: "Settings", href: "/settings", icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 bg-surface border-r border-border flex flex-col h-screen fixed left-0 top-0 z-30 select-none">
      {/* Brand Header */}
      <div className="h-16 flex items-center px-6 border-b border-border gap-3">
        <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-accent-cyan to-blue-600 flex items-center justify-center glow-cyan font-black text-slate-950 text-xl tracking-tighter">
          VI
        </div>
        <div>
          <div className="font-bold text-sm tracking-wide text-text-primary uppercase flex items-center gap-1.5">
            GTA 6 Clip Factory
          </div>
          <div className="text-[10px] text-accent-cyan tracking-wider font-mono">
            AI PRODUCTION ENGINE
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-medium transition-all ${
                isActive
                  ? "bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/30 glow-cyan font-semibold"
                  : "text-text-secondary hover:text-text-primary hover:bg-surface-elevated/70"
              }`}
            >
              <Icon className={`w-4 h-4 ${isActive ? "text-accent-cyan" : "text-text-muted"}`} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Safety Guard Indicator */}
      <div className="p-4 border-t border-border bg-background/50">
        <div className="p-2.5 rounded-lg bg-surface-elevated/60 border border-border flex items-center gap-2.5">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <div>
            <div className="text-[11px] font-medium text-emerald-400">Auto-Publish Safe</div>
            <div className="text-[9px] text-text-muted">Strict manual approval only</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
