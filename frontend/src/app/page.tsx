"use client";

import { useState, useEffect } from "react";
import type { View } from "@/types";
import { StatusProvider } from "@/lib/StatusContext";
import { CompileProvider } from "@/lib/CompileContext";
import { ChatProvider } from "@/lib/ChatContext";
import { Sidebar } from "@/components/Sidebar";
import { MobileNavBar } from "@/components/MobileNavBar";
import { MobileAppBar } from "@/components/MobileAppBar";
import { IngestTab } from "@/components/IngestTab";
import { CompileTab } from "@/components/CompileTab";
import { ChatTab } from "@/components/ChatTab";
import { ExplorerTab } from "@/components/ExplorerTab";
import { QualityTab } from "@/components/QualityTab";

const VIEW_TITLES: Record<View, string> = {
  explorer: "Explorer",
  chat: "Chat",
  ingest: "Ingest",
  compile: "Compile",
  quality: "Quality",
};

export default function HomePage() {
  const [activeView, setActiveView] = useState<View>("explorer");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Close mobile menu when view changes
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [activeView]);

  return (
    <StatusProvider>
      <CompileProvider>
        <ChatProvider>
          <div className="flex min-h-screen bg-zinc-100">
            {/* Desktop sidebar — hidden on mobile */}
            <div className="hidden md:block">
              <Sidebar activeView={activeView} onNavigate={setActiveView} />
            </div>

            {/* Mobile sidebar drawer — overlay when open */}
            <div
              className={`md:hidden fixed inset-0 z-50 transform transition-transform duration-200 ease-out ${
                mobileMenuOpen ? "translate-x-0" : "-translate-x-full"
              }`}
            >
              {/* Backdrop */}
              <div
                className="absolute inset-0 bg-black/40"
                onClick={() => setMobileMenuOpen(false)}
              />
              {/* Drawer */}
              <div className="relative h-full w-64 max-w-[80%]">
                <Sidebar
                  activeView={activeView}
                  onNavigate={setActiveView}
                />
              </div>
            </div>

            {/* Mobile app bar */}
            <MobileAppBar
              title={VIEW_TITLES[activeView]}
              onMenuClick={() => setMobileMenuOpen(true)}
            />

            <main
              className={`flex-1 transition-all duration-200 ease-out ${
                activeView === "explorer"
                  ? "pt-12 pb-16 md:pt-8 md:pb-0 md:p-8 overflow-y-auto"
                  : "pt-12 pb-16 md:py-8 md:px-8 overflow-y-auto"
              }`}
            >
              <div
                className={
                  activeView === "explorer"
                    ? "text-zinc-900"
                    : "max-w-5xl mx-auto text-zinc-900"
                }
              >
                <div key={activeView} className="animate-in fade-in duration-200">
                  {activeView === "ingest" && <IngestTab />}
                  {activeView === "compile" && <CompileTab />}
                  {activeView === "chat" && <ChatTab />}
                  {activeView === "explorer" && <ExplorerTab onNavigate={setActiveView} />}
                  {activeView === "quality" && <QualityTab />}
                </div>
              </div>
            </main>

            {/* Mobile bottom navigation */}
            <MobileNavBar activeView={activeView} onNavigate={setActiveView} />
          </div>
        </ChatProvider>
      </CompileProvider>
    </StatusProvider>
  );
}
