---
name: averaquioras
description: Floating desktop progress widget (Electron, always on top) plus a browser page that show a long-running job's overall % with a progress bar, the estimated time left, and one bar per step with its state. Use when the user asks for a progress widget, a progress bar, "cuánto falta", "cómo vamos" as something visual, or wants to watch background agents/workflows/builds/test runs. Triggers: '/averaquioras', 'a ver a qué horas', 'progress widget', 'widget de progreso', 'barra de progreso', 'cuánto falta', 'ver el progreso', 'progreso visual'.
---

# A ver a qué horas (progress widget)

Shows the progress of work that runs in the background (agents, workflows, builds, test suites, captures)
as a small floating window in the top-right corner of the screen (always on top, on every desktop) and as
a browser page. It refreshes on its own (default every 5 minutes).

## How it works

`scripts/progress.py <config.json>` loops: it reads **observable signals only** (files that appear when a
step finishes, a file count, git commits) and writes `widget.html` and `index.html` next to the config.
Each step has an expected duration; a step's progress is the time spent in it against that estimate,
capped at 95 % until its done-signal appears, so the estimate self-corrects as steps finish.
`scripts/run.sh <config.json>` starts the loop and the Electron window (Electron is installed once into
`widget/node_modules` the first time). `scripts/stop.sh <config.json>` stops both (by PID files).

## What you do when the skill is invoked

1. Identify the job and its steps: the running workflow's phases / agents, the pipeline you launched, or
   the user's described task. Pick 3 to 8 steps the user understands (their language, short titles).
2. For each step choose a **done-signal** that you know will appear when it finishes, in this order of
   preference: a report file the agent writes (`{"file": "/abs/path.md"}`), a glob that starts matching
   (`{"glob": "/abs/dir/**/*.json"}`), or a shell command that exits 0 (`{"command": "test -f …"}`).
   Never a signal that needs the network or secrets.
3. Estimate minutes per step honestly (from similar past steps if you have them).
4. Optional per step `count`: `{"glob": "/abs/shots/<step>/**/*.png", "label": "capturas"}`; optional
   top-level `commits`: `{"repo": "/abs/repo", "range": "<base>..<branch>"}` to list recent commits on the page.
5. **Language.** The widget and the page carry both English and Spanish and have an EN/ES switch at the
   bottom right. `lang` in the config is the default; once the user clicks EN or ES, that choice sticks for
   every widget and page. Any text in the config (`title`, a step's `title`, a count's `label`) can be a
   plain string or `{"en": "...", "es": "..."}`; give both when the user may switch.
6. Write the config to `~/.claude/averaquioras/<slug>/config.json` (slug: short kebab name of the job):

```json
{
  "title": {"es": "Ronda de revisión 1 · rama del PR", "en": "Review round 1 · PR branch"},
  "lang": "es",
  "start": 1793891925,
  "refreshSeconds": 300,
  "steps": [
    {"key": "layout", "title": {"es": "Fondo gris, menús y tablas", "en": "Grey background, menus and tables"}, "minutes": 75,
     "done": {"file": "/abs/.context/orchestration/review1-layout.md"},
     "count": {"glob": "/abs/wt/_pe/review1/layout/**/*.png", "label": "capturas"}}
  ],
  "commits": {"repo": "/abs/repo", "range": "39d5d859..MikeVillaIncode/prizma-enterprise"}
}
```

   `start` is the epoch second the job started (e.g. `stat -f %SB -t %s <dir the job created>` or now).

   **Sequential, parallel and nested.** By default steps run one after another. Add `"mode": "parallel"`
   (or `"parallel": true`) to run them at the same time. Any step can instead be a **group**: a `title`, an
   optional `mode`, and its own `steps` (no `minutes` or `done`: a group is done when all its steps are).
   Nest as deep as the job: parallel agents, each with sequential or parallel tasks, then a final step.
   Sequential children start when the previous one is done; parallel children all start with their group.
   Time left adds up sequential parts and takes the longest of parallel ones; the overall % weighs every
   leaf step by its minutes. Group rows show "N of M done · in parallel / in order" with their children
   indented under them.

```json
{
  "title": {"es": "Capturas del rediseño", "en": "Redesign screenshots"},
  "start": 1793891925,
  "steps": [
    {"title": {"es": "Agentes", "en": "Agents"}, "mode": "parallel", "steps": [
      {"title": "Agente A · copy", "steps": [
        {"key": "a1", "title": "Borrador", "minutes": 15, "done": {"file": "/abs/.context/a-draft.md"}},
        {"key": "a2", "title": "Revisión", "minutes": 30, "done": {"file": "/abs/.context/a-review.md"}}]},
      {"title": "Agente B · capturas", "mode": "parallel", "steps": [
        {"key": "b1", "title": "Escritorio", "minutes": 20, "done": {"glob": "/abs/shots/desktop/*.png"}},
        {"key": "b2", "title": "Móvil", "minutes": 25, "done": {"glob": "/abs/shots/mobile/*.png"}}]}]},
    {"key": "final", "title": "Integrar y revisar", "minutes": 15, "done": {"file": "/abs/.context/final.md"}}
  ]
}
```
7. Run `~/.claude/skills/averaquioras/scripts/run.sh ~/.claude/averaquioras/<slug>/config.json`
   (it stops a previous instance of the same config first). Tell the user, in their language: the widget
   is top-right, drag to move, × closes, it refreshes every N minutes, the page link
   (`file://…/<slug>/index.html`), and how to reopen (`run.sh` with the same config) or stop (`stop.sh`).
8. If the job's plan changes (steps added, relaunched agents), edit the config and run `run.sh` again.

## Rules

- Launch `run.sh` **outside the command sandbox** (in Claude Code: `dangerouslyDisableSandbox: true`). A sandboxed shell kills the Electron window as soon as the command ends, so the widget flashes and disappears. Check it survived with `ps -p $(cat <dir>/widget.pid)` in a later call.
- Only one widget window per config; `run.sh` replaces the previous one. The window remembers where the user leaves it (any display) and the size they give it in `widget-bounds.json`; never reposition or resize it yourself.
- **Size and scroll.** The window grows with the card up to 520 px tall by default; past that the step list scrolls inside the card while the title, overall % and footer stay put (the scroll position survives each refresh). The user resizes it from the bottom-right corner (320–720 px wide); the height they leave becomes the new cap. Tell the user about the corner when the job has many steps.
- Stop processes by PID (the scripts do), never with `pkill -f`.
- The estimate is an estimate: say so to the user; never present it as exact.
- Colours and type follow the Incode design canon (DM Sans, #0054FF, the UI greys); don't restyle ad hoc.
