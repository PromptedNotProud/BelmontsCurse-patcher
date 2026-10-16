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
PATCHER_VERSION = 'v0.29.0'   # semantic versioning MAJOR.MINOR.PATCH: features -> MINOR, fixes only -> PATCH; v20..v27 = 0.20.0..0.27.0
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
    'xYJ0IOs2aL1C6z+tTYTs01u8X8I3bflJ3Ibv4BF+PD9NvJZ4gWjS43YCQRNbTmOtcGoF5AWpQr83xMOT4VOo0zVujwHMS/ShCoxF'
    'fgEhjtw1w3mLkADEchFzxsS2OPIk4ua+sRLPGoI99oO/o60izE/aJcjymBRJI2kMRbqIzUYxaktRT8AnAkY2H9PDVHgcm49QcWMJ'
    'kckvIs35AJVRzyTdPKmjSMZJlz5C8ftrljrmmbL9kCRu2jbYqSf6F9tre22v7bW9ttf22l7ba3ttr+21vbbX9tpe22t7ba/ttb22'
    '1/baXttre22v7bW9ttf22l7ba3ttr+21vbbX9tpe22t7ba/ttb221/baXttre22v7bW9ttf22l7ba3ttr+21vbbX9tpem1yvvv3m'
    'lV+34TJcvfruGy54JaCkre/qVOLwpFAo6i7+8fH6Fkp+/llYuD853TvbP1yd7p2/+uu33/yssc7J8dl5WVjxVHHv6Lwv5LyC0u93'
    'd4YSo6HkfHW2d356nIoqG4tOTuleOAX3Ozs/9i9JwaDk7HAo4UIYKILujg/+vJeKlJ4VGTUrcnJWVM1elMxOi6wVBMsPq7ene6ms'
    '0iyVHe39FAfPVS76Po1VWM6nRY5gPN8/3BvKKoZ4ffvmvC+STE7flIJQ+qfVwd7pSSyRRDNE+86bN/tvj46P4uikEm7aidQ9FH2R'
    '4VMg8CSfWS03I5w0lZqiRNqqWh6N01j5zfHhzv7R0KwzWH3n7HB1fLJ3lMqcSWX7hzvfp9crjoW7BztnZ9Db8eHqaOcwPxJV/wga'
    'Xp3/5SQ/kcRacE8Pjl//YW83dVxZfm97RJzF9khiltpTnCFfFcRTgjDx78fHg5DgWXwTvlKWY2/QFL7ZD0JLosrp3tuDQe4k0b7k'
    'EDwkD0Xj7V5fy3CSgxFVDDdsXmbn9aKklbxgpDSzop49+iJFMnSyu3MyDEQT/00ojgdkTSlutJ5T3BhT3UMhK0n6z86GzqwkqLHo'
    '7I/7J6nMVVT2p6GaJQAPj4oSEp/Do9O+CI9kxoHvF+3jZ1NS2enxUMo5YmL38AThOz/dOTp7e3x6mJ4pYhZ8Asoylbm+LEuRE8QA'
    '+1jpfHVwfHySimlck6pE7VlVKSUVl9h3qpoyi7Ok+wrd4ZxFRO7v7MCrg5J2VRwSFb8uVDxZAyhGPV8Uy6niqhRpi903WPL2+5Pj'
    'U8DNfnqmuSuevf7x9euDvfREDE9ej54YQsYb6Hfo1lRIkZ/e7q7eHuUSBPng9R+x0tGPBwex2MqpMq+sxponPx3Qu1D06rJuwiXa'
    'vH++er9e/211fRNuLz7APXYSS9a3d7GItHJfK1zdQZkRueydr+Ge5OH27mOz+nh9c/Hu/R2ZXJkLL3x9eYlNCdUX3UFrq9vrGzLF'
    'JhfXNbTQQpkgXqOy2w+pyJEpXn1/fnyEfdp0DyRKBVX/zn+t1zh2xVTf9E3ocAxakB7vbuoPYdXiQEHT9MNqYVTYVDQ8VPT3zmOJ'
    'cSyXdOuru1TPkiIEMfzL4Wr3kJTn/tHbY3pE5jg+giGuvgdSH+6d78RnceioL/+IGAD/xAwlr2MR6aLd1b+f7pzvxRISS2hy//Ao'
    'FohYsH/051yg+hpvUwmx2QpNU2yVkOTfr8DxCe0KCHrzC2GBGscHt7/criJ8FhyBshCYAkulqlLpta+vkR+UzC9f3MUi0CEqFX1A'
    'fwu/EN3f36yphCQZS9qLW3zHRmOUS6gW6KcE0u4PxwlIFUveHO78n1TgcpUfjg/exDJS21R2+OdUYnLJ2WEsIUNxcUecHZkBPzmC'
    'ZcCIQyEI/agwCgG4MLkUQF6hHDhHBMlFDRUR49y1d6u79x+v/kbNOXI0V+dvzjNIlUi8DHrl8IefUqHpCw8OYplkbKh4spPK1FC2'
    'e7L/JpVGpOzuHP5x7y8J3sR2PxwcxwIrUsEP+6kgseHZyd5uLHEsleR3nEoF+R3nfv0Viq5CaKNOuf2wXt+9v7h6h151bzoLJ6s0'
    'xWOrWVrLkZVcsI5zv2XBX8lm5QDtSnbq8k2yDqXjWCj3mWtX+oSFku0d+sJvL5z6cUwxiSYmccQ4gHjlQUnd1Fmb/Tz4VyPv6xUo'
    '6pVfk8T+XJomlCQQ8f5R9pwKd6J0Iwr3oXRvRtZ2YpELz+jlaDp1MErHYuIlEOgEJQGYXJ3CxSldm7FLMyZ0QcvS5MfbQXePeKb0'
    'JOYexCs0E6gvLtd1HF2ywGPz/Kq9qC/X7z6GUdXe+A9Gf2LsCVGDwVlyQOaOx4LD8euv/w9Q6DfA'
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
           'ultrawide':bool(cfg.get('ultrawide',False)) and bool(cfg.get('resolutions',True))}
    found={}
    for f,oks in feats.items():
        want=wants.get(f,cfg.get(f,False))
        found[f]=all(oks) and all(syms.get(n) for n in spec['needs'].get(f,[]))
        enabled[f]=bool(want and found[f])
    # the scheduler needs its core hooks; a faster tick needs the scheduler, otherwise stay at 30 Hz
    if enabled.get('sim_sched') and not enabled.get('sched_core'): enabled['sim_sched']=False
    if not enabled.get('sim_sched'): enabled['sim_core']=False; enabled['sched_core']=False
    if not enabled.get('resolutions'): enabled['ultrawide']=False
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
