"""Progress widget generator: reads a config of steps with done-signals and writes widget.html and
index.html next to it, every refreshSeconds, until every step is done. See ../SKILL.md."""
import glob, html, json, os, pathlib, subprocess, sys, time

CFG_PATH = pathlib.Path(sys.argv[1]).expanduser().resolve()
OUTDIR = CFG_PATH.parent

T = {
    'es': dict(done='Terminado', now='En curso', todo='Pendiente', left='faltan aprox.', ready='Listo',
               step='Paso {i} de {n}', every='se actualiza cada {m} min', last='última actualización {t}', elapsed='Llevamos {t}.',
               note='El tiempo restante es una estimación: cada paso tiene una duración esperada y se ajusta cuando termina.',
               commits='Últimos commits', nocommits='Todavía sin commits nuevos.', close='Cerrar',
               of='{d} de {n} terminados', par='en paralelo', seq='en orden', resize='Cambiar tamaño'),
    'en': dict(done='Done', now='In progress', todo='Pending', left='about', ready='Done',
               step='Step {i} of {n}', every='refreshes every {m} min', last='last updated {t}', elapsed='Elapsed: {t}.',
               note='Time left is an estimate: each step has an expected duration and it adjusts when a step ends.',
               commits='Latest commits', nocommits='No new commits yet.', close='Close',
               of='{d} of {n} done', par='in parallel', seq='in order', resize='Resize'),
}


def load():
    return json.loads(CFG_PATH.read_text())


def signal_time(sig):
    """Epoch when the done-signal appeared, or None."""
    if not sig:
        return None
    if 'file' in sig:
        p = pathlib.Path(sig['file']).expanduser()
        return p.stat().st_mtime if p.exists() else None
    if 'glob' in sig:
        hits = glob.glob(os.path.expanduser(sig['glob']), recursive=True)
        return min(os.stat(h).st_mtime for h in hits) if hits else None
    if 'command' in sig:
        try:
            ok = subprocess.run(sig['command'], shell=True, capture_output=True, timeout=20).returncode == 0
        except Exception:
            ok = False
        return time.time() if ok else None
    return None


def count(c):
    if not c:
        return 0
    return len(glob.glob(os.path.expanduser(c['glob']), recursive=True))


def commits(c):
    if not c:
        return []
    try:
        out = subprocess.run(['git', '-C', os.path.expanduser(c['repo']), 'log', '--format=%s', c['range']],
                             capture_output=True, text=True, timeout=10).stdout
        return [l for l in out.splitlines() if l]
    except Exception:
        return []


def fmt(minutes):
    h, m = divmod(int(round(minutes)), 60)
    return f'{h} h {m:02d} min' if h else f'{m} min'


def tr(v, lang):
    """A config text is a plain string or {"es": ..., "en": ...}; pick the language, fall back to any."""
    if isinstance(v, dict):
        return v.get(lang) or next(iter(v.values()), '')
    return v or ''


def mode(node):
    """'parallel' when the node says so ("mode": "parallel" or "parallel": true); otherwise sequential."""
    return 'parallel' if node.get('mode') == 'parallel' or node.get('parallel') is True else 'sequential'


def work(node):
    """Total expected minutes of work under a node (drives the overall %)."""
    return sum(work(c) for c in node['steps']) if 'steps' in node else node['minutes']


def evaluate(node, t0, active, now):
    """Progress of a step or a group that may start at t0 (only when active).
    A step is a leaf with minutes + done; a group has steps and a mode. Sequential children start when
    the previous one is done; parallel children all start with their group, at any nesting depth.
    Returns (row, done_minutes, minutes_left, end_epoch_or_None)."""
    if 'steps' not in node:
        m = node['minutes']
        row = dict(title=node['title'], n=count(node.get('count')),
                   lb=node.get('count', {}).get('label', ''), kids=None)
        end = signal_time(node.get('done')) if active else None
        if end is not None:
            row.update(frac=1.0, state='done')
            return row, m, 0.0, max(t0, end)
        if active:
            frac = min(0.95, max(0.0, (now - t0) / (m * 60)))
            row.update(frac=frac, state='now')
            return row, m * frac, max(5, m * (1 - frac)), None
        row.update(frac=0.0, state='todo')
        return row, 0.0, float(m), None
    par = mode(node) == 'parallel'
    kids, done_w, lefts, ends, t, chain = [], 0.0, [], [], t0, active
    for c in node['steps']:
        r, d, l, e = evaluate(c, t0 if par else t, active if par else chain, now)
        kids.append(r); done_w += d; lefts.append(l); ends.append(e)
        if not par:
            if chain and e is not None:
                t = max(t, e)
            else:
                chain = False
    finished = active and all(e is not None for e in ends)
    row = dict(title=node.get('title', ''), n=0, lb='', kids=kids, parallel=par,
               frac=1.0 if finished else done_w / (work(node) or 1),
               state='done' if finished else ('now' if active else 'todo'),
               done_count=sum(1 for e in ends if e is not None), count_all=len(ends))
    left = 0.0 if finished else ((max(lefts) if par else sum(lefts)) if lefts else 0.0)
    return row, done_w, left, (max(ends) if finished and ends else None)


