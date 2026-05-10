---
id: H001
salience: 0.9
target: semantic
source: brain-learn
source_ref: ~/Khaan/brain/docs/brain.html
created: 2026-05-10
---
v2 uses level-encoded IDs: S1-### (L1), S2-### (L2), S3-### (L3). Current v1 uses flat S### / E### / PR### without level encoding. Same pattern for all regions. v2 L1->L2->L3 promotion is synthesis (produces NEW content from clusters), not file moves. Source L1s archived to cortex/archive/<region>/L1/.

---
id: H002
salience: 0.8
target: semantic
source: brain-learn
source_ref: ~/Khaan/brain/docs/brain.html
created: 2026-05-10
---
v2 Fusiform region (cortex/fusiform/L<n>/FUS###.md) gives people their own decay/reinforcement lifecycle. Entries hold: identity, view/stance, contact channels, interaction patterns, decisions. Levels: FUS1 first impression -> FUS4 inner circle. v2 renames identity entries: og-identity -> ID###, og-broca -> BR###, og-amygdala -> AM###. Broca becomes "emotional event chains" not just style.

---
id: H003
salience: 1.0
target: semantic
source: brain-learn
source_ref: ~/Khaan/brain/docs/identity-engine.html
created: 2026-05-10
---
v2 boot output: prose sections only (Identity/Voice/Charges) as additionalContext. YAML frontmatter with kernel_entries is diagnostic/file-only. Boot scoring: level_bonus (L4 +5.0 dominates), recency_bonus (+1.0 within 5 cycles), strength_bonus (+0.3/point, cap 2.0). Relay adds relevance_bonus (+2.0 overlap >= 0.25) and charge_bonus (+1.0 amygdala subject matches person in message via FUS lookup).

---
id: H004
salience: 1.0
target: procedural
source: brain-learn
source_ref: ~/Khaan/brain/docs/rule-engine.html
created: 2026-05-10
---
v2 cycle gate bypass spec: only /brain-cycle skill or python3 -m engines.brain_cycle. Current v1 uses substring "brain_cycle" in cmd which is exploitable (put it in a comment). Exploited during 2026-05-10 session. Fix: proper regex or exempt only the Skill tool.

---
id: H005
salience: 0.9
target: semantic
source: brain-learn
source_ref: ~/Khaan/brain/docs/handler.html
created: 2026-05-10
---
v2 repo layout: wiring/ directory (hook.py, CLAUDE.md, settings.json, skills/) + brain/ directory. setup.sh creates symlinks. Switching brains = re-run setup.sh from different repo. Bypass via HMAC token from Lambda, consumed by flip_bypass.py::consume(). Secret at ~/.claude/.bypass.secret (mode 0400, outside brain/).

---
id: H006
salience: 0.9
target: semantic
source: brain-learn
source_ref: ~/Khaan/brain/docs/recall-engine.html
created: 2026-05-10
---
v2 recall: 5 regions (semantic, episodic, procedural, fusiform, prefrontal -- NOT identity/broca/amygdala). Score floor 2.0. 7 signals: domain (+3), type (+1.5), level (L1+0.5/L2+1.5/L3+3.0), lex (IDF, cap 4), co_ref (+2), bundle (+1.5), reuse (cap 2). 5-stage pipeline: NORMALIZE -> DOMAIN -> SCORE -> RERANK -> HANDOFF. Rerank: specificity, diversity (-1 per dup), temporal. Graph expansion 1-hop at 50%.

---
id: H007
salience: 0.9
target: episodic
source: brain-learn
source_ref: audit-session-2026-05-10
created: 2026-05-10
---
Full audit 2026-05-10: 8 UNKNOWN deviations found. U1: gate bypass exploitable (substring match). U2: boot kernel blob in context (FIXED). U3: identity-relay-timeout stuck at 1. U4: flip_bypass.py dead code. U5: time.mktime on UTC strings. U6: ENGINE_REDIRECT_RE misses nested paths. U7: stemming not implemented. U8: /brain-cycle blocked by its own gate (circular dependency). Structural audit: all 8 cortex regions, 23 binaries, 5 skills, 8 cycle phases match spec.

---
id: H008
salience: 0.7
target: semantic
source: brain-learn
source_ref: ~/Khaan/brain/docs/learning-engine.html + skills.html
created: 2026-05-10
---
v2 brain cycle: 8 phases (ingest, hippo, consolidate, index, synthesis, eval, hygiene, commit). Phase 5 synthesis clusters L1s at strength>=5 -> new L2, L2s at strength>=8 -> new L3. Sources archived. 6 invariants at commit. Skills: Brain Retro (session sweep), Brain Learn (external source), Brain Correct (immediate correction). All run as subagents with SubagentStop verification.
