#!/usr/bin/env python3
"""
Belmont's Curse patcher (unofficial fan mod)
--------------------------------------------
by PromptedNotProud (made with AI assistance)

One installer for everything: patches GameAssembly.dll and two settings files and fixes the
resolution names in the settings menu. Everything is rebuilt
from clean copies of your own game files kept in ./stock, so it can always be undone.

Easiest: double-click Install.bat (opens a window with all options).
Command line (from this folder):
    python belmont_patcher.py                    install with the saved settings
    python belmont_patcher.py --gui              open the settings window
    python belmont_patcher.py --set=camera_zoom_factor=1.15    override one option for this run
    python belmont_patcher.py --no-bundles       skip the menu text (no extra packages)
    python belmont_patcher.py --uninstall        restore every original file

Options chosen in the window are saved to belmont_settings.json; CONFIG below holds the defaults.
After a Steam update just run it again: it sees the new vanilla files, saves them as the new
stock copies and patches those.
"""
PATCHER_AUTHOR = 'PromptedNotProud'
PATCHER_VERSION = 'v0.29.1'   # semantic versioning MAJOR.MINOR.PATCH: features -> MINOR, fixes only -> PATCH; v20..v27 = 0.20.0..0.27.0
CONFIG = {
    # resolution and anti-aliasing
    'resolutions':        True,   # the resolution list: 16:9 from 1280x720 to 7680x4320 plus 2560x1080, 3440x1440 and 5120x1440;
                                  #   every menu entry is the size you get (an entry appears only if your monitor offers it)
    'ultrawide':          False,  # EXPERIMENTAL: the ultra-wide entries render at their own width (21:9, 32:9) instead of the
                                  #   16:9 image with black bars the game normally gives; needs 'resolutions'
    'taa_menu':           True,   # the Anti-Aliasing menu offers TAA (Unity's temporal AA, shipped with the game but hidden)
    'smaa_high':          True,   # SMAA quality High instead of Low
    'reflection_aa':      'smaa', # anti-aliasing on water and mirror reflections: 'off', 'smaa' or 'taa' (post-processing on the
                                  #   reflection camera: its brightness is clamped to the main image's range, so reflected
                                  #   lights may look dimmer)
    # image quality
    'shadow_quality':     True,   # soft shadows on, higher realtime shadow resolution
    'reflection_shadows': True,   # water and mirror reflections render shadows (costs GPU time)
    'lightshaft_quality': True,   # light shafts at 32 samples, full resolution
    'anisotropic_16x':    True,   # force anisotropic filtering on every texture
    # camera
    'camera_zoom':        True,   # pulls the follow camera in
    'camera_zoom_factor': 1.25,   #   1.25 = characters 25% larger on screen
    'camera_zoom_boss_factor': 1.0, #   zoom used while a boss fight's dynamic camera is active (1.0 = stock framing;
                                    #   boss arenas are framed to fit the screen, extra zoom there makes the camera chase)
    'camera_zoom_full_below': 13.5, #   areas the game frames up to this many world units high get the full closer camera...
    'camera_zoom_stock_above': 14.0, #  ...areas framed this high or more get the stock framing (blended in between); most
                                     #  areas are 12-13.5 units high, the deliberately wide ones 14-18
    'camera_zoom_stock_on_zoom_out': True, # cameras the level switches to on purpose (door openings, vistas, set
                                     #  pieces) that frame wider than the room's follow camera get the stock framing
    'camera_toggle':      True,   # a key in game switches between the closer camera and the stock framing (for checking
                                  #   camera areas; the zoom eases over as usual). A system sound confirms each switch.
    'camera_toggle_key':  'F8',   #   F1..F12, or a Windows virtual-key code
    # motion
    'smooth_motion':      True,   # every object the simulation moves or rotates (water wheels, platforms, gates, cutscene
                                  #   props, projectiles) is drawn between its last two positions, animated props get the
                                  #   game's own animation smoothing, cutscene camera blends and cutscene walking update every
                                  #   rendered frame; in both tick-rate modes
    'sim_rate':           1,      # tick rate: 1 = 30 Hz (stock). 4 = 120 Hz and 2 = 60 Hz are EXPERIMENTAL: every object still
                                  #   runs the stock 30 Hz code once per frame; the player's frames start on the tick a button is
                                  #   pressed or the stick moves (lower input latency, identical movement). See AUDIT_NOTES.md.
    'sched_hold':         1,      #   sched: frames after an early start before the gained ticks are paid back one per
                                  #   frame (1 = the frame in which the new action begins is never stretched)
    'sched_move':         True,   #   sched: a change of stick/d-pad direction also starts the player's frame early
    'sched_smooth':       True,   #   sched: keep the player's drawn position continuous when a frame starts early
    # gameplay
    'skip_splash':        True,   # boot straight to the title screen: no company logos or startup notices
    'dialogue_preload':   True,   # loads dialogue portraits in the background when a cutscene starts (no hitch on the first line)
    'font_preload':       True,   # removes hitching in the game from font loading (Unity's list of the installed Windows fonts
                                  #   is built while the first room loads instead of during gameplay)
}
REFLECTION_AA_CHOICES = ('off', 'smaa', 'taa')

# ============================================================================
#  Signature engine
# ============================================================================
# Signature engine shared by generator and patcher (pure stdlib)
import struct
class PE:
    def __init__(s, b):
        s.b=b
        pe=struct.unpack_from('<I',b,0x3c)[0]; s.pe=pe
        s.nsec=struct.unpack_from('<H',b,pe+6)[0]
        s.optsz=struct.unpack_from('<H',b,pe+20)[0]
        s.opt=pe+24
        s.base=struct.unpack_from('<Q',b,s.opt+24)[0]
        s.secalign,s.filealign=struct.unpack_from('<II',b,s.opt+32)
        s.sizeofimage=struct.unpack_from('<I',b,s.opt+56)[0]
        s.sizeofheaders=struct.unpack_from('<I',b,s.opt+60)[0]
        s.shoff=s.opt+s.optsz
        s.secs=[]
        for i in range(s.nsec):
            o=s.shoff+40*i
            name=b[o:o+8].rstrip(b'\0').decode()
            vs,va,rs,rp=struct.unpack_from('<IIII',b,o+8); ch=struct.unpack_from('<I',b,o+36)[0]
            s.secs.append(dict(name=name,vs=vs,va=va,rs=rs,rp=rp,ch=ch,hdr=o))
    def v2o(s,va):
        r=va-s.base
        for x in s.secs:
            if x['va']<=r<x['va']+max(x['vs'],x['rs']) and r-x['va']<x['rs']: return x['rp']+r-x['va']
        raise ValueError(hex(va))
    def o2v(s,o):
        for x in s.secs:
            if x['rp']<=o<x['rp']+x['rs']: return s.base+x['va']+o-x['rp']
        return None
    def code_ranges(s):
        return [(x['rp'],x['rp']+min(x['rs'],x['vs'])) for x in s.secs if x['ch']&0x20000000 and not x['name'].startswith('.mod')]
    def exports(s):
        dd=s.opt+112; rva,size=struct.unpack_from('<II',s.b,dd)
        o=s.v2o(s.base+rva); b=s.b
        nfun,nnames,afun,anames,aord=struct.unpack_from('<IIIII',b,o+20)
        funcs=[struct.unpack_from('<I',b,s.v2o(s.base+afun)+4*i)[0] for i in range(nfun)]
        res={}
        no=s.v2o(s.base+anames); oo=s.v2o(s.base+aord)
        for i in range(nnames):
            nr=struct.unpack_from('<I',b,no+4*i)[0]; ordi=struct.unpack_from('<H',b,oo+2*i)[0]
            p=s.v2o(s.base+nr); e=b.index(b'\0',p)
            res[b[p:e].decode()]=s.base+funcs[ordi]
        return res
    def imports(s):
        dd=s.opt+112+8; rva,size=struct.unpack_from('<II',s.b,dd)
        res={}
        if not rva: return res
        o=s.v2o(s.base+rva); b=s.b
        while True:
            ilt,ts,fc,nm,iat=struct.unpack_from('<IIIII',b,o)
            if not nm: break
            t=ilt or iat; i=0
            while True:
                e=struct.unpack_from('<Q',b,s.v2o(s.base+t)+8*i)[0]
                if not e: break
                if not e>>63:
                    p=s.v2o(s.base+(e&0x7fffffff)+2); q=b.index(b'\0',p)
                    res.setdefault(b[p:q].decode(),s.base+iat+8*i)
                i+=1
            o+=20
        return res
    def cstr(s,va,maxlen=200):
        try: o=s.v2o(va)
        except ValueError: return None
        e=s.b.find(b'\0',o,o+maxlen)
        if e<0: return None
        t=s.b[o:e]
        if len(t)<6 or any(c<32 or c>126 for c in t): return None
        return t.decode()

