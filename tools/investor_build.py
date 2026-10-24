"""Investor build of RYSEON.

Usage: python3 tools/investor_build.py <source_checkout> <out_dir>

1. Copies the app from the source repo (SportynX/sportynx-ryse-prototype-, branch main) into out_dir.
2. Runs the source repo's own build.py there, so the investor link is exactly the app Ivan approves.
3. Adds only investor things on top: personal links (?r=<id>, kept through updates and on the Home Screen),
   PostHog analytics (EU, cookieless) and the optional investor tweaks from config.json.
Nothing here edits the design. Never edit the app in this repo: change it in the source repo.
"""
import json, pathlib, re, shutil, subprocess, sys, hashlib, html

ROOT = pathlib.Path(__file__).resolve().parent.parent
src, out = pathlib.Path(sys.argv[1]).resolve(), pathlib.Path(sys.argv[2]).resolve()
cfg = json.loads((ROOT / "config.json").read_text())
investors = json.loads((ROOT / "investors.json").read_text())

def slug(s):
    return re.sub(r"[^a-z0-9_-]", "", s.lower())[:40]

known = {}
for inv in investors:
    i = slug(inv["id"])
    assert i and i not in known, "bad or duplicate investor id: %r" % inv["id"]
    known[i] = inv.get("name") or i

# ---- 1. copy the app -------------------------------------------------------
if out.exists():
    shutil.rmtree(out)
out.mkdir(parents=True)
(out / "src").mkdir()
shutil.copy(src / "src/prototype.html", out / "src/prototype.html")
for f in ["build.py", "manifest.webmanifest", "robots.txt"]:
    shutil.copy(src / f, out / f)
for f in src.glob("icon-*.png"):
    shutil.copy(f, out / f.name)
if (src / "media").is_dir():
    shutil.copytree(src / "media", out / "media")

# ---- 2. the source repo's own build ----------------------------------------
subprocess.run([sys.executable, "build.py"], cwd=out, check=True)
shutil.rmtree(out / "src")
(out / "build.py").unlink()
build_id = json.loads((out / "version.json").read_text())["b"]
doc = (out / "index.html").read_text()

def replace_once(doc, old, new, count=1):
    n = doc.count(old)
    assert n == count, "expected %d x %r in index.html, found %d - the source build changed, update tools/investor_build.py" % (count, old[:60], n)
    return doc.replace(old, new)

# ---- 3a. personal link: ?r=<id> -------------------------------------------
# Read ?r= (or the one saved earlier), keep it in the address bar, and point the manifest at that person's own
# manifest so "Add to Home Screen" opens with ?r=<id> (iOS uses the manifest start_url, and the Home Screen app
# can have storage separate from Safari).
head_js = """<script>
(function(){ var K=%s, r=null;
  try{ var q=new URLSearchParams(location.search).get('r'); if(q) r=q.toLowerCase().replace(/[^a-z0-9_-]/g,'').slice(0,40)||null }catch(e){}
  if(!r){ try{ r=localStorage.getItem('ryseon-r') }catch(e){} }
  if(r){ try{ localStorage.setItem('ryseon-r',r) }catch(e){}
    if(!/[?&]r=/.test(location.search)) try{ history.replaceState(null,'',location.pathname+'?r='+encodeURIComponent(r)+location.hash) }catch(e){} }
  window.__ryseR=r;
  var l=document.createElement('link'); l.rel='manifest'; l.href=(r&&K[r])?'m/'+r+'.webmanifest':'manifest.webmanifest'; document.head.appendChild(l) })();
</script>""" % json.dumps({k: 1 for k in known})
doc = replace_once(doc, '<link rel="manifest" href="manifest.webmanifest">', head_js)

# the auto-update reload must keep ?r= (build.py reloads to pathname+'?v='+build)
doc = replace_once(doc, "location.replace(location.pathname+'?v='+",
                   "location.replace(location.pathname+(window.__ryseR?'?r='+encodeURIComponent(window.__ryseR)+'&':'?')+'v='+", count=2)

man = json.loads((out / "manifest.webmanifest").read_text())
(out / "m").mkdir()
for i in known:
    m = dict(man, start_url="../?r=" + i, scope="../", id="../?r=" + i)
    m["icons"] = [dict(x, src="../" + x["src"]) for x in man["icons"]]
    (out / "m" / (i + ".webmanifest")).write_text(json.dumps(m, indent=1))

# ---- 3b. readable screen names (English, taken from the source markup) -----
names = {"sLang": "Language", "screen-intro": "Intro", "s17": "Home", "s21": "Settings"}
body = (src / "src/prototype.html").read_text()
for m in re.finditer(r'<section\b[^>]*\bid="([A-Za-z0-9_-]+)"[^>]*>(.*?)</section>', body, re.S):
    sid = m.group(1)
    if sid in names:
        continue
    h = re.search(r"<h[12]\b[^>]*>(.*?)</h[12]>", m.group(2), re.S)
    t = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h.group(1))).strip()) if h else ""
    names[sid] = (t[:50] or sid)
