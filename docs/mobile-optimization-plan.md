# Mobile Optimization Plan for GSA-kb

## Research Summary

### Mobile Navigation Patterns (from top knowledge base apps)
1. **Bottom navigation bar** — 3-5 primary destinations, within thumb reach (Material Design / iOS tab bar)
2. **Hamburger/side drawer** — secondary navigation, space-efficient
3. **Floating Action Button (FAB)** — single primary action, always accessible
4. **Swipe gestures** — common in note-taking (swipe to reveal actions, swipe between tabs)
5. **Touch targets** — minimum 44px (iOS) / 48px (Android) for tap targets
6. **Adaptive layout** — sidebar on desktop, bottom nav on mobile (Material 3 adaptive navigation)

### Tailwind CSS Responsive Patterns
- Mobile-first breakpoints: `sm` (640px), `md` (768px), `lg` (1024px), `xl` (1280px), `2xl` (1536px)
- Use responsive prefixes: `md:flex-row`, `md:w-56`, etc.
- Touch-friendly padding: `p-4` minimum for tap targets
- Use `min-h-screen`, `h-dvh` for mobile viewport units
- Drawer/slider patterns with `transform translate-x-0/translate-x-full` and `transition-transform`

## Current Codebase Analysis

### Architecture
- **Root**: `page.tsx` — flexbox layout with `<Sidebar>` + `<main>`
- **Sidebar.tsx** — fixed 224px (w-56), collapsible, 5 nav items + status pills + refresh
- **page.tsx** — wraps tabs in `max-w-5xl mx-auto` for non-explorer views
- **ExplorerTab.tsx** (1079 lines) — complex file explorer with graph view, list view, search, trash drawer
- **WikiGraph.tsx** — canvas-based graph, 938+ lines
- **ChatTab.tsx** — chat interface with message history
- No responsive utilities used anywhere — desktop-only design

### Mobile Pain Points
1. Sidebar takes 25%+ of screen width on mobile
2. No navigation accessible from main content area
3. Explorer toolbar has too many controls in a horizontal row
4. Graph canvas is difficult to navigate on touch
5. File list items may be too small for touch
6. Sidebar status pills take vertical space that could be used for content

## Implementation Plan

### Phase 1: Mobile-Responsive Layout Foundation
**Files**: `page.tsx`, `Sidebar.tsx`, `globals.css`

1. **page.tsx**: Make layout responsive
   - Desktop: sidebar + main (current behavior)
   - Mobile (`md:hidden`): hide sidebar, show bottom nav
   - Add a top app bar on mobile with hamburger menu icon

2. **Sidebar.tsx**: Make responsive
   - Desktop: keep current design (`md:flex`)
   - Mobile: transform into a slide-over drawer (`md:hidden fixed inset-y-0 left-0 z-50`)
   - Add overlay backdrop when drawer is open
   - Drawer slides in with `transform -translate-x-full → translate-x-0`

3. **Add MobileNavBar component** (new file)
   - Bottom fixed bar with 5 icons: Explorer, Chat, Ingest, Compile, Quality
   - Uses `fixed bottom-0 left-0 right-0 bg-zinc-900 text-zinc-100`
   - Touch targets: `h-14` minimum, icons `w-5 h-5`
   - Active state with violet accent
   - Shows on `md:hidden`, hidden on desktop

4. **Add MobileAppBar component** (new file)
   - Top fixed bar on mobile only (`md:hidden`)
   - Shows app title + hamburger menu button
   - Hamburger opens the sidebar drawer

### Phase 2: Explorer Tab Mobile Optimizations
**File**: `ExplorerTab.tsx`

1. **Toolbar**: Stack controls vertically on mobile
   - Desktop: horizontal row of category tabs, view toggles, search, actions
   - Mobile: 
     - Category tabs: horizontal scrollable overflow-x-auto
     - Search: full width below category tabs
     - Actions: icon-only buttons in a compact row

2. **File list**: Optimize for touch
   - Increase `min-h-12` for file rows (vs current ~40px)
   - Larger font size on mobile (`text-sm` → `text-base` on mobile)
   - Add more vertical padding

3. **Graph view**: Touch-friendly controls
   - Move zoom/fit controls to bottom-right corner
   - Larger button sizes (`h-10 w-10` on mobile)
   - Settings panel as a bottom sheet instead of side panel

### Phase 3: Other Tabs Mobile Optimizations
**Files**: `ChatTab.tsx`, `CompileTab.tsx`, `IngestTab.tsx`, `QualityTab.tsx`, `shared.tsx`

1. **ChatTab**: 
   - Full-width message input at bottom
   - Larger tap targets for send/stop buttons
   - Collapsible history rail on mobile

2. **CompileTab**:
   - Stack model select and options vertically
   - Full-width action buttons
   - Larger compile output area

3. **IngestTab**: 
   - Tabbed interface for URL/path/upload modes
   - Full-width input fields

4. **shared.tsx (SectionCard)**:
   - Reduced padding on mobile (`p-4` instead of `p-6`)
   - Responsive grid for two-column inputs

### Phase 4: Mobile-Specific Enhancements

1. **Viewport meta tag** — already in layout.tsx, verify
2. **Touch action CSS** — prevent double-tap zoom on interactive elements
3. **Mobile-friendly forms** — ensure inputs have proper `type` attributes
4. **Gesture support** — swipe between wiki files (optional, future phase)

## Implementation Order

1. Create `MobileNavBar.tsx` — bottom navigation
2. Create `MobileAppBar.tsx` — top app bar with hamburger
3. Update `page.tsx` — integrate mobile nav, responsive layout
4. Update `Sidebar.tsx` — drawer mode for mobile
5. Update `ExplorerTab.tsx` — mobile toolbar and file list
6. Update `ChatTab.tsx` — mobile chat layout
7. Update `CompileTab.tsx`, `IngestTab.tsx`, `QualityTab.tsx` — responsive cards
8. Update `shared.tsx` — responsive SectionCard
9. Update `globals.css` — mobile viewport units, touch actions
10. Test on mobile browser

## Files to Create
- `frontend/src/components/MobileNavBar.tsx`
- `frontend/src/components/MobileAppBar.tsx`

## Files to Modify
- `frontend/src/app/page.tsx`
- `frontend/src/components/Sidebar.tsx`
- `frontend/src/components/ExplorerTab.tsx`
- `frontend/src/components/ChatTab.tsx`
- `frontend/src/components/CompileTab.tsx`
- `frontend/src/components/IngestTab.tsx`
- `frontend/src/components/QualityTab.tsx`
- `frontend/src/components/shared.tsx`
- `frontend/src/app/globals.css`
- `frontend/tailwind.config.js` (if custom breakpoints needed)