def match_at(pe,o,sig):
    b=pe.b; pat=sig['pat']
    if o<0 or o+len(pat)>len(b): return False
    for i,v in enumerate(pat):
        if v is not None and b[o+i]!=v: return False
    for rel,ln,s in sig.get('str',[]):
        disp=struct.unpack_from('<i',b,o+rel)[0]
        va=pe.o2v(o+rel)
        if va is None or pe.cstr(va+4+ln+disp)!=s: return False
    return True

def find(pe,sig,limit=3):
    pat=sig['pat']
    # longest literal run
    best=(0,0); i=0
    while i<len(pat):
        if pat[i] is None: i+=1; continue
        j=i
        while j<len(pat) and pat[j] is not None: j+=1
        if j-i>best[1]-best[0]: best=(i,j)
        i=j
    lit=bytes(pat[best[0]:best[1]])
    out=[]
    for a,z in pe.code_ranges():
        p=pe.b.find(lit,a,z)
        while p>=0:
            o=p-best[0]
            if match_at(pe,o,sig):
                out.append(o)
                if len(out)>=limit: return out
            p=pe.b.find(lit,p+1,z)
    return out

def sig_to_json(sig): return {'pat':''.join('??' if v is None else '%02x'%v for v in sig['pat']),'str':sig.get('str',[]),'off':sig.get('off',0)}
def sig_from_json(j):
    p=j['pat']; return {'pat':[None if p[i:i+2]=='??' else int(p[i:i+2],16) for i in range(0,len(p),2)],'str':[tuple(x) for x in j.get('str',[])],'off':j.get('off',0)}

SPEC_B64 = (
    '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'
    'kh21bj4tWE3//Of/A9Aw9S4='
)

# ============================================================================
#  Patcher logic
# ============================================================================
import os, sys, json, zlib, base64, shutil, hashlib, struct, re

def log(*a): print(*a); sys.stdout.flush()

PATCH_HOOKS = []   # extra blob settings of the diagnostics build (patcher_diag.py); empty in the release

def load_spec(): return json.loads(zlib.decompress(base64.b64decode(SPEC_B64)))

def has_mod_sections(b):
    pe=PE(b); return any(s['name'] in ('.modt','.modd') for s in pe.secs)

