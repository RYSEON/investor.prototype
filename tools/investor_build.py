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

# investor icon (Ivan, 24 Oct): icons/ in this repo replace the source icons; new ?v= so iPhones don't use a cached icon
icons = sorted((ROOT / "icons").glob("icon-*.png")) if (ROOT / "icons").is_dir() else []
if icons:
    iv = "inv" + hashlib.sha1(b"".join(f.read_bytes() for f in icons)).hexdigest()[:8]
    for f in icons:
        shutil.copy(f, out / f.name)
    doc = re.sub(r"(icon-\d+\.png)\?v=[\w-]+", r"\1?v=" + iv, doc)
    mf = out / "manifest.webmanifest"
    mf.write_text(re.sub(r"(icon-\d+\.png)\?v=[\w-]+", r"\1?v=" + iv, mf.read_text()))

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

# preview photo (Ivan, 24 Oct): a player who skips the profile photo (or never sees that screen, e.g. the pro path) gets
# assets/preview-player.jpg, with a short "Photo added for preview" message. Uses the app's own photo input, so the
# avatar, buttons and saved profile behave exactly as if the photo had been chosen.
if cfg.get("preview_photo") and (ROOT / "assets/preview-player.jpg").is_file():
    pb = (ROOT / "assets/preview-player.jpg").read_bytes()
    pname = "preview-player.jpg?v=" + hashlib.sha1(pb).hexdigest()[:8]
    (out / "preview-player.jpg").write_bytes(pb)
    tail = """<script>
(function(){ var SRC='%s', MSG='Photo added for preview', data=null;
  function P(){ return window.ryseProfile||{} }
  try{ fetch(SRC).then(function(r){return r.blob()}).then(function(b){ var fr=new FileReader(); fr.onload=function(){ data=fr.result }; fr.readAsDataURL(b) }) }catch(e){}
  function note(){ var t=document.getElementById('toast'); if(!t) return;
    t.innerHTML='<span class="ti"><svg viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="m3.8 8.3 2.7 2.7 5.7-6" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></span><span></span>';
    t.lastChild.textContent=MSG; t.classList.remove('on','off'); void t.offsetWidth; t.classList.add('on');
    setTimeout(function(){ t.classList.remove('on'); t.classList.add('off'); setTimeout(function(){ t.classList.remove('off') },500) },2800) }
  function direct(){ if(!data) return false; var p=P(); p.photo=data; try{ if(p.first) localStorage.setItem('ryse-last-profile',JSON.stringify(p)) }catch(e){} return true }
  /* "Skip for now" on the photo screen: put the preview photo in through the app's own photo input */
  document.addEventListener('click',function(e){ var b=e.target&&e.target.closest&&e.target.closest('#photo-skip'); if(!b||!b.dataset.go||P().photo) return;
    var inp=document.getElementById('photo-lib'), ok=false;
    try{ if(data&&inp&&window.DataTransfer){ var bin=atob(data.split(',')[1]), u=new Uint8Array(bin.length); for(var i=0;i<bin.length;i++) u[i]=bin.charCodeAt(i);
      var dt=new DataTransfer(); dt.items.add(new File([u],'preview.jpg',{type:'image/jpeg'})); inp.files=dt.files; inp.dispatchEvent(new Event('change',{bubbles:true})); ok=true } }catch(err){}
    if(!ok) ok=direct(); if(ok) setTimeout(note,700) },true);
  /* any path that reaches the app without a photo */
  var prev=window.ryseOnEnter; window.ryseOnEnter=function(to){ var n=false; try{ if(to&&to.id==='s17'&&!P().photo) n=direct() }catch(e){} var r=prev?prev.apply(this,arguments):undefined; if(n) setTimeout(note,900); return r };
})();
</script>
""" % pname + tail

