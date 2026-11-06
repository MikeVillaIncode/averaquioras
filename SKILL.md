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
7. Run `~/.claude/skills/averaquioras/scripts/run.sh ~/.claude/averaquioras/<slug>/config.json`
   (it stops a previous instance of the same config first). Tell the user, in their language: the widget
   is top-right, drag to move, × closes, it refreshes every N minutes, the page link
   (`file://…/<slug>/index.html`), and how to reopen (`run.sh` with the same config) or stop (`stop.sh`).
8. If the job's plan changes (steps added, relaunched agents), edit the config and run `run.sh` again.

## Rules

- Only one widget window per config; `run.sh` replaces the previous one. The window remembers where the user leaves it (any display) in `widget-bounds.json`; never reposition it yourself.
- Stop processes by PID (the scripts do), never with `pkill -f`.
- The estimate is an estimate: say so to the user; never present it as exact.
- Colours and type follow the Incode design canon (DM Sans, #0054FF, the UI greys); don't restyle ad hoc.
