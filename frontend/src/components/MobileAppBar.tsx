"use client";

import { Menu } from "lucide-react";

interface MobileAppBarProps {
  title: string;
  onMenuClick: () => void;
}

export function MobileAppBar({ title, onMenuClick }: MobileAppBarProps) {
  return (
    <header className="md:hidden fixed top-0 left-0 right-0 h-12 bg-zinc-900 text-zinc-100 border-b border-zinc-700 flex items-center justify-between px-3 safe-area-inset-top z-40">
      <h1 className="text-sm font-semibold text-white">{title}</h1>
      <button
        onClick={onMenuClick}
        className="p-2 text-zinc-300 hover:text-zinc-100 hover:bg-zinc-800 rounded transition-colors duration-150 ease-out"
        title="Open menu"
        aria-label="Open menu"
      >
        <Menu className="w-5 h-5" />
      </button>
    </header>
  );
}
