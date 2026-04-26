"use client";

import React from 'react';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

export default function HunterPage() {
  return (
    <div className="w-screen h-screen bg-[#030508] flex flex-col overflow-hidden">
      <div className="h-10 border-b border-white/10 flex items-center px-4 bg-background z-50">
        <Link
          href="/"
          className="flex items-center gap-2 text-[11px] text-slate-400 hover:text-white transition-colors font-mono font-bold"
        >
          <ArrowLeft size={14} />
          <span>RETURN TO DASHBOARD</span>
        </Link>
        <div className="ml-auto flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-orange-500 animate-pulse"></div>
            <span className="text-[10px] text-orange-500 font-bold font-mono tracking-widest uppercase">Embedded View: Hunter V16</span>
          </div>
        </div>
      </div>
      <div className="flex-1 relative">
        <iframe
          src="/hunter.html"
          className="w-full h-full border-none"
          title="Alpha Hunter"
        />
      </div>
    </div>
  );
}
