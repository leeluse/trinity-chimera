"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  LayoutDashboard, 
  Search, 
  History, 
  Settings, 
  ShieldAlert,
  BarChart3
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { icon: LayoutDashboard, label: "Dashboard", href: "/" },
  { icon: Search, label: "Scanner", href: "/scanner" },
  { icon: History, label: "Backtest", href: "/backtest" },
  { icon: ShieldAlert, label: "Liquidation", href: "/liquidation" },
  { icon: BarChart3, label: "Stats", href: "/stats" },
  { icon: Settings, label: "Settings", href: "/settings" },
];

export function NavigationSidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-[72px] bg-background border-r border-white/5 flex flex-col items-center py-6 gap-8 z-[200]">
      {/* App Logo */}
      <div className="w-10 h-10 bg-primary/10 rounded-xl flex items-center justify-center border border-primary/20 rotate-45 mb-4">
        <div className="-rotate-45 font-black text-primary text-xl">T</div>
      </div>

      {/* Navigation */}
      <nav className="flex flex-col gap-4 flex-1">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "w-12 h-12 rounded-xl flex items-center justify-center transition-all group relative",
                isActive 
                  ? "bg-primary/10 text-primary border border-primary/20 shadow-[0_0_15px_rgba(189,147,249,0.1)]" 
                  : "text-slate-500 hover:text-slate-200 hover:bg-white/5"
              )}
            >
              <item.icon className={cn("w-5 h-5", isActive && "stroke-[2.5px]")} />
              
              {/* Tooltip (simplified) */}
              <div className="absolute left-full ml-4 px-2 py-1 bg-slate-900 border border-white/10 rounded text-[10px] font-mono whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-[300]">
                {item.label}
              </div>

              {/* Active Indicator */}
              {isActive && (
                <div className="absolute left-0 w-1 h-6 bg-primary rounded-full -ml-[22px]" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* User / Bottom Actions */}
      <div className="mt-auto flex flex-col gap-4">
        <div className="w-10 h-10 rounded-full bg-slate-800 border border-white/10 overflow-hidden cursor-pointer hover:border-primary/50 transition-colors">
          {/* Avatar placeholder */}
        </div>
      </div>
    </aside>
  );
}
