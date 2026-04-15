"use client";

import { ReactNode } from "react";

interface RightPanelProps {
  children: ReactNode;
  className?: string;
  width?: string;
}

export default function RightPanel({ 
  children, 
  className = "", 
  width = "lg:w-[400px]"
}: RightPanelProps) {
  return (
    <div className={`
      w-full ${width} shrink-0 flex flex-col 
      border-t lg:border-t-0 lg:border-l border-white/[0.05] 
      bg-[#060912]/80 backdrop-blur-3xl relative z-[120] 
      h-screen sticky top-0
      ${className}
    `}>
      <div className="flex flex-col h-full overflow-hidden">
        {children}
      </div>
    </div>
  );
}