def snapshot(cfg):
    """Overall fraction, minutes left, the row tree, minutes elapsed, finished?"""
    now = time.time(); start = cfg.get('start', now)
    row, done_w, left, end = evaluate(cfg, start, True, now)
    finished = end is not None
    pct = 1.0 if finished else done_w / (work(cfg) or 1)
    return pct, (0 if finished else left), row['kids'], (now - start) / 60, finished


CSS = """html,body{margin:0;font-family:'DM Sans',system-ui,sans-serif}
.bar{height:10px;border-radius:9999px;background:#EBECEF;overflow:hidden}.bar span{display:block;height:100%;background:#0054FF;border-radius:9999px}
.st{flex-shrink:0;font-size:11px;padding:2px 8px;border-radius:9999px;background:#EBECEF;color:#6E758C}
.st-done{background:#E4FBF0;color:#189F60}.st-now{background:#E5F0FF;color:#0054FF}
ul.sub{list-style:none;margin:8px 0 0 4px;padding:0 0 0 12px;border-left:1px solid #EBECEF}
[hidden]{display:none!important}
.lg{display:inline-flex;flex-shrink:0;padding:2px;border-radius:9999px;background:#EBECEF}
.lg button{border:0;margin:0;padding:2px 8px;border-radius:9999px;background:transparent;color:#6E758C;font:500 11px/16px 'DM Sans',system-ui,sans-serif;cursor:pointer}
.lg button[aria-pressed=true]{background:#FFFFFF;color:#262831;box-shadow:0 1px 3px rgba(50, 50, 93, 0.08), 0 1px 0 rgba(0, 0, 0, 0.03)}
.lg button:focus-visible{outline:2px solid #0054FF;outline-offset:1px}"""
FONT = '<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500&display=swap" rel="stylesheet">'
LANGS = ('en', 'es')
# Canonical drag-handle icon (incode-design icons bank, verbatim) for the widget's resize corner.
GRIP = ('<svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor" xmlns="http://www.w3.org/2000/svg">\n'
        '<circle cx="7.5" cy="5" r="1.3"/><circle cx="12.5" cy="5" r="1.3"/><circle cx="7.5" cy="10" r="1.3"/>'
        '<circle cx="12.5" cy="10" r="1.3"/><circle cx="7.5" cy="15" r="1.3"/><circle cx="12.5" cy="15" r="1.3"/>\n</svg>')
# The widget reports its card's full height (as if the step list did not scroll) in the page title; the
# Electron window sizes itself to that, up to its height cap, and the list scrolls past it.
FIT = ("try{var w=document.getElementById('w'),u=document.querySelector('[data-lang]:not([hidden]) ul.steps'),"
       "x=u?u.scrollHeight-u.clientHeight:0;document.title=String(Math.ceil(w.getBoundingClientRect().bottom+8+x));}catch(e){}")


def lang_switch():
    return ('<span class="lg" role="group" aria-label="Language / Idioma">'
            + ''.join(f'<button type="button" data-set="{l}" aria-pressed="false">{l.upper()}</button>' for l in LANGS)
            + '</span>')


def lang_script(default, fit):
    """The config's lang until the user clicks EN/ES; that click then applies to every widget and page
    (localStorage is shared per file:// origin)."""
    return f"""<script>(function(){{var K='averaquioras-lang';var l;try{{l=localStorage.getItem(K)}}catch(e){{}}
if(['en','es'].indexOf(l)<0)l='{default}';
function fit(){{{fit}}}
function set(x,save){{l=x;if(save){{try{{localStorage.setItem(K,x)}}catch(e){{}}}}document.documentElement.lang=x;
document.querySelectorAll('[data-lang]').forEach(function(e){{e.hidden=e.getAttribute('data-lang')!==x}});
document.querySelectorAll('.lg button').forEach(function(b){{b.setAttribute('aria-pressed',String(b.getAttribute('data-set')===x))}});fit();}}
document.querySelectorAll('.lg button').forEach(function(b){{b.addEventListener('click',function(){{set(b.getAttribute('data-set'),true)}})}});
set(l);}})();</script>"""


