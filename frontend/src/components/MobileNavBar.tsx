"use client";

import type { View } from "@/types";
import {
  FolderOpen,
  MessageSquare,
  Upload,
  CheckCircle,
} from "lucide-react";

const NAV_ITEMS: { id: View; label: string; icon: React.ReactNode }[] = [
  { id: "explorer", label: "Explorer", icon: <FolderOpen className="w-5 h-5" /> },
  { id: "chat", label: "Chat", icon: <MessageSquare className="w-5 h-5" /> },
  { id: "upload", label: "Upload", icon: <Upload className="w-5 h-5" /> },
  { id: "quality", label: "Quality", icon: <CheckCircle className="w-5 h-5" /> },
];

interface MobileNavBarProps {
  activeView: View;
  onNavigate: (view: View) => void;
}

export function MobileNavBar({ activeView, onNavigate }: MobileNavBarProps) {
  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-zinc-900 text-zinc-100 border-t border-zinc-700 flex justify-around items-center h-14 safe-area-inset-bottom z-50">
      {NAV_ITEMS.map((item) => {
        const isActive = activeView === item.id;
        return (
          <button
            key={item.id}
            onClick={() => onNavigate(item.id)}
            className={`flex flex-col items-center justify-center w-16 h-12 rounded transition-colors duration-150 ease-out ${
              isActive
                ? "text-violet-400"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
            title={item.label}
          >
            {item.icon}
            <span className="text-[10px] font-medium mt-0.5">{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