def add_sections(b, code, datalen, writable=False):
    pe=PE(b); b=bytearray(b)
    last=max(pe.secs,key=lambda s:s['va'])
    va=(last['va']+max(last['vs'],last['rs'])+pe.secalign-1)//pe.secalign*pe.secalign
    hdr_end=pe.shoff+40*pe.nsec
    first_raw=min(s['rp'] for s in pe.secs if s['rp'])
    assert hdr_end+80<=first_raw, "no room for section headers"
    assert all(v==0 for v in b[hdr_end:hdr_end+80]), "header slack not empty"
    fa=pe.filealign
    raw=(len(b)+fa-1)//fa*fa
    b+=b'\0'*(raw-len(b))
    csize=(len(code)+fa-1)//fa*fa
    tva=va; dva=va+((csize+pe.secalign-1)//pe.secalign*pe.secalign)
    dsize=(datalen+fa-1)//fa*fa
    def sh(name,vs,v,rs,rp,ch): return name.ljust(8,b'\0')+struct.pack('<IIIIIIHHI',vs,v,rs,rp,0,0,0,0,ch)
    b[hdr_end:hdr_end+40]=sh(b'.modt',len(code),tva,csize,raw,0xE0000020 if writable else 0x60000020)
    b[hdr_end+40:hdr_end+80]=sh(b'.modd',datalen,dva,dsize,raw+csize,0xC0000040)
    struct.pack_into('<H',b,pe.pe+6,pe.nsec+2)
    soi=(dva+datalen+pe.secalign-1)//pe.secalign*pe.secalign
    struct.pack_into('<I',b,pe.opt+56,soi)
    b+=code+b'\0'*(csize-len(code))+b'\0'*dsize
    return b, pe.base+tva, pe.base+dva

def patch_dll(stock, cfg, spec):
    pe=PE(stock)
    report={}
    # 1. locate all patch sites
    sites=[]
    for p in spec['patches']:
        sg=sig_from_json(p['sig']); m=find(pe,sg,limit=2)
        ok=False; va=None
        if len(m)==1:
            va=pe.o2v(m[0])+sg['off']; o=pe.v2o(va)
            if p['type'] in ('bytes','jmp_to'):
                # 'wild': byte positions allowed to differ (rip-relative displacements to metadata, which move in every build)
                old=bytes.fromhex(p['old']); cur=stock[o:o+len(old)]; wild=set(p.get('wild',()))
                ok = len(cur)==len(old) and all(cur[i]==old[i] for i in range(len(old)) if i not in wild)
            elif p['type'] in ('call_to','call_sym'):
                ok = stock[o]==int(p['op'],16)
            elif p['type']=='rip_to':
                ok = stock[o:o+p['disp_at']]==bytes.fromhex(p['old_prefix'])
        sites.append((p,va if ok else None))
    # 2. symbols
    exp=pe.exports(); imp=pe.imports(); syms={}
    for k,s in spec['symbols'].items():
        if s['type']=='export': syms[k]=exp.get(s['name'])
        elif s['type']=='import': syms[k]=imp.get(s['name'])
        elif s['type']=='rip':
            m=find(pe,sig_from_json(s['sig']),limit=2)
            if len(m)==1:
                va=pe.o2v(m[0])+s['sig'].get('off',0); o=pe.v2o(va)
                syms[k]=va+s['insn_len']+struct.unpack_from('<i',stock,o+s['disp_at'])[0]
            else: syms[k]=None
        else:
            m=find(pe,sig_from_json(s['sig']),limit=2); syms[k]=pe.o2v(m[0])+s['sig'].get('off',0) if len(m)==1 else None
    bad=set()
    for idx,(p,va) in enumerate(sites):
        if va is None: continue
        if p['type']=='call_to':
            o=pe.v2o(va); t=va+5+struct.unpack_from('<i',stock,o+1)[0]
            if syms.get(p['capture']) is None: syms[p['capture']]=t
            elif syms[p['capture']]!=t: bad.add(idx)
        if p['type']=='jmp_to' and p.get('ret_sym'): syms[p['ret_sym']]=va+p['ret_off']
        for dn,(doff,dexp) in p.get('defs',{}).items():
            do=pe.v2o(va+doff)
            if stock[do:do+len(bytes.fromhex(dexp))]==bytes.fromhex(dexp): syms[dn]=va+doff
            else: bad.add(idx)
        if p['type']=='call_sym':
            o=pe.v2o(va); t=va+5+struct.unpack_from('<i',stock,o+1)[0]
            if syms.get(p['expect']) not in (None,t): bad.add(idx)
    sites=[(p,None if i in bad else va) for i,(p,va) in enumerate(sites)]
    # 3. decide features
    feats={}
    for p,va in sites: feats.setdefault(p['feature'],[]).append(va is not None)
    enabled={}
    N=int(cfg.get('sim_rate',1) or 1)
    sm=bool(cfg.get('smooth_motion',True))
    raa=str(cfg.get('reflection_aa','smaa')).lower()
    wants={'sim_core':N>1,'sim_sched':N>1,'sched_core':N>1,
           'smoothing':sm,'cutscene_camera':sm,'cutscene_goto':sm,
           'reflection_aa_smaa':raa=='smaa','reflection_aa_taa':raa=='taa',
           'ultrawide':bool(cfg.get('ultrawide',False)) and bool(cfg.get('resolutions',True)),
           'camera_zoom_edges':bool(cfg.get('camera_zoom',True))}
    found={}
    for f,oks in feats.items():
        want=wants.get(f,cfg.get(f,False))
        found[f]=all(oks) and all(syms.get(n) for n in spec['needs'].get(f,[]))
        enabled[f]=bool(want and found[f])
    # the scheduler needs its core hooks; a faster tick needs the scheduler, otherwise stay at 30 Hz
    if enabled.get('sim_sched') and not enabled.get('sched_core'): enabled['sim_sched']=False
    if not enabled.get('sim_sched'): enabled['sim_core']=False; enabled['sched_core']=False
    if not enabled.get('resolutions'): enabled['ultrawide']=False
    if not enabled.get('camera_zoom'): enabled['camera_zoom_edges']=False
    for f in feats:
        want=wants.get(f,cfg.get(f,False))
        if not found[f]: report[f]='NOT FOUND (skipped)' if want else 'off (not found in this build)'
        elif enabled[f]: report[f]='ON'
        else: report[f]='off (needs another part that was not found)' if want else 'off'
    if N>1 and not enabled.get('sim_core'): N=1; report['sim_rate_effective']='30 Hz (faster rate unavailable in this build)'
    for f in ('reflection_aa_smaa','reflection_aa_taa'): report.pop(f,None)
    report['reflection_aa']='off' if raa not in ('smaa','taa') else ('ON (%s)'%raa.upper() if enabled.get('reflection_aa_'+raa) else 'NOT FOUND (skipped)')
    # 4. build blob
    bl=spec['blob']; code=bytearray(bytes.fromhex(bl['code']))
    cvk=key_vk(cfg)
    cam_on=bool(cvk) and enabled.get('camera_zoom') and 'P_CAMKEY' in bl['labels'] \
        and all(syms.get(n) for n in ('IAT_GMHW','IAT_LLW','IAT_GPA','IAT_GCPID'))
    if cvk: report['camera_toggle']=('ON (%s: closer <-> stock camera in game)'%cfg.get('camera_toggle_key','F8')) if cam_on \
        else ('off (needs the closer camera)' if not enabled.get('camera_zoom') else 'NOT AVAILABLE')
    out,tva,dva=add_sections(stock,bytes(code),bl['datalen'])
    pe2=PE(bytes(out))
    def label_va(l): return tva+bl['labels'][l]
    co=pe2.v2o(tva)
    for off,name in bl['fixups']:
        t=syms.get(name)
        if t is None: t=tva+off+4   # unresolved: points to itself, never executed
        struct.pack_into('<i',out,co+off,t-(tva+off+4))
    zoom=float(cfg.get('camera_zoom_factor',1.25))
    struct.pack_into('<f',out,co+bl['labels']['P_ZOOMK'],1.0/zoom)
    if 'P_ZHLO' in bl['labels']:
        lo=float(cfg.get('camera_zoom_full_below',13.5)); hi=float(cfg.get('camera_zoom_stock_above',14.0))
        if hi<=lo: hi=lo+0.01
        struct.pack_into('<ff',out,co+bl['labels']['P_ZHLO'],lo,hi)
    if 'P_ZSPEC' in bl['labels']:
        zs=bool(cfg.get('camera_zoom_stock_on_zoom_out',True)) and all(syms.get(n) for n in ('OBJ_GETNAME','RESOLVE'))
        struct.pack_into('<I',out,co+bl['labels']['P_ZSPEC'],1 if zs else 0)
    if 'P_ZOOMKB' in bl['labels']:
        zb=float(cfg.get('camera_zoom_boss_factor',1.0) or 1.0)
        struct.pack_into('<f',out,co+bl['labels']['P_ZOOMKB'],1.0/zb)
    struct.pack_into('<i',out,co+bl['labels']['P_SIMN'],N)
    struct.pack_into('<f',out,co+bl['labels']['P_INVN'],1.0/N)
    if 'P_SIMNF' in bl['labels']: struct.pack_into('<f',out,co+bl['labels']['P_SIMNF'],float(N))
    for lab in [l for l in bl['labels'] if l.startswith('P_SYM_')]:
        t=syms.get(lab[6:])
        if t: struct.pack_into('<i',out,co+bl['labels'][lab],t-tva)
    for lab in [l for l in bl['labels'] if l.startswith('P_IAT_')]:
        t=syms.get('IAT_'+lab[6:])
        if t: struct.pack_into('<i',out,co+bl['labels'][lab],t-tva)
    if 'P_GTON' in bl['labels']: struct.pack_into('<I',out,co+bl['labels']['P_GTON'],1 if sm else 0)
    if 'P_IAAON' in bl['labels']: struct.pack_into('<I',out,co+bl['labels']['P_IAAON'],1 if sm else 0)
    if 'P_TDTON' in bl['labels']: struct.pack_into('<I',out,co+bl['labels']['P_TDTON'],1 if enabled.get('sim_sched') else 0)
    if 'P_CAMKEY' in bl['labels']: struct.pack_into('<I',out,co+bl['labels']['P_CAMKEY'],cvk if cam_on else 0)
    if 'P_SCHON' in bl['labels']:
        struct.pack_into('<I',out,co+bl['labels']['P_SCHON'],1 if enabled.get('sim_sched') and N>1 else 0)
        # the player may lead the world grid by less than one frame, so every world frame sees exactly one player frame
        struct.pack_into('<I',out,co+bl['labels']['P_DMAX'],max(0,N-1))
        struct.pack_into('<I',out,co+bl['labels']['P_SCHHOLD'],max(0,min(8,int(cfg.get('sched_hold',1) or 0))))
        struct.pack_into('<I',out,co+bl['labels']['P_SCHMV'],1 if cfg.get('sched_move',True) else 0)
        struct.pack_into('<I',out,co+bl['labels']['P_SCHSM'],1 if cfg.get('sched_smooth',True) else 0)
    for fn in PATCH_HOOKS: fn(out, co, bl, cfg, enabled, syms, report, tva, pe2)
    # 5. apply site patches
    for p,va in sites:
        if va is None or not enabled.get(p['feature']): continue
        o=pe2.v2o(va); t=p['type']
        if t=='bytes':
            new=bytes.fromhex(p['new']); out[o:o+len(new)]=new
        elif t=='jmp_to':
            n=len(bytes.fromhex(p['old'])); j=b'\xe9'+struct.pack('<i',label_va(p['label'])-(va+5))
            out[o:o+n]=j+b'\x90'*(n-5)
        elif t=='call_to':
            struct.pack_into('<i',out,o+1,label_va(p['label'])-(va+5))
        elif t=='call_sym':
            struct.pack_into('<i',out,o+1,syms[p['sym']]-(va+5))
        elif t=='rip_to':
            if p.get('new_prefix'): np_=bytes.fromhex(p['new_prefix']); out[o:o+len(np_)]=np_
            struct.pack_into('<i',out,o+p['disp_at'],label_va(p['label'])-(va+p['insn_len']))
    disp={'sim_core':'tick_rate_fast','sim_sched':'tick_rate_scheduler','sched_core':'scheduler_hooks'}
    return bytes(out), {disp.get(k,k):v for k,v in report.items()}

# ---------------- asset patches (globalgamemanagers / .assets) ----------------
def patch_assets(data_dir, stock_dir, cfg):
    rep={}
    # URP pipeline asset (High tier)
    src=os.path.join(stock_dir,'globalgamemanagers.assets')
    b=bytearray(open(src,'rb').read())
    name=b'RedWine_URP_Settings_High'
    i=b.find(struct.pack('<i',len(name))+name)
    want=cfg.get('shadow_quality',False)
    ok=False
    if i>0:
        o=i-28
        EXP={228:256,244:1024,248:128,252:256,256:512,324:2}
        if all(struct.unpack_from('<i',b,o+k)[0]==v for k,v in EXP.items()) and b[o+312]==0:
            ok=True
            if want:
                for k,v in {228:2048,244:4096,248:512,252:1024,256:2048,324:3}.items(): struct.pack_into('<i',b,o+k,v)
                b[o+312]=1
    rep['shadow_quality']=('ON' if want else 'off') if ok else ('NOT FOUND (skipped)' if want else 'off (not found)')
    _atomic_write(os.path.join(data_dir,'globalgamemanagers.assets'),bytes(b))
    # QualitySettings: force anisotropic filtering on High tier
    src=os.path.join(stock_dir,'globalgamemanagers')
    b=bytearray(open(src,'rb').read())
    want=cfg.get('anisotropic_16x',False); ok=False
    i=b.find(b'\x04\x00\x00\x00High')
    while i>0 and not ok:
        base=i+8
        pl,sh,sr,sp,sc=struct.unpack_from('<5i',b,base)
        if sh in (0,1,2) and 1<=sc<=4 and struct.unpack_from('<i',b,base+56)[0]==0 and struct.unpack_from('<i',b,base+60)[0] in (0,1,2):
            ok=True
            if want: struct.pack_into('<i',b,base+60,2)
        i=b.find(b'\x04\x00\x00\x00High',i+1)
    rep['anisotropic_16x']=('ON' if want else 'off') if ok else ('NOT FOUND (skipped)' if want else 'off (not found)')
    _atomic_write(os.path.join(data_dir,'globalgamemanagers'),bytes(b))
    # v19: the reflection renderer (UniversalRendererData 'ReflectionRenderer') has no PostProcessData, so URP cannot run
    # SMAA on reflection cameras; give it the main renderer's. Both objects: name, 2 debug shader PPtrs, feature list,
    # feature map, native-pass flag, then postProcessData and xrSystemData (PPtr = int file id + long path id).
    src=os.path.join(stock_dir,'globalgamemanagers.assets')
    b=bytearray(open(os.path.join(data_dir,'globalgamemanagers.assets'),'rb').read())
    want=str(cfg.get('reflection_aa','smaa')).lower() in ('smaa','taa'); ok=False
    i=b.find(b'\x12\x00\x00\x00ReflectionRenderer'); j=b.find(b'\x0c\x00\x00\x00MainRenderer')
    def _after_lists(base,nlen):
        p=base+32+((nlen+3)&~3)+24
        n=struct.unpack_from('<i',b,p)[0]; p+=4+12*n
        n=struct.unpack_from('<i',b,p)[0]; p+=4+8*n
        return p+4
    if i>0 and j>0:
        pr=_after_lists(i-28,18); pm=_after_lists(j-28,12)
        fid,pid=struct.unpack_from('<iq',b,pm)
        if fid==0 and 0<pid<(1<<40) and struct.unpack_from('<iq',b,pr)==(0,0) and struct.unpack_from('<iq',b,pr+12)==struct.unpack_from('<iq',b,pm+12):
            ok=True
            if want: struct.pack_into('<iq',b,pr,0,pid)
    rep['reflection_post_data']=('ON' if want else 'off') if ok else ('NOT FOUND (skipped)' if want else 'off (not found)')
    _atomic_write(os.path.join(data_dir,'globalgamemanagers.assets'),bytes(b))
    return rep

SETTINGS_FILE = 'belmont_settings.json'

def here_dir(): return os.path.dirname(os.path.abspath(__file__))

def is_game_dir(d):
    try: return os.path.exists(os.path.join(d, 'GameAssembly.dll')) and any(f.endswith('_Data') and os.path.isdir(os.path.join(d, f)) for f in os.listdir(d))
    except OSError: return False

def find_game(arg=None):
    for d in ([arg] if arg else []) + [os.path.dirname(here_dir()), here_dir(), os.getcwd()]:
        if d and is_game_dir(d): return os.path.abspath(d)
    return None

def parse_value(v):
    """--set=key=value: True/False, numbers, or a plain string"""
    if v.lower() in ('true', 'false'): return v.lower() == 'true'
    try: return float(v) if '.' in v else int(v)
    except ValueError: return v

def load_cfg():
    cfg = dict(CONFIG)
    p = os.path.join(here_dir(), SETTINGS_FILE)
    if os.path.exists(p):
        try:
            saved = json.load(open(p))
            if 'smooth_motion' not in saved:          # v23: one switch per mode; v22 and older: five switches
                if 'smooth_30' in saved or 'smooth_120' in saved:
                    saved['smooth_motion'] = bool(saved.get('smooth_30', True)) or bool(saved.get('smooth_120', True))
                elif 'smoothing' in saved:
                    saved['smooth_motion'] = bool(saved.get('smoothing', True)) and bool(saved.get('smooth_objects', True))
            # v0.28: TAA is a 4th menu entry instead of replacing "None"; reflection AA is a choice instead of a switch
            if 'taa_menu' not in saved and 'taa_replaces_none' in saved: saved['taa_menu'] = bool(saved['taa_replaces_none'])
            if isinstance(saved.get('reflection_aa'), bool): saved['reflection_aa'] = 'smaa' if saved['reflection_aa'] else 'off'
            cfg.update({k: v for k, v in saved.items() if k in CONFIG})
        except Exception: pass
    if str(cfg.get('reflection_aa', 'smaa')).lower() not in REFLECTION_AA_CHOICES: cfg['reflection_aa'] = 'smaa'
    return cfg

VK_NAMES = dict(('F%d' % i, 0x6f + i) for i in range(1, 13))
def key_vk(cfg):
    """virtual-key code of the camera key, 0 when it is off"""
    if not cfg.get('camera_toggle', False): return 0
    k = cfg.get('camera_toggle_key', 'F8')
    if isinstance(k, str): return VK_NAMES.get(k.strip().upper(), 0)
    try: return int(k) if 0 < int(k) < 0xff else 0
    except (TypeError, ValueError): return 0

def save_cfg(cfg):
    _atomic_write(os.path.join(here_dir(), SETTINGS_FILE), json.dumps({k: cfg[k] for k in CONFIG if k in cfg}, indent=1).encode())

def _data_dir(game): return os.path.join(game, [f for f in os.listdir(game) if f.endswith('_Data') and os.path.isdir(os.path.join(game, f))][0])

def _atomic_write(path, data):
    """Write next to the target, then swap it in: an interrupted install (window closed, crash, power cut) leaves the
    previous file in place instead of a truncated one. Retries the swap for a few seconds (antivirus scan, Steam)."""
    import time
    tmp = path + '.belmont_tmp'
    with open(tmp, 'wb') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    for i in range(20):
        try:
            os.replace(tmp, path); return
        except PermissionError:
            if i < 19: time.sleep(0.5)
    try: os.remove(tmp)
    except OSError: pass
    raise PermissionError("%s could not be replaced (the game or another program has it open). Close the game and "
                          "click Apply again; the previous file is unchanged." % os.path.basename(path))

def _atomic_copy(src, dst):
    _atomic_write(dst, open(src, 'rb').read())
    try: shutil.copystat(src, dst)
    except OSError: pass

def _refresh_stock(game, log):
    stock_dir = os.path.join(here_dir(), 'stock'); os.makedirs(stock_dir, exist_ok=True)
    dll = os.path.join(game, 'GameAssembly.dll'); data_dir = _data_dir(game)
    cur = open(dll, 'rb').read()
    try: modded = has_mod_sections(cur) if cur[:2] == b'MZ' else None
    except Exception: modded = None
    if modded is None:
        log("GameAssembly.dll is damaged (%d bytes, probably an interrupted install); it is rebuilt from the stock copy." % len(cur))
    elif not modded:
        sp = os.path.join(stock_dir, 'GameAssembly.dll')
        if not os.path.exists(sp) or hashlib.sha256(open(sp, 'rb').read()).hexdigest() != hashlib.sha256(cur).hexdigest():
            log("Vanilla GameAssembly.dll found, saving it as the stock copy.")
            _atomic_copy(dll, sp)
            for f in ('globalgamemanagers', 'globalgamemanagers.assets'): _atomic_copy(os.path.join(data_dir, f), os.path.join(stock_dir, f))
    for f in ('GameAssembly.dll', 'globalgamemanagers', 'globalgamemanagers.assets'):
        if not os.path.exists(os.path.join(stock_dir, f)):
            raise RuntimeError("Missing stock copy of %s. Verify the game files in Steam (Properties > Installed Files > Verify) and run again." % f)
    return stock_dir, dll, data_dir

def install(game, cfg, log, bundles=True):
    stock_dir, dll, data_dir = _refresh_stock(game, log)
    spec = load_spec()
    stock = open(os.path.join(stock_dir, 'GameAssembly.dll'), 'rb').read()
    if hashlib.sha256(stock).hexdigest() != spec['stock_sha256']:
        log("Note: this is a different game build than the patcher was made for. Searching by signature...")
    log("Belmont Patcher %s, game folder: %s" % (PATCHER_VERSION, game))
    log("Patching GameAssembly.dll...")
    out, rep = patch_dll(stock, cfg, spec)
    rep.update(patch_assets(data_dir, stock_dir, cfg))
    _atomic_write(dll, out)
    log("GameAssembly.dll written (sha256 %s)" % hashlib.sha256(out).hexdigest()[:16])
    if bundles:
        log("Updating asset bundles (menu text)...")
        try: patch_bundles(game, here_dir(), cfg, log, rep)
        except Exception as e:
            log("Asset bundle step failed: %r. The DLL patch is still installed." % (e,)); rep['menu_text'] = rep['taa_menu'] = 'FAILED'
    w = max(len(k) for k in rep)
    log("")
    for k in sorted(rep): log("  %-*s  %s" % (w, k, rep[k]))
    n = int(cfg.get('sim_rate', 1) or 1)
    if n > 1 and rep.get('tick_rate_fast') != 'ON': n = 1
    how = '' if n == 1 else ' (scheduler: stock 30 Hz frames, input on the next tick; experimental)'
    log("\nDone. Tick rate: %d Hz%s." % (30 * n, how))
    if rep.get('camera_toggle', '').startswith('ON'):
        log("In game, %s switches between the closer camera and the stock framing." % cfg.get('camera_toggle_key', 'F8'))
    if rep.get('ultrawide') == 'ON':
        log("Ultra-wide rendering is on: 2560x1080, 3440x1440 and 5120x1440 render at their own width when your monitor offers them.")
    return rep

def uninstall(game, log):
    stock_dir, dll, data_dir = _refresh_stock(game, log)
    _atomic_copy(os.path.join(stock_dir, 'GameAssembly.dll'), dll)
    for f in ('globalgamemanagers', 'globalgamemanagers.assets'): _atomic_copy(os.path.join(stock_dir, f), os.path.join(data_dir, f))
    log("Restored the original GameAssembly.dll and game settings files.")
    try: restore_bundles(game, here_dir(), log)
    except Exception as e: log("Asset bundle restore failed: %r" % (e,))
    log("Uninstall complete. The game is back to stock.")

def main():
    args = sys.argv[1:]
    if '--gui' in args or not args and os.path.basename(sys.executable).lower().startswith('pythonw'):
        import traceback
        errp = os.path.join(here_dir(), 'belmont_error.log')
        try:
            import tkinter
        except Exception:
            msg = ("This Python (%s, %s) has no tkinter, so the settings window can't open.\n"
                   "Reinstall Python from python.org and keep 'tcl/tk and IDLE' ticked, or use the command line:\n"
                   "  python belmont_patcher.py\n" % (sys.version.split()[0], sys.executable))
            open(errp, 'w').write(msg + traceback.format_exc()); print(msg); sys.exit(2)
        try:
            return run_gui()
        except Exception:
            tb = traceback.format_exc()
            open(errp, 'w').write("Python %s at %s\n%s" % (sys.version, sys.executable, tb))
            print(tb); print("Saved to " + errp); sys.exit(3)
    game_arg = next((a for a in args if not a.startswith('-')), None)
    game = find_game(game_arg)
    if not game:
        print("Game folder not found. Put the 'Belmont Patcher' folder inside the game folder, or pass the game folder as an argument."); sys.exit(1)
    cfg = load_cfg()
    for a in args:
        if a.startswith('--set='):
            k, v = a[6:].split('=', 1)
            if k not in CONFIG: print("Unknown option %r (see CONFIG at the top of this file)." % k); sys.exit(1)
            cfg[k] = parse_value(v)
    if '--uninstall' in args: uninstall(game, log)
    else: install(game, cfg, log, bundles='--no-bundles' not in args)

# ============================================================================
#  Asset bundles: resolution menu names
#  (needs UnityPy, installed on first use)
#  v20: the texture mipmaps of v15-v19 are gone. Bundles an older version rewrote for mipmaps are put back to
#  their stock copies on the next Install, and the Addressables catalog is rewritten from the stock one.
# ============================================================================
BUNDLE_PKGS = [('UnityPy', 'UnityPy>=1.25,<1.26')]
RES_STOCK = [(800,600),(1280,720),(1024,768),(1280,1024),(1650,1050),(1920,1080),(2560,1080),(1920,1200),
             (2560,1440),(3440,1440),(5120,1440),(3840,2160)]
# must match RES_LIST used for the GameAssembly.dll resolution patch (gen_spec.py): menu entry k gets label RES_NEW[k]
RES_NEW   = [(1280,720),(1366,768),(1600,900),(1920,1080),(2560,1080),(2560,1440),(3440,1440),(3840,2160),
             (5120,1440),(5120,2880),(5760,3240),(7680,4320)]
BUNDLE_VER = 7   # stored per bundle in bundle_state.json; a bundle written by another version is redone from its stock copy

def _sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''): h.update(blk)
    return h.hexdigest()