# ---- 3e. welcome / Add to Home Screen guide (Ivan, 24 Oct) -----------------
# Opened in a phone browser (not yet from the Home Screen): ask iPhone or Android, show the three steps on one screen,
# and let the investor choose to add it or continue in the browser. On a computer: show their QR code to scan instead.
# Never shown inside the Home Screen app. "Continue in browser" is remembered on that device.
if cfg.get("install_guide") and (ROOT / "assets/guide").is_dir():
    shutil.copytree(ROOT / "assets/guide", out / "guide")
    qr_ok = False
    try:
        import qrcode
        (out / "qr").mkdir(exist_ok=True)
        base = cfg.get("public_url", "").rstrip("/")
        for i in known:
            q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=12, border=2)
            q.add_data(base + "/?r=" + i); q.make(fit=True)
            q.make_image(fill_color="black", back_color="white").save(out / "qr" / (i + ".png"))
        qr_ok = True
    except ImportError:
        print("qrcode not installed - desktop QR skipped")
    names_short = {k: re.sub(r"\s*\(.*?\)\s*", "", v).split(" ")[0] for k, v in known.items()}
    guide_html = """<style>
#rg{position:fixed;inset:0;z-index:2147483000;display:none;background:rgba(3,5,10,.88);-webkit-backdrop-filter:blur(18px);backdrop-filter:blur(18px);
  font-family:var(--font-body,Manrope,-apple-system,sans-serif);color:#F5F7FB;-webkit-user-select:none;user-select:none;opacity:0;transition:opacity .35s ease}
#rg.on{display:block}#rg.in{opacity:1}
#rg .w{position:absolute;inset:0;margin:0 auto;max-width:430px;display:flex;flex-direction:column;padding:calc(env(safe-area-inset-top) + 34px) 24px calc(env(safe-area-inset-bottom) + 22px);overflow-y:auto}
#rg .pg{display:none;flex:1;flex-direction:column}#rg .pg.on{display:flex;animation:rgIn .45s cubic-bezier(.2,.7,.2,1)}
@keyframes rgIn{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
#rg .bd{font-family:var(--font-display,Archivo,sans-serif);font-weight:700;font-size:13px;letter-spacing:.26em}#rg .bd span{color:#7D8698}
#rg h2{font-family:var(--font-display,Archivo,sans-serif);font-weight:600;font-size:34px;line-height:1.08;letter-spacing:-.01em;margin:44px 0 0}
#rg p{font-size:16px;line-height:1.5;color:#B8C0CF;margin:14px 0 0}
#rg .lb{font-size:13px;letter-spacing:.14em;text-transform:uppercase;color:#7D8698;margin:auto 0 14px}
#rg .os{display:flex;gap:12px}
#rg .ob{flex:1;height:108px;border-radius:18px;border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.04);color:#F5F7FB;font:600 17px var(--font-body,Manrope,sans-serif);
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;cursor:pointer}
#rg .ob:active{border-color:#2F6BFF;background:rgba(47,107,255,.12)}
#rg .ob svg{width:26px;height:26px}
#rg .lk{background:none;border:0;color:#9AA4B6;font:500 15px var(--font-body,Manrope,sans-serif);padding:18px 0 4px;cursor:pointer;align-self:center}
#rg .bk{background:none;border:0;color:#F5F7FB;padding:0;width:36px;height:36px;margin:-6px 0 0 -8px;cursor:pointer}
#rg .st{display:flex;gap:10px;margin-top:26px}
#rg .st div{flex:1;text-align:center}
#rg .st img{width:100%;height:auto;display:block}
#rg .st .n{width:24px;height:24px;border-radius:50%;border:1px solid #2F6BFF;color:#8FB0FF;font:600 12px var(--font-display,Archivo,sans-serif);display:grid;place-items:center;margin:0 auto 10px}
#rg .st em{display:block;font-style:normal;font-size:12.5px;line-height:1.38;color:#9AA4B6;margin-top:12px}
#rg .st b{color:#F5F7FB;font-weight:600}
#rg .nt{font-size:12.5px;line-height:1.45;color:#7D8698;margin-top:18px}
#rg .pb{margin-top:auto;height:56px;border-radius:16px;border:0;background:#F5F7FB;color:#03050A;font:600 16px var(--font-body,Manrope,sans-serif);cursor:pointer}
#rg .qr{margin:34px auto 0;width:220px;height:220px;border-radius:22px;background:#fff;padding:14px}#rg .qr img{width:100%;height:100%;display:block}
</style>
<div id="rg" aria-modal="true" role="dialog"><div class="w">
 <div class="pg" data-p="hi"><div class="bd">RYSE<span>ON</span></div>
  <h2 data-h>Welcome.</h2>
  <p>For the best experience, add RYSEON to your Home Screen. It opens full screen, just like the real app.</p>
  <div class="lb">Which phone are you using?</div>
  <div class="os"><button class="ob" type="button" data-os="ios"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="6.5" y="2.5" width="11" height="19" rx="3"/><path d="M10.5 5h3"/></svg>iPhone</button>
   <button class="ob" type="button" data-os="android"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="6.5" y="2.5" width="11" height="19" rx="2.2"/><circle cx="12" cy="5.2" r=".6" fill="currentColor"/></svg>Android</button></div>
  <button class="lk" type="button" data-x="browser">Continue in browser</button></div>
 <div class="pg" data-p="ios"><button class="bk" type="button" data-to="hi" aria-label="Back"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M15 5l-7 7 7 7"/></svg></button>
  <h2 style="margin-top:22px">Add to Home Screen</h2><p>iPhone · Safari · three taps</p>
  <div class="st"><div><div class="n">1</div><img src="guide/ios-1.png" alt=""><em>Tap <b>≡</b> on the left of the address bar</em></div>
   <div><div class="n">2</div><img src="guide/ios-2.png" alt=""><em>Tap <b>Share</b></em></div>
   <div><div class="n">3</div><img src="guide/ios-3.png" alt=""><em>Scroll down, tap <b>Add to Home Screen</b>, then <b>Add</b></em></div></div>
  <div class="nt">Older iPhone? Tap the Share button at the bottom of Safari, then Add to Home Screen. Then open RYSEON from your Home Screen.</div>
  <button class="pb" type="button" data-x="got">Got it, I'll add it</button><button class="lk" type="button" data-x="browser">Continue in browser</button></div>
 <div class="pg" data-p="android"><button class="bk" type="button" data-to="hi" aria-label="Back"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M15 5l-7 7 7 7"/></svg></button>
  <h2 style="margin-top:22px">Add to Home Screen</h2><p>Android · Chrome · three taps</p>
  <div class="st"><div><div class="n">1</div><img src="guide/android-1.png" alt=""><em>Tap <b>⋮</b> at the top right</em></div>
   <div><div class="n">2</div><img src="guide/android-2.png" alt=""><em>Tap <b>Add to Home screen</b> or <b>Install app</b></em></div>
   <div><div class="n">3</div><img src="guide/android-3.png" alt=""><em>Tap <b>Install</b></em></div></div>
  <div class="nt">Samsung Internet? Menu at the bottom, then Add page to, Home screen. Then open RYSEON from your Home Screen.</div>
  <button class="pb" type="button" data-x="got">Got it, I'll add it</button><button class="lk" type="button" data-x="browser">Continue in browser</button></div>
 <div class="pg" data-p="desk"><div class="bd">RYSE<span>ON</span></div>
  <h2 data-h>Welcome.</h2><p>RYSEON is made for your phone. Scan this code with your phone's camera to open your personal preview there.</p>
  <div class="qr" data-qr><img alt="QR code" data-qri></div>
  <button class="pb" type="button" data-x="browser" style="margin-top:auto;background:transparent;color:#F5F7FB;border:1px solid rgba(255,255,255,.16)">Continue on this computer</button></div>
</div></div>
<script>
(function(){ var NM=__NM__, QR=__QR__, R=window.__ryseR;
  try{ if(navigator.standalone||(window.matchMedia&&matchMedia('(display-mode: standalone)').matches)) return }catch(e){ return }
  try{ if(/[?&]guide=1/.test(location.search)) localStorage.removeItem('ryseon-guide'); else if(localStorage.getItem('ryseon-guide')==='browser') return }catch(e){}
  var ua=navigator.userAgent||'', mobile=/iPhone|iPad|iPod|Android/i.test(ua)||(navigator.maxTouchPoints>1&&Math.min(screen.width,screen.height)<900);
  if(!mobile&&!(QR&&R&&NM[R])) return;
  var g=document.getElementById('rg'); if(!g) return;
  function ev(n,p){ try{ window.posthog&&window.posthog.capture&&window.posthog.capture(n,p||{}) }catch(e){} }
  var nm=R&&NM[R]; g.querySelectorAll('[data-h]').forEach(function(h){ h.textContent=nm?('Welcome, '+nm+'.'):'Welcome.' });
  function show(p){ g.querySelectorAll('.pg').forEach(function(x){ x.classList.toggle('on',x.dataset.p===p) }); g.querySelector('.w').scrollTop=0 }
  function close(how){ g.classList.remove('in'); setTimeout(function(){ g.classList.remove('on') },350); ev('guide_closed',{action:how});
    if(how==='browser'){ try{ localStorage.setItem('ryseon-guide','browser') }catch(e){} } }
  g.addEventListener('click',function(e){ var b=e.target.closest('button'); if(!b) return;
    if(b.dataset.os){ show(b.dataset.os); ev('guide_os',{os:b.dataset.os}) }
    else if(b.dataset.to) show(b.dataset.to);
    else if(b.dataset.x) close(b.dataset.x) });
  function open(){ if(!mobile){ g.querySelector('[data-qri]').src='qr/'+R+'.png'; show('desk') } else show('hi');
    g.classList.add('on'); setTimeout(function(){ g.classList.add('in') },30); ev('guide_shown',{device:mobile?'phone':'computer'}) }
  /* wait until the loading screen has lifted and an app screen is really on top, then let its entrance play */
  var t0=Date.now(); (function wait(){ var el=null; try{ el=document.elementFromPoint(innerWidth/2,innerHeight/2) }catch(e){}
    if(el&&el.closest&&el.closest('section[id]')) return setTimeout(open,900);
    if(Date.now()-t0<45000) setTimeout(wait,300) })();
})();
</script>
"""
    guide_html = guide_html.replace("__NM__", json.dumps(names_short)).replace("__QR__", "true" if qr_ok else "false")
    tail = guide_html + tail

doc = replace_once(doc, "\n</body>\n</html>\n", "\n" + tail + "</body>\n</html>\n")
(out / "index.html").write_text(doc)
(out / ".nojekyll").write_text("")
print("investor build", build_id, "-", len(doc), "bytes,", len(known), "personal links,", "analytics ON" if key else "analytics OFF (no posthog_key)")
