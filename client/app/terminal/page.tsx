import React, { Suspense } from 'react';
import TerminalMigrated from "@/components/features/terminal/TerminalMigrated";

export default function TerminalPage() {
  return (
    <Suspense fallback={<div className="h-screen w-full bg-[#030508] animate-pulse" />}>
      <TerminalMigrated />
    </Suspense>
  );
}