def ensure_packages(log):
    import importlib, importlib.util, subprocess, site
    def missing(): return [pip for mod, pip in BUNDLE_PKGS if importlib.util.find_spec(mod) is None]
    m = missing()
    if not m: return True
    log("Installing the Python package needed for the menu text (one time, needs internet):")
    log("  " + ", ".join(m))
    kw = {}
    if os.name == 'nt': kw['creationflags'] = 0x08000000   # no console window
    def run(args):
        try:
            p = subprocess.Popen([sys.executable, '-m'] + args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, errors='replace', **kw)
        except OSError as e:
            log("  " + str(e)); return 1
        for line in p.stdout:
            line = line.rstrip()
            if line and not line.startswith('  Downloading') and 'already satisfied' not in line: log("  " + line)
        return p.wait()
    if run(['pip', '--version']) != 0: run(['ensurepip', '--upgrade'])
    if run(['pip', 'install', '--disable-pip-version-check'] + m) != 0:
        run(['pip', 'install', '--user', '--disable-pip-version-check'] + m)
    try:
        us = site.getusersitepackages()
        if us not in sys.path and os.path.isdir(us): sys.path.append(us)
    except Exception: pass
    importlib.invalidate_caches()
    m = missing()
    if m: log("Could not install: " + ", ".join(m) + ". The menu text was skipped."); return False
    log("Packages installed.")
    return True

