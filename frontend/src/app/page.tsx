"use client";

import { useState } from "react";
import type { View } from "@/types";
import { Sidebar } from "@/components/Sidebar";
import { IngestTab } from "@/components/IngestTab";
import { CompileTab } from "@/components/CompileTab";
import { AskTab } from "@/components/AskTab";
import { ExplorerTab } from "@/components/ExplorerTab";
import { LintTab } from "@/components/LintTab";

export default function HomePage() {
  const [activeView, setActiveView] = useState<View>("explorer");

  return (
    <div className="flex min-h-screen bg-slate-100">
      <Sidebar activeView={activeView} onNavigate={setActiveView} />
      <main className="flex-1 p-8 overflow-y-auto">
        <div className="max-w-5xl mx-auto text-slate-900">
          {activeView === "ingest" && <IngestTab />}
          {activeView === "compile" && <CompileTab />}
          {activeView === "ask" && <AskTab />}
          {activeView === "explorer" && <ExplorerTab />}
          {activeView === "lint" && <LintTab />}
        </div>
      </main>
    </div>
  );
}
