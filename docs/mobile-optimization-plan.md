# Mobile Optimization Plan for GSA-kb

## Research Summary

### Mobile Navigation Patterns (from top knowledge base apps)
1. **Bottom navigation bar** — 3-5 primary destinations, within thumb reach (Material Design / iOS tab bar)
2. **Hamburger/side drawer** — secondary navigation, space-efficient
3. **Floating Action Button (FAB)** — single primary action, always accessible
4. **Touch targets** — minimum 44px (iOS) / 48px (Android) for tap targets
5. **Adaptive layout** — sidebar on desktop, bottom nav on mobile (Material 3 adaptive navigation)

### Tailwind CSS Responsive Patterns
- Mobile-first breakpoints: `sm` (640px), `md` (768px), `lg` (1024px), `xl` (1280px), `2xl` (1536px)
- Use responsive prefixes: `md:flex-row`, `md:w-56`, etc.
- Touch-friendly padding: `p-4` minimum for tap targets
- Use `h-dvh` for mobile viewport units (avoids URL bar resize issues)
- Drawer/slider patterns with `transform translate-x-0/translate-x-full` and `transition-transform`

## Current Codebase Analysis

- **Root**: `page.tsx` — flexbox layout with `<Sidebar>` + `<main>`
- **Sidebar.tsx** — fixed 224px (w-56), collapsible, 5 nav items + status pills + refresh
- **ExplorerTab.tsx** — complex file explorer with graph view, list view, search, trash drawer
- No responsive utilities used anywhere — desktop-only design

## Mobile Pain Points
1. Sidebar takes 25%+ of screen width on mobile
2. No navigation accessible from main content area
3. Explorer toolbar has too many controls in a horizontal row
4. File list items are too small for touch (~40px height)
5. Sidebar status pills take vertical space

## Implementation Status

### Phase 1: ✅ Mobile-Responsive Layout Foundation (COMMITTED)
**Files**: `MobileNavBar.tsx` (NEW), `MobileAppBar.tsx` (NEW), `page.tsx`, `globals.css`, `layout.tsx`

1. **page.tsx**: Responsive layout with `hidden md:block` sidebar / `md:hidden` bottom nav
2. **Sidebar.tsx**: Unchanged (works as-is in desktop layout)
3. **MobileNavBar.tsx** (NEW): Bottom fixed nav bar with 5 tabs, `h-14` touch targets
4. **MobileAppBar.tsx** (NEW): Top app bar with hamburger menu (mobile only)
5. **globals.css**: Added `dvh` viewport units, `safe-area-inset` CSS, `touch-action`
6. **layout.tsx**: Added `viewport` export for proper mobile rendering

### Phase 2: ✅ Explorer Tab Mobile Optimizations (COMMITTED)
**File**: `ExplorerTab.tsx`

1. **Toolbar**: `flex-wrap` command bar that wraps on mobile (`md:flex-nowrap`)
2. **Search**: Full width on mobile (`w-full md:w-64`), taller input (`h-9 md:h-8`)
3. **Actions**: Larger touch targets (`h-9 md:h-8` for buttons)
4. **File list**: `py-2.5 md:py-2` for appropriate padding

### Phase 3: ✅ Other Tabs Mobile Optimizations (COMMITTED)
**Files**: `ChatTab.tsx`, `CompileTab.tsx`, `IngestTab.tsx`, `QualityTab.tsx`, `shared.tsx`

1. **ChatTab**: HistoryRail hidden on mobile (`hidden md:block`), flex-col on mobile
2. **CompileTab**: `grid-cols-1 md:grid-cols-3`, checkboxes wrap on small screens
3. **IngestTab**: Sub-tabs scrollable on mobile (`overflow-x-auto`), PDF options stack
4. **QualityTab**: Health check controls wrap on small screens
5. **shared.tsx (SectionCard)**: `p-4 md:p-6` for responsive padding

### Phase 4: ✅ Viewport & Meta (COMMITTED)
- Added `viewport` export in `layout.tsx`
- Verified page loads with no JS errors

## Remaining Work

### Future Enhancements (not implemented)
- Touch action CSS on interactive elements (prevent double-tap zoom)
- Swipe gestures between explorer files
- Bottom sheet for graph settings panel
- Offline PWA support

## Git History
All changes committed on branch `feature/mobile-optimization`:
- `12a2ab2` — Initial mobile optimization (Phase 1)
- `71662e3` — Phase 1 & 2 commit
- `dca22ab` — Phase 3: Mobile-responsive Chat, Compile, Ingest tabs
- `254711b` — Phase 4: Mobile-responsive QualityTab
- `e36cf0d` — Add mobile viewport meta for proper mobile rendering