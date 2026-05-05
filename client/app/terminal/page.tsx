"use client";

import React, { Suspense } from 'react';
import TerminalMigrated from "@/components/features/terminal/TerminalMigrated";

function TerminalContent() {
  return <TerminalMigrated />;
}

export default function TerminalPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center min-h-screen bg-[#030508] text-white">로딩 중...</div>}>
      <TerminalContent />
    </Suspense>
  );
}