_LABEL = re.compile(r'^(\d{3,4})(\D{1,3})(\d{3,4})$')
# English text the shipped game leaves empty, so Unity falls back to French ("Aucun" in the Anti-Aliasing option).
# (string table entry id, text); applied only to the English settings table and only while the entry is empty.
EN_FIXES = [(412388007, 'None')]
def _relabel(env):
    n = 0
    for o in env.objects:
        if o.type.name != 'MonoBehaviour': continue
        try: raw = o.get_raw_data()
        except Exception: continue
        if b'3440' not in raw or b'5120' not in raw: continue
        try: t = o.read_typetree()
        except Exception: continue
        td = t.get('m_TableData') if isinstance(t, dict) else None
        if not isinstance(td, list): continue
        hit = nfix = 0
        loc = t.get('m_LocaleId') if isinstance(t.get('m_LocaleId'), dict) else {}
        if loc.get('m_Code') == 'en':
            fix = dict(EN_FIXES)
            for ent in td:
                if ent.get('m_Id') in fix and not (ent.get('m_Localized') or '').strip():
                    ent['m_Localized'] = fix[ent['m_Id']]; nfix += 1
        for ent in td:
            mm = _LABEL.match(ent.get('m_Localized') or '')
            if not mm: continue
            k = (int(mm.group(1)), int(mm.group(3)))
            if k in RES_STOCK:
                w, h = RES_NEW[RES_STOCK.index(k)]
                ent['m_Localized'] = '%d%s%d' % (w, mm.group(2), h); hit += 1
        if hit >= 10: o.save_typetree(t); n += hit + nfix   # only the table that holds the resolution names
    return n

def _replace(tmp, dst, log):
    """os.replace with retries: on Windows the rename of a freshly written file is sometimes refused for a moment
    (antivirus scan, Steam, the game itself still open)"""
    import time
    for i in range(20):
        try: os.replace(tmp, dst); return True
        except PermissionError: time.sleep(0.5)
    try: os.remove(tmp)
    except OSError: pass
    log("  %s: could not be written (file in use? close the game), skipped for now" % os.path.basename(dst)[:12])
    return False

def _save_state(st, path):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f: json.dump(st, f)
    os.replace(tmp, path)

def _copy_back(src, dst, log):
    """put a stock copy back over the game's file (via a temporary file, so a locked file is reported, not half-written)"""
    tmp = dst + '.tmp'
    shutil.copy2(src, tmp)
    return _replace(tmp, dst, log)

def _bundle_paths(game, here):
    data_dir = [os.path.join(game, d) for d in os.listdir(game) if d.endswith('_Data') and os.path.isdir(os.path.join(game, d))][0]
    aa = os.path.join(data_dir, 'StreamingAssets', 'aa')
    st = os.path.join(here, 'stock')
    return dict(bdir=os.path.join(aa, 'StandaloneWindows64'), cat=os.path.join(aa, 'catalog.json'),
                sdir=os.path.join(st, 'bundles'), scat=os.path.join(st, 'catalog.json'), stp=os.path.join(st, 'bundle_state.json'),
                old=os.path.join(st, 'mip_state.json'))

def restore_bundles(game, here, log):
    P = _bundle_paths(game, here)
    n = 0
    if os.path.isdir(P['sdir']):
        for f in os.listdir(P['sdir']):
            if f.endswith('.bundle'): shutil.copy2(os.path.join(P['sdir'], f), os.path.join(P['bdir'], f)); n += 1
    if os.path.exists(P['scat']): shutil.copy2(P['scat'], P['cat'])
    if os.path.exists(P['stp']):
        st = json.load(open(P['stp'])); st['applied'] = {}; st['out'] = {}; st['mod'] = {}; st.pop('cat_out', None)
        _save_state(st, P['stp'])
    log("Restored %d asset bundles and the Addressables catalog." % n)

