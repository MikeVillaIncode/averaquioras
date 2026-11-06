"""Progress widget generator: reads a config of steps with done-signals and writes widget.html and
index.html next to it, every refreshSeconds, until every step is done. See ../SKILL.md."""
import glob, html, json, os, pathlib, subprocess, sys, time

CFG_PATH = pathlib.Path(sys.argv[1]).expanduser().resolve()
OUTDIR = CFG_PATH.parent

T = {
    'es': dict(done='Terminado', now='En curso', todo='Pendiente', left='faltan aprox.', ready='Listo',
               step='Paso {i} de {n}', every='se actualiza cada {m} min', last='última actualización {t}', elapsed='Llevamos {t}.',
               note='El tiempo restante es una estimación: cada paso tiene una duración esperada y se ajusta cuando termina.',
               commits='Últimos commits', nocommits='Todavía sin commits nuevos.', close='Cerrar'),
    'en': dict(done='Done', now='In progress', todo='Pending', left='about', ready='Done',
               step='Step {i} of {n}', every='refreshes every {m} min', last='last updated {t}', elapsed='Elapsed: {t}.',
               note='Time left is an estimate: each step has an expected duration and it adjusts when a step ends.',
               commits='Latest commits', nocommits='No new commits yet.', close='Close'),
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


def snapshot(cfg):
    now = time.time(); t = cfg.get('start', now)
    steps = cfg['steps']; total = sum(s['minutes'] for s in steps) or 1
    rows, done_w, left, current = [], 0.0, 0.0, None
    for s in steps:
        end = signal_time(s.get('done'))
        n = count(s.get('count'))
        lb = s.get('count', {}).get('label', '')
        if end is not None and current is None:
            rows.append((s['title'], 1.0, 'done', n, lb))
            done_w += s['minutes']; t = max(t, end)
        elif current is None:
            frac = min(0.95, max(0.0, (now - t) / (s['minutes'] * 60)))
            current = s
            rows.append((s['title'], frac, 'now', n, lb))
            done_w += s['minutes'] * frac
            left += max(5, s['minutes'] * (1 - frac))
        else:
            rows.append((s['title'], 0.0, 'todo', n, lb))
            left += s['minutes']
    return done_w / total, (0 if current is None else left), rows, (now - cfg.get('start', now)) / 60


CSS = """html,body{margin:0;font-family:'DM Sans',system-ui,sans-serif}
.bar{height:10px;border-radius:9999px;background:#EBECEF;overflow:hidden}.bar span{display:block;height:100%;background:#0054FF;border-radius:9999px}
.st{flex-shrink:0;font-size:11px;padding:2px 8px;border-radius:9999px;background:#EBECEF;color:#6E758C}
.st-done{background:#E8F5EE;color:#128050}.st-now{background:#E5F0FF;color:#0054FF}
[hidden]{display:none!important}
.lg{display:inline-flex;flex-shrink:0;padding:2px;border-radius:9999px;background:#EBECEF}
.lg button{border:0;margin:0;padding:2px 8px;border-radius:9999px;background:transparent;color:#6E758C;font:500 11px/16px 'DM Sans',system-ui,sans-serif;cursor:pointer}
.lg button[aria-pressed=true]{background:#FFFFFF;color:#262831;box-shadow:0 1px 2px rgba(0,0,0,.08)}
.lg button:focus-visible{outline:2px solid #0054FF;outline-offset:1px}"""
FONT = '<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500&display=swap" rel="stylesheet">'
LANGS = ('en', 'es')


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
    pct, left, rows, elapsed = snapshot(cfg)
    finished = all(r[2] == 'done' for r in rows)
    mins = max(1, int(cfg.get('refreshSeconds', 300) // 60))
    refresh = int(cfg.get('refreshSeconds', 300))
    stamp = time.strftime('%H:%M')

    def parts(lang):
        L = T[lang]
        when = L['ready'] if finished else f"{L['left']} {fmt(left)}"
        steps = ''.join(
            f'<li><div class="sr"><span class="sn">{html.escape(tr(t, lang))}</span><span class="st st-{s}">{L[s]}</span></div>'
            f'<div class="bar sm"><span style="width:{f*100:.0f}%"></span></div>'
            f'<div class="m">{f*100:.0f}%{f" · {n} {html.escape(tr(lb, lang))}" if n else ""}</div></li>'
            for t, f, s, n, lb in rows)
        return L, html.escape(tr(cfg.get('title', 'Progress'), lang)), when, steps

    def hid(lang):
        return '' if lang == default else ' hidden'

    w_body, w_foot, p_body, p_note = '', '', '', ''
    for lang in LANGS:
        L, title, when, steps = parts(lang)
        w_body += (f'<div data-lang="{lang}"{hid(lang)}><div class="ttl" title="{title}">{title}</div>'
                   f'<div class="top"><span class="pct">{pct*100:.0f}%</span><span class="left">{when}</span></div>'
                   f'<div class="bar"><span style="width:{pct*100:.0f}%"></span></div><ul>{steps}</ul></div>')
        w_foot += (f'<span class="ft" data-lang="{lang}"{hid(lang)}>'
                   f"{L['every'].format(m=mins).capitalize()} · {L['last'].format(t=stamp)}</span>")
        p_body += (f'<div data-lang="{lang}"{hid(lang)}><h1>{title}</h1>'
                   f"<div class=\"m\">{L['every'].format(m=mins).capitalize()} · {L['last'].format(t=stamp)}. {L['elapsed'].format(t=fmt(elapsed))}</div>"
                   f'<div class="big"><span class="pct">{pct*100:.0f}%</span><span class="left">{when}</span></div>'
                   f'<div class="bar"><span style="width:{pct*100:.0f}%"></span></div><ul>{steps}</ul></div>')
        p_note += f'<span data-lang="{lang}"{hid(lang)}>{L["note"]}</span>'

    title0 = html.escape(tr(cfg.get('title', 'Progress'), default))
    close = T[default]['close']
    widget = f"""<!doctype html><html lang="{default}"><head><meta charset="utf-8"><meta http-equiv="refresh" content="{refresh}">{FONT}
<style>{CSS}
html,body{{background:transparent;overflow:hidden}}
.w{{position:relative;margin:8px;padding:16px;border-radius:16px;background:#FFFFFF;border:1px solid #EBECEF;box-shadow:0 6px 12px rgba(50,50,93,.11),0 3px 6px rgba(0,0,0,.07);cursor:move;user-select:none;color:#3A3E4B}}
.ttl{{margin:0 36px 6px 0;font-size:13px;font-weight:500;color:#262831;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.top{{display:flex;align-items:baseline;gap:10px}}.pct{{font-size:32px;font-weight:500;color:#262831;line-height:1.2}}.left{{font-size:13px;color:#6E758C}}
.bar.sm{{height:6px;margin:6px 0 2px}}[data-lang]>.bar{{margin:8px 0 4px}}
ul{{list-style:none;margin:12px 0 0;padding:0}}li{{margin:10px 0 0}}.sr{{display:flex;justify-content:space-between;align-items:center;gap:8px}}
.sn{{font-size:12px;font-weight:500;color:#262831;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.m{{font-size:11px;color:#6E758C}}
.foot{{margin-top:10px;display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:11px;color:#6E758C}}
.ft{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.x{{position:absolute;z-index:2;top:8px;right:8px;width:32px;height:32px;display:flex;align-items:center;justify-content:center;padding:0;border:0;border-radius:8px;background:transparent;color:#6E758C;font-size:18px;line-height:1;cursor:pointer}}.x:hover{{background:#F9F9F9;color:#3A3E4B}}
</style></head><body><div class="w" id="w"><button class="x" title="{close}" aria-label="{close}" onclick="window.avq?avq.close():window.close()">×</button>
{w_body}<div class="foot">{w_foot}{lang_switch()}</div></div>
{lang_script(default, "try{document.title=String(Math.ceil(document.getElementById('w').getBoundingClientRect().bottom+8));}catch(e){}")}
<script>(function(){{var w=document.getElementById('w'),a=window.avq;w.addEventListener('mousedown',function(e){{if(e.button!==0||e.target.closest('button'))return;if(a)a.dragStart();}});window.addEventListener('mouseup',function(){{if(a)a.dragEnd();}});document.addEventListener('keydown',function(e){{if(e.key==='Escape'){{if(a)a.close();else window.close();}}}});}})();</script>
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
.card{{background:#FFFFFF;border:1px solid #EBECEF;border-radius:16px;padding:32px;box-shadow:0 6px 12px rgba(50,50,93,.11),0 3px 6px rgba(0,0,0,.07);margin-bottom:24px}}
h1{{margin:0 0 4px;font-size:20px;font-weight:500;color:#262831}}h2{{font-size:16px;font-weight:500;margin:0 0 12px;color:#262831}}.m{{font-size:12px;color:#6E758C}}
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
