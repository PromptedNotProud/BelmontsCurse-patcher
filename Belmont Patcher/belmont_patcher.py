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
PATCHER_VERSION = 'v0.28.0'   # semantic versioning MAJOR.MINOR.PATCH: features -> MINOR, fixes only -> PATCH; v20..v27 = 0.20.0..0.27.0
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
    'eNrtfWtz3biV4F/p8ofd2arOFN4A+8uWLMtuTfSKpE426UrdIkHQ1kSWtJKcpCeV/77nHAAk+JB05Ss77tnLpK1LEABxHjgvHID/'
    'ePXXcHt3cX316ofv+PffvXpffwzw89VufXd/Gf5aX13U370Olx+vr+7/5913u59u78J3b8LH61dQ9+7+2v9ldfehFtpgG9uKthJK'
    'qtpJwV0QWja18LxhbWPq1lphZWCa2bqxynPNRd0ExbnuWs0Y77DPm/refwh30N3P/3jVhfr+0y2N5zbcXV9+uoeB3tGrL95D6T+w'
    'Oj5VzrWqNZ2UXQevZEwyuBRvnHZM0G/nKgs14rhvsf8/w8/rroOf5p/w8/6XG3pT88t9uBvA+2uNhezv3DGjOy9qfHR92VLV/lVY'
    'eBX+FgvhXlMhdPsMIJ4ePPxtWrcIgn0GCF0BQvmaAggsblkqfh4YkRbW4qCVFGzAh/IOWOF/p2v0iiWQ3Pog6W5ElZ4AJVW0+Syq'
    'rDP8SB9rg8tPnbQNjI0vAsbF+pCZZkKsEmUFsVhmxM8iVpeI5QhatQwtK3h9E2JVbEosNSMWlJjPJdYTw0/E6mbEEhsTq/ITYrG5'
    'eMBipzYgVpVmlnx0ZpVY3YRYnj89s+Bl9oVnVk9GIlY1n1lyY2L5dk4stUAs6VLxZxErzSwJM8uKyNNzaHn9MsTqxIhY+YVT5VR/'
    'FrGeHn4i1nxmqY2J1YUJsUqUvRSx6jSzFBt4eg5t/4rNiNUKOSJWP4lehFhPDz8Sq57PLL0psdqZgVGirCBW/Xl2UiJWmlnKDWj6'
    'csTSaioG6xmxAOHt54rBei1izWeW2ZhYhn0FYjVpZulHZ1bzMjqrdXqtmdW98MxqRjqrmc8suzGxKj4hVrOss2CE7vOJlWaWfnRm'
    '1YUlsAmxGvP0zALnUL3wzMrDT8Sazyy3MbG8mBCrnhtPG88sn2aWYYMA+nLECnZsYGSJ9yLEenr4kVh+PrOqjYnVyfWIBaA1n0+s'
    'NLOMG9D0xYgVuJvMLK4WTHf+uX7WU8NPxJrPrHpTYgWh1pxZjvnPJlabZpZlg7aYQ9tL2g2JpaqpGOyWZlb4XDH4xPAjsdr5zGo2'
    'JpbWE2KVKCuIFRhnn0OsMUyRdGUcLULW4Su8iO9YhomvD1NTfbEo4OMjjxHAgUpwr9tlGlXrgzPTVCWiNo8Iss6ZYsBNJBAr5IRq'
    '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'
    'YX7SL0GWx6Q8jR5ntiKZwWajGPWl6E3AJwJGNh/T41R4GptPUHHtGSKT/UIS7hEqo5xJMnRSR9EcJ5n3BMUfrlnKmA3n9mMzcd2+'
    'GZ1kmPXn9tpe22t7ba/ttb221/baXttre22v7bW9ttf22l7ba3ttr+21vbbX9tpe22t7ba/ttb221/baXttre22v7bW9ttf22l7b'
    'a3ttr+21vbbX9tpe22t7ba/ttb221/baXttre22v7bW9ttf2evx69f13r/x1Gy7D1asfvuP4WRIoaev7OpU4/JojFHUXf/90cwcl'
    'P/8sLNyfnO6d7R+uTvfOX/35++9+1ljn5PjsvCyseKq4d3TeF3JeQem73Z2hxGgoOV+d7Z2fHqeiysaik1O6F07B/c7OT30jKXCg'
    'Z4dDCRfCQBG87vjg93upSOlZkVGzIidnRdWsoWR2WmStIFh+XL093UtllWap7GjvD3HwXOWid2mswnI+LXIE4/n+4d5QVjHE69s3'
    '532RZHLaUgpC6e9WB3unJ7FEEs0Q7Ttv3uy/PTo+iqOTSrjpS6TuoeiLDJ8CgScUzWq5GeGkqdQUJdJW1fJonMbKb44Pd/aPhm6d'
    'weo7Z4er45O9o1TmTCrbP9x5l5pXHAt3D3bOzuBtx4ero53D/EhU/SPoeHX+x5P8RBJrwT09OH79H3u76cWV5Q/2R8RZ7K8SD/Sn'
    'OEO+KoinBGHiT8fHwyTBswAnfKUsx7dBV9iyH4SWRJXTvbcHw7yTRPuSQ/CQPpwab/f6WobTPBhRxXDD5mV2Xi/OtJIXjJRmVtSz'
    'R1+kaA6d7O6cDAPRxH8TiuMBXVOKG63nFDfGVA9QyEqa/Wdnw8usJKix6Oy3+yepzFVU9ruhmiUAD4+KEpo+h0enfREeyYwD3y/6'
    'x8+mpLLT46GUc8TE7uEJwnd+unN09vb49DA9U8Qs+ASEZSpzfVmeRU4QA+xjpfPVwfHxSSqmcU2qErVnVaWUVFxi36lqyizOkuwr'
    'ZIdzFhG5v7MDTQch7ao4JCp+XYh40gZQjHK+KJZTwVUpkha7b7Dk7buT41PAzX56prkrnr3+6fXrg730RAxPXo+eGELGG3jv8FpT'
    'IUX+8HZ39fYolyDIB69/i5WOfjo4ePVnKH91WTfhEtXZP159uL7+y+rmNtxdfIR7bB9Lru/uYxEJ3L5WuLqHMiNy2Xtfwz2x+t39'
    'p2b16eb24v2He9KmMhde+PryErsSqi+6h95Wdze3pGVNLq5r6KGFMkFsRGV3H1ORIy27end+fITvtNTbyQqwnwtcbvNf19c4dsVU'
    '3/Vt6HAMWpCI7m7rj2HV4kBBiPTDamFU2FXUKVT0t85jiSHTAObSHw9Xu4ckAfeP3h7Te5nqH8FgVu+AXod75zvxWRw0Cr3fIqyc'
    'k6hIJa9jEamg3dWfTnfO91KJiV3uHx6lVrFg/+j3qcCwvsbbVEJCeoX6Jd4TOvyHFVgvoV0B6W5/IXhp4uKDu1/uVhFiC9q8LATy'
    'Y6lUVSq98fUNUl7J3PjiPhaBIFCp6CMaTfiZ5/7+9ppKaDpiSXtxh21s1Ci5hGqBkEl43P3xOAGZkP7mcOf/pIK+yo/HB29Smctl'
    'h7+PJZXIJWeHqQTRd3FPPBzJjt8NwTJguaEQZu6oMLI72CG5FEBeIcc7R2IzFzVURKO9b+9X9x8+Xf2FunNkLa7O35wnkIRwiWtB'
    'OBz++IdYKEVfeHCQy8xQ8WQnlik2lO2e7L9JpREpuzuHv937YyxKLPmnHw+OU0Hiwx9/3I8FPLHh2cnebioxqSS3ESwV5DZC/fOf'
    'UHQVQhulx93H6+v7DxdX79E07vVfYSmV+nSs+kqVN1J1CypubnwsGB1ZNxygcsiWWb5JIr60/goJPbPPSsOuME96q7wwvgvLfOwY'
    'TFyCiTMw9gJeeRBHt3WWWz8PRtLIhHoFInnlr2nG/lzqF5xJMMX7R9n8KWyC0hYobIDSRhmpzIlaLcybl6Pp1EoorYOJqifQCUoC'
    'MNkrhZ1S2idju2RM6IKWpd6Ot4PsHvFMaQ7MzYBX7UV9ef3+U0CZcXldxxH2qnlQyRNVTBgYNMmSeTA3CxbMgX/+8/8BNn3Uyw=='
)

# ============================================================================
#  Patcher logic
# ============================================================================
import os, sys, json, zlib, base64, shutil, hashlib, struct, re

def log(*a): print(*a); sys.stdout.flush()

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
