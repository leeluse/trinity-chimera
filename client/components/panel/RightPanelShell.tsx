"use client";

import { ReactNode } from "react";
import PanelTabs from "./sections/PanelTabs";
import { cn } from "@/lib/utils";

interface RightPanelShellProps {
  children?: ReactNode;
  className?: string;
}

export function RightPanelShell({ children, className }: RightPanelShellProps) {
  return (
    <div className={cn("flex flex-col h-full overflow-hidden bg-background/50", className)}>
      <PanelTabs />
      <div className="flex-1 overflow-y-auto no-scrollbar flex flex-col min-h-0">
        {children}
      </div>
    </div>
  );
}