def _scan_bundles(names, src_of, need, log):
    """one pass over every bundle: the ones holding the resolution menu table (one per language, 'labels') and the one
    holding the Video settings definition ('video')"""
    import UnityPy, gc
    log("Scanning %d asset bundles for the menu text (one time, a few minutes)..." % len(names))
    labels, video = [], []
    for i, f in enumerate(names):
        try:
            env = UnityPy.load(src_of(f))
            for o in env.objects:
                if o.type.name == 'MonoBehaviour':
                    raw = o.get_raw_data()
                    if 'labels' in need and b'3440' in raw and b'1440' in raw and b'5120' in raw and b'Settings_Video' not in raw:
                        labels.append(f)
                    if 'video' in need and b'video/antialiasing' in raw and _AA_OPTS[0] in raw: video.append(f)
            del env
        except Exception: pass
        if i % 200 == 199: log("  %d/%d" % (i + 1, len(names))); gc.collect()
    gc.collect()
    return sorted(set(labels)), sorted(set(video))

# Video settings: the Anti-Aliasing EnumSetting's options, each serialized as id string, LocalizedString name (table
# reference string, entry key id int64, key string, fallback state, wait flag, variable count), int value, float data,
# bool supported.
_AA_OPTS = [b'\x08\x00\x00\x00disabled', b'\x04\x00\x00\x00fxaa', b'\x04\x00\x00\x00smaa', b'\x03\x00\x00\x00taa\x00']
def _aa_options(raw):
    """[(id, keyid_offset, keyid, value, supported_offset, supported)] for the 4 options, or None if the layout is not the expected one"""
    k = raw.find(b'video/antialiasing')
    p = raw.find(_AA_OPTS[0], k) if k >= 0 else -1
    if p < 4 or struct.unpack_from('<i', raw, p - 4)[0] != 4: return None
    out = []
    def sstr(q):
        n = struct.unpack_from('<i', raw, q)[0]
        if not 0 <= n < 256: raise ValueError
        return raw[q + 4:q + 4 + n], q + 4 + ((n + 3) & ~3)
    try:
        for want_id, val in zip((b'disabled', b'fxaa', b'smaa', b'taa'), range(4)):
            sid, q = sstr(p)
            if sid != want_id: return None
            ref, q = sstr(q)
            if not ref.startswith(b'GUID:'): return None
            kpos = q; keyid = struct.unpack_from('<q', raw, q)[0]; q += 8
            key, q = sstr(q)
            fb, wait, nvars = struct.unpack_from('<3i', raw, q)   # fallback state, wait-for-completion, local variables count
            if not (0 <= fb < 8 and wait in (0, 1) and nvars == 0): return None
            q += 12
            value, data = struct.unpack_from('<if', raw, q); q += 8
            sup = raw[q]
            if value != val or sup not in (0, 1): return None
            out.append((sid.decode(), kpos, keyid, value, q, sup)); p = q + 4
    except (ValueError, struct.error): return None
    return out

def _taa_unhide(env):
    """the Anti-Aliasing menu's TAA option ships with supported = 0, so the dropdown skips it; listed, it works as shipped:
    the game's own CameraVideoSettings.OnAntiAliasingChanged maps menu value 3 to URP's temporal anti-aliasing"""
    n = 0
    for o in env.objects:
        if o.type.name != 'MonoBehaviour': continue
        try: raw = o.get_raw_data()
        except Exception: continue
        if b'video/antialiasing' not in raw: continue
        opts = _aa_options(raw)
        if not opts: continue
        b = bytearray(raw); b[opts[3][4]] = 1   # taa.supported
        o.set_raw_data(bytes(b)); n += 1
    return n

def _unmip(P, st, keep, log):
    """put back to stock every bundle an older version rewrote that is not in `keep` (the texture mipmaps of v15-v19);
    the stock copy is removed once the game's file is byte-identical to it again"""
    n = 0; failed = []
    for f in sorted(set(st.get('applied', {})) | set(st.get('mod', {})) | set(st.get('out', {}))):
        if f in keep: continue
        gp, sp = os.path.join(P['bdir'], f), os.path.join(P['sdir'], f)
        if os.path.exists(sp) and os.path.exists(gp):
            ssha, gsha = _sha(sp), _sha(gp)
            ours = st.get('out', {}).get(f)
            updated = ours is not None and gsha not in (ssha, ours)   # neither stock nor ours: Steam replaced it, keep it
            if gsha != ssha and not updated:                          # the file this patcher wrote: put stock back
                if not _copy_back(sp, gp, log): failed.append(f); continue
                n += 1
            os.remove(sp)      # identical to the game's file now, or stale after an update
        for k in ('applied', 'out', 'mod'): st.get(k, {}).pop(f, None)
    # stock copies left by an interrupted run (copy made, file never rewritten): drop them when identical to the game's file
    if os.path.isdir(P['sdir']):
        for f in os.listdir(P['sdir']):
            if not f.endswith('.bundle') or f in keep or f in st.get('applied', {}): continue
            gp, sp = os.path.join(P['bdir'], f), os.path.join(P['sdir'], f)
            if os.path.exists(gp) and _sha(gp) == _sha(sp): os.remove(sp)
    for k in ('chars', 'mipb'): st.pop(k, None)
    if n: log("  %d asset bundles put back to stock (texture mipmaps are no longer part of the mod)." % n)
    return failed

def _catalog_sizes(cat_path):
    """{bundle file name without .bundle: size} from an Addressables catalog.json (the file names are content hashes,
    so a bundle that keeps its name across a game update kept its content)"""
    j = json.load(open(cat_path, encoding='utf-8'))
    ids = j['m_InternalIds']; ed = base64.b64decode(j['m_EntryDataString']); x = base64.b64decode(j['m_ExtraDataString'])
    n = struct.unpack_from('<i', ed, 0)[0]; out = {}
    for k in range(n):
        iid, prov, dep, dh, di, pk, rt = struct.unpack_from('<7i', ed, 4 + 28 * k)
        sid = ids[iid]
        if not sid.endswith('.bundle') or di < 0: continue
        q = di + 1; q += 1 + x[q]; q += 1 + x[q]
        ln = struct.unpack_from('<i', x, q)[0]
        try: rec = json.loads(x[q + 4:q + 4 + ln].decode('utf-16-le'))
        except ValueError: continue
        out[sid.replace(chr(92), '/').split('/')[-1][:-7]] = rec.get('m_BundleSize')
    return out

def _heal_old(P, st, log):
    """stock copies set aside as .old by a game update (or by v24's first run after the update of 2026-10-16) whose bundle
    is still in the current catalog with the same size are still the originals: put them back as the stock copy and as
    the game's file, and redo their edits from them"""
    olds = [f for f in os.listdir(P['sdir'])] if os.path.isdir(P['sdir']) else []
    olds = [f for f in olds if f.endswith('.bundle.old')]
    if not olds: return
    try: sizes = _catalog_sizes(P['scat'])
    except Exception as e: log("  (could not read the catalog to check the old stock copies: %r)" % (e,)); return
    n = 0
    for f in olds:
        name = f[:-4]; op = os.path.join(P['sdir'], f); sp = os.path.join(P['sdir'], name); gp = os.path.join(P['bdir'], name)
        if sizes.get(name[:-7]) != os.path.getsize(op): continue
        os.replace(op, sp)
        if os.path.exists(gp) and _sha(gp) != _sha(sp): _copy_back(sp, gp, log)
        for k in ('applied', 'out', 'mod'): st.get(k, {}).pop(name, None)
        n += 1
    if n:
        for k in ('labels', 'video'): st.pop(k, None)
        log("  %d original asset bundle(s) recovered from before the game update; the menu edits are redone from them." % n)