for t, n in {"home": "Home", "progress": "Progress", "ryseon": "RYSEON", "profile": "Profile"}.items():
    names["tab:" + t] = "Tab · " + n

# ---- 3c. analytics ---------------------------------------------------------
key = (cfg.get("posthog_key") or "").strip()
tail = ""
if key:
    ph = (ROOT / "vendor/posthog.js").read_bytes()
    (out / "ph.js").write_bytes(ph)
    tail = """<script src="ph.js?v=%s"></script>
<script>
(function(){ var ph=window.posthog; if(!ph||!ph.init) return;
  var N=%s, KN=%s, R=window.__ryseR, B='%s';
  var mode=(navigator.standalone||(window.matchMedia&&matchMedia('(display-mode: standalone)').matches))?'home_screen_app':'browser';
  /* cookieless: memory persistence; a personal link is the same person on every open (bootstrap with the ?r= id) */
  ph.init(%s,{api_host:%s,persistence:'memory',person_profiles:'always',autocapture:true,capture_pageview:false,capture_pageleave:false,
    bootstrap:R?{distinctID:'investor:'+R,isIdentifiedID:true}:undefined,
    disable_session_recording:%s,session_recording:{maskAllInputs:true}});
  ph.register({investor:R||'(no link)',investor_name:R?(KN[R]||R):'(no link)',app_mode:mode,app_build:B});
  if(R) ph.setPersonProperties({name:KN[R]||R,investor_id:R,known_link:!!KN[R]});
  var cur=null,t0=Date.now(),vis=Date.now(),seen={},nSeen=0;
  function nm(id){ return N[id]||id }
  function screen(id){ if(!id||id===cur) return; var now=Date.now(), p={screen_id:id,screen_name:nm(id)};
    if(cur){ p.previous_screen=nm(cur); p.previous_seconds=Math.round((now-t0)/1000) }
    if(id==='s17'&&cur==='sLang') ph.capture('demo_profile_opened');
    if(!seen[id]){ seen[id]=1; nSeen++ }
    ph.capture('screen_view',p); cur=id; t0=now }
  ph.capture('app_open',{mode:mode,personal_link:!!R});
  var prev=window.ryseOnEnter; window.ryseOnEnter=function(to){ try{ screen(to&&to.id) }catch(e){} if(prev) return prev.apply(this,arguments) };
  var ps=window.ryseSettings; if(ps) window.ryseSettings=function(id){ try{ ph.capture('settings_open',{page:id}) }catch(e){} return ps.apply(this,arguments) };
  document.addEventListener('click',function(e){ var t=e.target&&e.target.closest&&e.target.closest('.hnav-tab'); if(t&&t.dataset.tab){ ph.capture('tab_switch',{tab:t.dataset.tab}); setTimeout(function(){ screen('tab:'+t.dataset.tab) },0) } },true);
  var st=document.getElementById('st-title'); if(st&&window.MutationObserver){ var last=''; new MutationObserver(function(){ var t=(st.textContent||'').trim(); if(t&&t!==last){ last=t; ph.capture('settings_page',{title:t}) } }).observe(st,{childList:true,characterData:true,subtree:true}) }
  setTimeout(function(){ var s=document.querySelectorAll('section[id]'); for(var i=0;i<s.length;i++){ if(N[s[i].id]&&!s[i].classList.contains('is-hidden')){ screen(s[i].id); break } } },0);
  function end(){ var sec=Math.round((Date.now()-vis)/1000); ph.capture('session_end',{seconds_visible:sec,last_screen:cur?nm(cur):null,screens_seen:nSeen},{transport:'sendBeacon'}) }
  var hidden=false;
  document.addEventListener('visibilitychange',function(){ if(document.hidden){ if(!hidden){ hidden=true; end() } } else if(hidden){ hidden=false; vis=Date.now(); t0=Date.now(); ph.capture('app_resume',{mode:mode}) } });
  addEventListener('pagehide',function(){ if(!hidden){ hidden=true; end() } });
})();
</script>
""" % (hashlib.sha1(ph).hexdigest()[:10], json.dumps(names), json.dumps(known), build_id,
       json.dumps(key), json.dumps(cfg.get("posthog_host") or "https://eu.i.posthog.com"),
       "false" if cfg.get("session_replay") else "true")

# ---- 3d. investor tweaks (each one is a switch in config.json) -------------
css = ""
if cfg.get("hide_preview_helpers"):
    css += ".mb-proto{display:none!important}"
if css:
    tail = "<style>%s</style>\n" % css + tail

doc = replace_once(doc, "\n</body>\n</html>\n", "\n" + tail + "</body>\n</html>\n")
(out / "index.html").write_text(doc)
(out / ".nojekyll").write_text("")
print("investor build", build_id, "-", len(doc), "bytes,", len(known), "personal links,", "analytics ON" if key else "analytics OFF (no posthog_key)")
