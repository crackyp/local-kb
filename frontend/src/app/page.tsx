"use client";

import { useState } from "react";
import type { View } from "@/types";
import { StatusProvider } from "@/lib/StatusContext";
import { CompileProvider } from "@/lib/CompileContext";
import { ChatProvider } from "@/lib/ChatContext";
import { Sidebar } from "@/components/Sidebar";
import { IngestTab } from "@/components/IngestTab";
import { CompileTab } from "@/components/CompileTab";
import { ChatTab } from "@/components/ChatTab";
import { ExplorerTab } from "@/components/ExplorerTab";
import { QualityTab } from "@/components/QualityTab";

export default function HomePage() {
  const [activeView, setActiveView] = useState<View>("explorer");

  return (
    <StatusProvider>
      <CompileProvider>
        <ChatProvider>
          <div className="flex min-h-screen bg-zinc-100">
            <Sidebar activeView={activeView} onNavigate={setActiveView} />
            <main className="flex-1 p-8 overflow-y-auto">
              <div className="max-w-5xl mx-auto text-zinc-900">
                <div key={activeView} className="animate-in fade-in duration-200">
                  {activeView === "ingest" && <IngestTab />}
                  {activeView === "compile" && <CompileTab />}
                  {activeView === "chat" && <ChatTab />}
                  {activeView === "explorer" && <ExplorerTab onNavigate={setActiveView} />}
                  {activeView === "quality" && <QualityTab />}
                </div>
              </div>
            </main>
          </div>
        </ChatProvider>
      </CompileProvider>
    </StatusProvider>
  );
}