def patch_bundles(game, here, cfg, log, rep):
    want_lbl = bool(cfg.get('resolutions', True)); want_taa = bool(cfg.get('taa_menu', True))
    P = _bundle_paths(game, here)
    os.makedirs(P['sdir'], exist_ok=True)
    st = json.load(open(P['stp'])) if os.path.exists(P['stp']) else {}
    st.setdefault('applied', {}); st.setdefault('out', {})
    # stock catalog (refreshed when the game updates)
    csha = _sha(P['cat'])
    if not os.path.exists(P['scat']):
        shutil.copy2(P['cat'], P['scat'])
    elif 'cat_out' in st and csha not in (_sha(P['scat']), st['cat_out']):
        log("The game's asset catalog changed (game update): saving it as the new stock copy.")
        shutil.copy2(P['cat'], P['scat'])
        sizes = _catalog_sizes(P['scat'])
        # a stock copy whose bundle keeps its name (= content hash) and size in the new catalog is still the original;
        # only bundles the update replaced or removed are set aside
        for f in os.listdir(P['sdir']):
            if f.endswith('.bundle') and sizes.get(f[:-7]) != os.path.getsize(os.path.join(P['sdir'], f)):
                os.replace(os.path.join(P['sdir'], f), os.path.join(P['sdir'], f + '.old'))
        keep = {k: st[k] for k in ('labels', 'video') if k in st and all(sizes.get(b[:-7]) is not None for b in st[k])}
        st = {'applied': {}, 'out': {}}; st.update(keep)
    _heal_old(P, st, log)
    def edit_plan():
        e = {}
        if want_lbl:
            for f in st.get('labels', []): e.setdefault(f, []).append('lbl')
        if want_taa:
            for f in st.get('video', []): e.setdefault(f, []).append('taa')
        return e
    failed = _unmip(P, st, set(edit_plan()), log)
    _save_state(st, P['stp'])
    if not (want_lbl or want_taa) and not st['applied']:
        if os.path.exists(P['scat']) and _sha(P['cat']) != _sha(P['scat']): shutil.copy2(P['scat'], P['cat'])
        st.pop('cat_out', None); _save_state(st, P['stp'])
        rep['menu_text'] = 'off (stock names)' + (', %d bundle(s) still locked, click Apply again' % len(failed) if failed else '')
        rep['taa_menu'] = 'off'; return
    if want_lbl or want_taa:
        if not ensure_packages(log):
            rep['menu_text'] = rep['taa_menu'] = 'SKIPPED (package missing)'; return
        import UnityPy, gc
        names = sorted(f for f in os.listdir(P['bdir']) if f.endswith('.bundle'))
        src_of = lambda f: os.path.join(P['sdir'], f) if os.path.exists(os.path.join(P['sdir'], f)) else os.path.join(P['bdir'], f)
        need = [k for k, w in (('labels', want_lbl), ('video', want_taa)) if w and k not in st]
        if need:
            lb, vd = _scan_bundles(names, src_of, need, log)
            if 'labels' in need: st['labels'] = lb
            if 'video' in need: st['video'] = vd
            _save_state(st, P['stp'])
    edits = edit_plan()
    tag = lambda e: '%d:%s' % (BUNDLE_VER, ','.join(sorted(e)))
    nlbl = ntaa = 0
    for f in sorted(set(edits) | set(st['applied'])):
        gp, sp = os.path.join(P['bdir'], f), os.path.join(P['sdir'], f)
        if not os.path.exists(gp): continue
        gsha = _sha(gp)
        if os.path.exists(sp) and f in st['out'] and gsha not in (_sha(sp), st['out'][f]):
            shutil.copy2(gp, sp); st['applied'].pop(f, None); st['out'].pop(f, None)   # game updated this bundle
        want = edits.get(f)
        if want and st['applied'].get(f) == tag(want) and st['out'].get(f) == gsha:
            md = (st.get('mod') or {}).get(f) or {}
            nlbl += bool(isinstance(md, dict) and md.get('lbl')); ntaa += bool(isinstance(md, dict) and md.get('taa')); continue
        if not want:
            if os.path.exists(sp) and gsha != _sha(sp) and not _copy_back(sp, gp, log): failed.append(f); continue
            st['applied'].pop(f, None); st['out'].pop(f, None); continue
        # always work from the stock copy: UnityPy keeps the file it loaded open, and Windows refuses to replace an open file
        if not os.path.exists(sp): shutil.copy2(gp, sp)
        env = UnityPy.load(sp); done = {}
        if 'lbl' in want: done['lbl'] = _relabel(env)
        if 'taa' in want: done['taa'] = _taa_unhide(env)
        if any(done.values()):
            tmp = gp + '.tmp'
            with open(tmp, 'wb') as fo: fo.write(env.file.save(packer='lz4'))
            del env; gc.collect()
            if not _replace(tmp, gp, log): failed.append(f); continue
            log("  %s: %s" % (f[:12], ', '.join(x for x in ((done.get('lbl') and '%d menu texts' % done['lbl']),
                                                            (done.get('taa') and 'TAA listed in the Anti-Aliasing menu')) if x)))
        else:
            del env; gc.collect()
            if gsha != _sha(sp) and not _copy_back(sp, gp, log): failed.append(f); continue
        st['applied'][f] = tag(want); st['out'][f] = _sha(gp); st.setdefault('mod', {})[f] = {k: bool(v) for k, v in done.items()}
        nlbl += bool(done.get('lbl')); ntaa += bool(done.get('taa'))
        _save_state(st, P['stp'])
    # catalog: rewritten from the stock one, CRC cleared for every bundle that differs from stock (same-length edit, offsets stay valid)
    modified = set(f[:-7] for f in st['applied'] if os.path.exists(os.path.join(P['sdir'], f))
                   and st['out'].get(f) != _sha(os.path.join(P['sdir'], f)))
    text = open(P['scat'], encoding='utf-8').read()
    km = re.search(r'"m_ExtraDataString":"([^"]*)"', text)
    x = bytearray(base64.b64decode(km.group(1)))
    pat = re.compile(rb'"\x00m\x00_\x00H\x00a\x00s\x00h\x00"\x00:\x00"\x00((?:[0-9a-f]\x00)+)"\x00,\x00"\x00m\x00_\x00C\x00r\x00c\x00"\x00:\x00((?:[0-9]\x00)+)')
    ncrc = 0
    for mm in pat.finditer(bytes(x)):
        if mm.group(1).decode('utf-16-le') in modified:
            d = len(mm.group(2)) // 2
            x[mm.start(2):mm.end(2)] = ('0' + ' ' * (d - 1)).encode('utf-16-le'); ncrc += 1
    if ncrc < len(modified):
        log("  Warning: %d modified bundle(s) not found in the catalog; they may fail to load." % (len(modified) - ncrc))
    text = text[:km.start(1)] + base64.b64encode(bytes(x)).decode() + text[km.end(1):]
    with open(P['cat'] + '.tmp', 'w', encoding='utf-8', newline='') as fo: fo.write(text)
    if not _replace(P['cat'] + '.tmp', P['cat'], log): raise PermissionError('catalog.json could not be replaced')
    st['cat_out'] = _sha(P['cat'])
    _save_state(st, P['stp'])
    rep['menu_text'] = ('ON (%d languages)' % nlbl) if want_lbl else 'off (stock names)'
    rep['taa_menu'] = ('ON' if ntaa else 'NOT FOUND (skipped)') if want_taa else 'off'
    if failed: rep['menu_text'] += ', %d bundle(s) could not be written, click Apply again' % len(failed)

# ============================================================================
#  Settings window (python belmont_patcher.py --gui, or double-click Install.bat)
# ============================================================================
# (key, label, description) = a tick box; (key, label, description, [(text, value), ...]) = a drop-down
GUI_GROUPS = [
    ("Image Quality", [
        ('resolutions', "Improved Resolutions", "Adds additional resolutions and forces the game to render beyond 4K instead of upscaling"),
        ('ultrawide', "Ultra-Wide Rendering (Experimental)", "The ultra-wide entries render at their own width instead of a 16:9 image with black bars"),
        ('taa_menu', "TAA in the Anti-Aliasing Menu", "The game's hidden temporal anti-aliasing becomes a 4th entry after None, FXAA and SMAA"),
        ('smaa_high', "SMAA High", "SMAA quality High instead of Low"),
        ('reflection_aa', "Anti-Aliasing in Reflections", "Water and mirror reflections (very bright reflected lights may look a touch dimmer)",
         [("Off (stock)", 'off'), ("SMAA", 'smaa'), ("TAA (experimental)", 'taa')]),
    ]),
    ("Graphics", [
        ('shadow_quality', "Better Shadows", "Soft shadows, higher shadow resolution"),
        ('reflection_shadows', "Shadows in Reflections", "Water and mirror reflections show shadows (costs GPU time)"),
        ('lightshaft_quality', "Better Light Shafts", "Full resolution, 32 samples"),
        ('anisotropic_16x', "16x Anisotropic Filtering", "Sharper textures at an angle"),
    ]),
    ("Camera", [
        ('camera_zoom', "Closer Camera", "Characters larger on screen; boss arenas and the wide areas keep the game's own framing"),
        ('camera_toggle', "F8 Switches to the Stock Camera in Game", "For comparing the two; a sound confirms each switch"),
    ]),
    ("Motion", [
        ('smooth_motion', "Smooth Motion", "Moving objects, prop animations, cutscene camera and walking drawn at your frame rate"),
    ]),
    ("Gameplay", [
        ('skip_splash', "Skip Startup Logos", "Boot straight to the title screen (first-launch setup screens still appear)"),
        ('dialogue_preload', "Dialogue Preload", "No hitch on the first line of a conversation"),
        ('font_preload', "Font Preload", "Removes hitching in the game from font loading"),
    ]),
]
GUI_COLUMNS = [["Image Quality", "Graphics", "Gameplay"], ["Camera", "Motion"]]
GUI_SUB = {'ultrawide': 'resolutions'}   # sub-option: indented, greyed out while its parent is unticked
SIM_CHOICES = [("30 Hz (original, recommended)", 1),
               ("120 Hz input, stock movement (experimental)", 4),
               ("60 Hz input, stock movement (experimental)", 2)]

