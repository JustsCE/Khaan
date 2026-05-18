# PROJECT: Simplify Mobile View — goodhealth.lv/brain + /dashboard

## Draft 1 — 2026-04-24

### Objective
Make both routes (goodhealth.lv/brain and goodhealth.lv/dashboard) fully usable on mobile. Currently, the desktop layout is the primary design — mobile components exist but Justs reports they're not working properly.

### Approach
Audit both pages on a mobile viewport (375px and 390px widths), identify layout breaks, unresponsive elements, and UX friction. Fix iteratively — simplify rather than redesign.

### Requirements & Access
- viz/ frontend codebase (available in claude-brain repo)
- Dev server (npm run dev on port 5173)
- Deploy via `cd viz && bash deploy.sh` or SSH to goodhealth.lv
- PEM_KEY env var for deployment

### Steps
1. **Audit BrainPage mobile** — Start dev server, test at 375px. Document: broken layouts, touch issues, Three.js canvas overflow, pane overlap, text truncation, bottom sheet behavior
2. **Audit DashboardPage mobile** — Same viewport test. Document: MobileDashboard component, circle buttons reachability, bottom sheet scrolling, task card sizing, digest feed usability
3. **Fix BrainPage mobile** — Priority issues first: canvas sizing, HUD readability, floating pane overlap, toolbar/inspector touch targets
4. **Fix DashboardPage mobile** — Bottom sheet improvements, task card layout, source filter usability, safe area compliance
5. **Deploy + verify on real device** — Deploy to goodhealth.lv, test on actual phone

### Follow-up Questions (self-generated)
- [ ] What specific issues is Justs seeing? (he said "not working" — need to reproduce)
- [ ] Are both /brain and /dashboard equally broken, or is one worse?
- [ ] Is the PWA install prompt working on mobile?
- [ ] Should mobile be simplified further (e.g., skip Three.js on low-end devices)?

### Risk Assessment
- Three.js on mobile is inherently heavy — may need to reduce neuron count or disable effects
- Touch interactions (drag-and-drop for tasks) may need mobile-specific gesture handling
- Safe area insets on notch phones need testing

### Estimated Effort
2-3 solo-time runs for audit + fix + deploy
