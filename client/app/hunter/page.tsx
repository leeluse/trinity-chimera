"use client";

import React from 'react';

export default function HunterPage() {
  return (
    <div className="flex h-screen w-full flex-col bg-[#06070d]">
      <div className="flex-1 overflow-hidden">
        <iframe 
          src="/hunter.html" 
          className="h-full w-full border-none"
          title="Hunter Engine Web View"
        />
      </div>
    </div>
  );
}