def run_gui():
    import threading, queue, traceback
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    from tkinter.scrolledtext import ScrolledText
    cfg = load_cfg()
    root = tk.Tk(); root.title("Belmont Patcher %s by %s (made with AI assistance)" % (PATCHER_VERSION, PATCHER_AUTHOR))
    try: scale = max(1.0, root.winfo_fpixels('1i') / 96.0)   # pixel sizes follow the display scaling (fonts already do)
    except Exception: scale = 1.0
    root.minsize(int(790 * scale), int(690 * scale)); wrap = int(360 * scale)
    q = queue.Queue()
    def glog(*a): q.put(' '.join(str(x) for x in a))
    game = [find_game()]
    top = ttk.Frame(root, padding=10); top.pack(fill='both', expand=True)
    gf = ttk.Frame(top); gf.pack(fill='x')
    ttk.Label(gf, text="Game folder:").pack(side='left')
    gvar = tk.StringVar(value=game[0] or "(not found, click Browse)")
    ttk.Label(gf, textvariable=gvar, foreground='#555').pack(side='left', padx=6, fill='x', expand=True)
    def browse():
        d = filedialog.askdirectory(title="Select the Castlevania Belmont's Curse game folder")
        if d and is_game_dir(d): game[0] = os.path.abspath(d); gvar.set(game[0])
        elif d: messagebox.showerror("Belmont Patcher", "That folder doesn't contain GameAssembly.dll and the game's _Data folder.")
    ttk.Button(gf, text="Browse...", command=browse).pack(side='right')
    vars_, choices, boxes = {}, {}, {}
    small = ('Segoe UI', 8)
    body = ttk.Frame(top); body.pack(fill='x', pady=(8, 4))
    groups = dict(GUI_GROUPS)
    def tip(parent, text, indent=0): ttk.Label(parent, text=text, foreground='#777', font=small, wraplength=wrap, justify='left').pack(anchor='w', padx=(int(24 * scale) + indent, 0))
    for col, titles in enumerate(GUI_COLUMNS):
        for row, title in enumerate(titles):
            lf = ttk.LabelFrame(body, text=title, padding=6)
            lf.grid(row=row, column=col, sticky='nsew', padx=4, pady=4)
            if title == "Motion":
                sf = ttk.Frame(lf); sf.pack(anchor='w', pady=(0, 2))
                ttk.Label(sf, text="Input Rate").pack(side='left')
                cur = int(cfg.get('sim_rate', 1) or 1)
                svar = tk.StringVar(value=next((n for n, v in SIM_CHOICES if v == cur), SIM_CHOICES[0][0]))
                ttk.Combobox(sf, textvariable=svar, values=[n for n, _ in SIM_CHOICES], state='readonly', width=40).pack(side='left', padx=6)
                tip(lf, "The rate the game runs at. 120 Hz makes Rose react to your inputs sooner; everything else keeps its stock timing")
            for item in groups[title]:
                key, label, text = item[:3]; indent = int(18 * scale) if key in GUI_SUB else 0
                if len(item) > 3:
                    opts = item[3]; cur = cfg.get(key)
                    cf = ttk.Frame(lf); cf.pack(anchor='w', pady=(4, 0))
                    ttk.Label(cf, text=label).pack(side='left')
                    v = tk.StringVar(value=next((n for n, val in opts if val == cur), opts[0][0])); choices[key] = (v, opts)
                    ttk.Combobox(cf, textvariable=v, values=[n for n, _ in opts], state='readonly', width=18).pack(side='left', padx=6)
                else:
                    v = tk.BooleanVar(value=bool(cfg.get(key, True))); vars_[key] = v
                    boxes[key] = ttk.Checkbutton(lf, text=label, variable=v); boxes[key].pack(anchor='w', padx=(indent, 0))
                tip(lf, text, indent)
                if key == 'camera_zoom':
                    zf = ttk.Frame(lf); zf.pack(anchor='w', pady=(0, 2), padx=(int(24 * scale), 0))
                    ttk.Label(zf, text="Zoom factor (1.0 = stock)", font=small).pack(side='left')
                    zvar = tk.StringVar(value=str(cfg.get('camera_zoom_factor', 1.25)))
                    ttk.Spinbox(zf, from_=1.0, to=1.6, increment=0.05, width=6, textvariable=zvar).pack(side='left', padx=4)
    def sync_subs(*_):
        for sub, parent in GUI_SUB.items(): boxes[sub].state(['!disabled'] if vars_[parent].get() else ['disabled'])
    for parent in set(GUI_SUB.values()): vars_[parent].trace_add('write', sync_subs)
    sync_subs()
    body.columnconfigure(0, weight=1); body.columnconfigure(1, weight=1)
    bf = ttk.Frame(top); bf.pack(fill='x', pady=6)
    logw = ScrolledText(top, height=12, font=('Consolas', 9), state='disabled'); logw.pack(fill='both', expand=True)
    busy = [False]
    def collect():
        c = dict(cfg)
        for k, v in vars_.items(): c[k] = bool(v.get())
        for k, (v, opts) in choices.items(): c[k] = dict(opts).get(v.get(), opts[0][1])
        try: c['camera_zoom_factor'] = max(1.0, min(2.0, float(zvar.get())))
        except ValueError: pass
        c['sim_rate'] = dict(SIM_CHOICES).get(svar.get(), 1)
        return c
    def work(fn):
        try: fn()
        except Exception as e:
            glog("ERROR: %s" % e); glog(traceback.format_exc())
        finally: q.put(None)
    def start(kind):
        if busy[0]: return
        if not game[0]: messagebox.showerror("Belmont Patcher", "Select the game folder first (Browse...)."); return
        if kind == 'install':
            c = collect(); save_cfg(c)
            glog("=== Applying ==="); fn = lambda: install(game[0], c, glog)
        elif kind == 'packages':
            glog("=== Installing the Python packages the patcher needs ===")
            def fn():
                if ensure_packages(glog): glog("All packages are present.")
        else:
            if not messagebox.askyesno("Belmont Patcher", "Restore all original game files?"): return
            glog("=== Restoring the original game files ==="); fn = lambda: uninstall(game[0], glog)
        busy[0] = True
        for b in btns: b.state(['disabled'])
        threading.Thread(target=work, args=(fn,), daemon=False).start()
    btns = [ttk.Button(bf, text="Apply", command=lambda: start('install')),
            ttk.Button(bf, text="Restore to Original", command=lambda: start('uninstall')),
            ttk.Button(bf, text="Install Python/Packages", command=lambda: start('packages'))]
    btns[0].pack(side='left'); btns[1].pack(side='left', padx=8); btns[2].pack(side='left')
    ttk.Label(bf, text="Close the game before applying.", foreground='#777').pack(side='right')
    def pump():
        try:
            while True:
                m = q.get_nowait()
                if m is None:
                    busy[0] = False
                    for b in btns: b.state(['!disabled'])
                    continue
                logw.configure(state='normal'); logw.insert('end', m + '\n'); logw.see('end'); logw.configure(state='disabled')
        except queue.Empty: pass
        root.after(100, pump)
    pump()
    if not game[0]: glog("Game folder not found. Put this folder inside the game folder, or click Browse.")
    else:
        glog("Ready. Choose your options and click Apply.")
        try:
            import importlib.util
            missing = [pip for mod, pip in BUNDLE_PKGS if importlib.util.find_spec(mod) is None]
        except Exception: missing = []
        if missing: glog("The first Apply downloads the Python packages the patcher needs (%s). Internet is needed once." % ", ".join(m.split('>')[0].split('<')[0] for m in missing))
    def on_close():
        if busy[0]:
            messagebox.showwarning("Belmont Patcher", "Still working. Please wait until the log says Done, then close the window.")
            return
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == '__main__':
    main()