def write(cfg):
    default = cfg.get('lang', 'es') if cfg.get('lang') in LANGS else 'es'
    pct, left, rows, elapsed, finished = snapshot(cfg)
    mins = max(1, int(cfg.get('refreshSeconds', 300) // 60))
    refresh = int(cfg.get('refreshSeconds', 300))
    stamp = time.strftime('%H:%M')

    def parts(lang):
        L = T[lang]
        when = L['ready'] if finished else f"{L['left']} {fmt(left)}"
        def item(r):
            f = r['frac']
            if r['kids'] is None:
                meta = f'{f*100:.0f}%' + (f" · {r['n']} {html.escape(tr(r['lb'], lang))}" if r['n'] else '')
                sub = ''
            else:
                meta = (f"{f*100:.0f}% · {L['of'].format(d=r['done_count'], n=r['count_all'])}"
                        f" · {L['par'] if r['parallel'] else L['seq']}")
                sub = f'<ul class="sub">{"".join(item(k) for k in r["kids"])}</ul>'
            return (f'<li><div class="sr"><span class="sn">{html.escape(tr(r["title"], lang))}</span>'
                    f'<span class="st st-{r["state"]}">{L[r["state"]]}</span></div>'
                    f'<div class="bar sm"><span style="width:{f*100:.0f}%"></span></div>'
                    f'<div class="m">{meta}</div>{sub}</li>')
        steps = ''.join(item(r) for r in rows)
        return L, html.escape(tr(cfg.get('title', 'Progress'), lang)), when, steps

    def hid(lang):
        return '' if lang == default else ' hidden'

    w_body, w_foot, p_body, p_note = '', '', '', ''
    for lang in LANGS:
        L, title, when, steps = parts(lang)
        w_body += (f'<div data-lang="{lang}"{hid(lang)}><div class="ttl" title="{title}">{title}</div>'
                   f'<div class="top"><span class="pct">{pct*100:.0f}%</span><span class="left">{when}</span></div>'
                   f'<div class="bar"><span style="width:{pct*100:.0f}%"></span></div><ul class="steps">{steps}</ul></div>')
        w_foot += (f'<span class="ft" data-lang="{lang}"{hid(lang)}>'
                   f"{L['every'].format(m=mins).capitalize()} · {L['last'].format(t=stamp)}</span>")
        p_body += (f'<div data-lang="{lang}"{hid(lang)}><h1>{title}</h1>'
                   f"<div class=\"m\">{L['every'].format(m=mins).capitalize()} · {L['last'].format(t=stamp)}. {L['elapsed'].format(t=fmt(elapsed))}</div>"
                   f'<div class="big"><span class="pct">{pct*100:.0f}%</span><span class="left">{when}</span></div>'
                   f'<div class="bar"><span style="width:{pct*100:.0f}%"></span></div><ul>{steps}</ul></div>')
        p_note += f'<span data-lang="{lang}"{hid(lang)}>{L["note"]}</span>'

    title0 = html.escape(tr(cfg.get('title', 'Progress'), default))
    close, resize = T[default]['close'], T[default]['resize']
    widget = f"""<!doctype html><html lang="{default}"><head><meta charset="utf-8"><meta http-equiv="refresh" content="{refresh}">{FONT}
<style>{CSS}
html,body{{background:transparent;overflow:hidden}}
.w{{position:relative;box-sizing:border-box;max-height:calc(100vh - 16px);display:flex;flex-direction:column;margin:8px;padding:16px;border-radius:16px;background:#FFFFFF;border:1px solid #EBECEF;box-shadow:0 6px 12px rgba(50, 50, 93, 0.11), 0 3px 6px rgba(0, 0, 0, 0.07);cursor:move;user-select:none;color:#3A3E4B}}
.w>[data-lang]{{display:flex;flex-direction:column;min-height:0;flex:1 1 auto}}.w>[data-lang]>:not(ul){{flex-shrink:0}}ul.steps{{overflow-y:auto;min-height:0;flex:1 1 auto}}.foot{{flex-shrink:0}}
.rz{{position:absolute;z-index:2;right:2px;bottom:2px;width:14px;height:14px;display:flex;color:#A3A8B8;cursor:nwse-resize}}.rz:hover{{color:#6E758C}}.rz svg{{width:14px;height:14px}}
.ttl{{margin:0 32px 6px 0;font-size:13px;font-weight:500;color:#262831;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.top{{display:flex;align-items:baseline;gap:10px}}.pct{{font-size:32px;font-weight:500;color:#262831;line-height:1.2}}.left{{font-size:13px;color:#6E758C}}
.bar.sm{{height:6px;margin:6px 0 2px}}[data-lang]>.bar{{margin:8px 0 4px}}
ul{{list-style:none;margin:12px 0 0;padding:0}}li{{margin:10px 0 0}}.sr{{display:flex;justify-content:space-between;align-items:center;gap:8px}}
.sn{{font-size:12px;font-weight:500;color:#262831;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.m{{font-size:11px;color:#6E758C}}
.foot{{margin-top:10px;display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:11px;color:#6E758C}}
.ft{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.x{{position:absolute;z-index:2;top:8px;right:8px;width:32px;height:32px;display:flex;align-items:center;justify-content:center;padding:0;border:0;border-radius:8px;background:transparent;color:#6E758C;font-size:18px;line-height:1;cursor:pointer}}.x:hover{{background:#F9F9F9;color:#3A3E4B}}
</style></head><body><div class="w" id="w"><button class="x" title="{close}" aria-label="{close}" onclick="window.avq?avq.close():window.close()">×</button>
{w_body}<div class="foot">{w_foot}{lang_switch()}</div><span class="rz" id="rz" title="{resize}" aria-label="{resize}">{GRIP}</span></div>
{lang_script(default, FIT)}
<script>(function(){{var w=document.getElementById('w'),a=window.avq,K='avq-scroll:'+location.pathname;
function list(){{return document.querySelector('[data-lang]:not([hidden]) ul.steps')}}
var l=list();try{{if(l)l.scrollTop=+sessionStorage.getItem(K)||0}}catch(e){{}}
document.querySelectorAll('ul.steps').forEach(function(u){{u.addEventListener('scroll',function(){{try{{sessionStorage.setItem(K,String(u.scrollTop))}}catch(e){{}}}})}});
w.addEventListener('mousedown',function(e){{if(e.button!==0||e.target.closest('button'))return;
if(e.target.closest('#rz')){{e.preventDefault();if(a)a.resizeStart();return;}}
var u=e.target.closest('ul.steps');if(u&&e.clientX>=u.getBoundingClientRect().left+u.clientWidth)return;
if(a)a.dragStart();}});
window.addEventListener('mouseup',function(){{if(a){{a.dragEnd();a.resizeEnd();}}}});
window.addEventListener('resize',function(){{{FIT}}});
document.addEventListener('keydown',function(e){{if(e.key==='Escape'){{if(a)a.close();else window.close();}}}});}})();</script>
</body></html>"""
    (OUTDIR / 'widget.html').write_text(widget)
    cs = commits(cfg.get('commits'))
    commits_card = ''
    if cfg.get('commits'):
        log = ''.join(f'<li>{html.escape(c)}</li>' for c in cs[:12])
        heads = ''.join(f'<h2 data-lang="{l}"{hid(l)}>{T[l]["commits"]}</h2>' for l in LANGS)
        empty = ''.join(f'<li class="m" data-lang="{l}"{hid(l)}>{T[l]["nocommits"]}</li>' for l in LANGS)
        commits_card = f'<div class="card">{heads}<ul class="log">{log or empty}</ul></div>'
    page = f"""<!doctype html><html lang="{default}"><head><meta charset="utf-8"><meta http-equiv="refresh" content="{refresh}">
<title>{pct*100:.0f}% · {title0}</title>{FONT}<style>{CSS}
body{{background:#F9F9F9;color:#3A3E4B}}.wrap{{max-width:720px;margin:48px auto;padding:0 24px}}
.card{{background:#FFFFFF;border:1px solid #EBECEF;border-radius:16px;padding:32px;box-shadow:0 6px 12px rgba(50, 50, 93, 0.11), 0 3px 6px rgba(0, 0, 0, 0.07);margin-bottom:24px}}
h1{{margin:0 0 4px;font-size:22px;font-weight:500;color:#262831}}h2{{font-size:16px;font-weight:500;margin:0 0 12px;color:#262831}}.m{{font-size:12px;color:#6E758C}}
.big{{display:flex;align-items:baseline;gap:16px;margin:24px 0 12px}}.pct{{font-size:48px;font-weight:500;color:#262831}}.left{{font-size:16px;color:#6E758C}}
[data-lang]>.bar{{height:14px}}ul{{list-style:none;margin:24px 0 0;padding:0}}li{{margin:16px 0}}.sr{{display:flex;justify-content:space-between;gap:12px;margin-bottom:6px;font-size:14px}}
.sn{{color:#262831;font-weight:500}}.st{{font-size:12px;padding:2px 10px}}.log li{{margin:6px 0;font-size:13px}}
.pf{{display:flex;align-items:center;justify-content:space-between;gap:16px}}
</style></head><body><div class="wrap"><div class="card">{p_body}</div>{commits_card}
<div class="pf"><span class="m">{p_note}</span>{lang_switch()}</div></div>
{lang_script(default, "")}</body></html>"""
    (OUTDIR / 'index.html').write_text(page)
    return finished


if __name__ == '__main__':
    while True:
        cfg = load()
        if write(cfg):
            break
        time.sleep(int(cfg.get('refreshSeconds', 300)))
