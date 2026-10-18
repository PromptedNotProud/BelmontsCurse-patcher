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
PATCHER_VERSION = 'v0.30.0'   # semantic versioning MAJOR.MINOR.PATCH: features -> MINOR, fixes only -> PATCH; v20..v27 = 0.20.0..0.27.0
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
    'camera_toggle':      True,   # a key in game switches between the closer camera and the stock framing (to see more of
                                  #   the room when needed; the zoom eases over as usual). A system sound confirms each switch.
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
    'low_latency':        False,  # EXPERIMENTAL: Unity's queued frames 2 -> 1 (QualitySettings.maxQueuedFrames, any GPU):
                                  #   measured 1.6 ms less on average (up to ~3 ms once frames queue up); may cost a little frame rate when the GPU is maxed out
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
    'ff5hKbrqRto+bvFnOtPx/0PCcsv88gbUwIoNpe6LX1UZoXaSLiqXt+AYL5qMux3A3avV4d7ZzgbAf7UBvEchoMTyiPivcLK/fnNy'
    '/Bak+P7ZphJ8SMYTs2UCHCpY/wi4t5pOSnuWTYob89mYDJj4ZthkqdkYI3OK4iS6ytZyHlc82P373dZ5KZrGTFH58o8vXx7s/X+M'
    'SN2rR6LQsxqFLx+JwvuXp/snI6JVrR7TafnjQHNZqR6//A+EbS2C8slwPUbydmOUt/WxBMDxnA09W4B/lH1iF3zNY4qvfPcdaJsj'
    'UDz/tv5sI/cwStTE+LC9uGoJNeGqI4xprsGlpiRgwk90vHwkKJuz8NTpRvvROollIw5baN09pbVxd7eOrOxyHXsYt3sOvdDECiCV'
    'uWWx6svppTdzzUu7CNWGt7dqSIKmHYGYtVp2tIb0VLi+ZzoErVMgvPQNpV3gWtfvhvf4AksovEjtm8X2zax9kHjUirbIZTIESt9m'
    'tNvEtyK3BBHSO2m9CLShnWwAPBMGN2EzQFvqEVcmFMMvTeZeWGyBK4PrAB34wQ58K9jYHEDsezyegmkjhtHkDWgjJnE+KZOe4xg4'
    'J9wOOI1tPmmxUCFTU814AcvIX6GVg8IPop1uw6oTMFCkw4xU9BeIJT2dddNndwz4AMbP6V/wSYG6dDJN68rSRZA5LX60tH1oaRzo'
    'yvm+WgHQ42cScpquskMJYC42wo5QRNfEnq486w3Net01ejiykGJXUAYQUj/R81j3yJRwdY/w3rrHpMA0WDnjIYiMvCIoZa70CbqD'
    'j30KMe1Tt0t9Olv3yfM4o87ng/nQ1H3KOO1T8qU+dTfpM4+zfAMn+obVfep+2iezS31KWfcp8jiBbLlPa+o+bTPts+v6uN4n85M+'
    '8zjB5cp9qlD32eppn61c6rPr9XiiKCt01770KUTdZz/rE/hwoc9WT/rM45Sm9NmP3gDSXQk/oXu/1CdIuqpPlcfJ5UD3WPep2bRP'
    'qZf6NHzSZx5nX85y8o2q+7R22idrJ32qDKWt+9R5nKHLfba2S7017bS3qPpuvTc8/6zqLY+wGXqj40Nwhrtpb2231Fv0evycCgi+'
    'jNmhN5TQEqR7kWsgnWXq3zWim9B92n+SGbrSK8hZQaR53jI5SKx8xgJM2JakHRsgUaPsiy1YmsMhTnBnxjOBIrBxmw86pTv0LfVw'
    'h99AMgM8TZuPsqM7fJ8rdzzgyu1wp+GuKXfwf8fa4c62+QBpuiOdwlstCo60Q6xxM5Ro1esFHW6Gg1ZE+kVp9fhLk89Lv4rJjTJW'
    'iIRNSl7A80qiA80h8slIbOiJDT2xoSeWeyKMG1ZreDx2jXhG6DSzQSYK6GK0QtGqBM2fqCGSTdhnSTpaAils21g9yAfWSZn4cF7L'
    'h7qWae+oxetanRBqrRaUA4x6qdzLhXKgjNYZEqAVuVZYJscy0eUyXpUlvu+QjqUn2zI6zQ7I5fLZsKjJY7oT1I5ZxB2LuSc+ywHF'
    'jYgOrT8gnqc7sgWhj4D6X4DoS3wuOR7s1HpeICGKdV7nA7wNWBPDgZEdA7NW0bmOOC/AymiydaVZi+4bWhjMKC/BgmHIQz3aTuPb'
    'kAPA39FAPrJCqE22QCZ2a7Y/xmODmCFONjxxdNqrlC0lOopWQ7dTC6oDscvoiVh/IugJ/Eo2kAXWDYWaeCcCm27sd0mS3GMrKfht'
    'exssG6jLJ6PMGq/V2b6Fv47qi9FqnI4+tchsSC14aqGWWxTtL/zYQqxJQ6CCLSdaJj6jTdGc/m0wJ9WawPFvB/Ukyd8sb0xuO47Y'
    'klzgPMmHhrP72ovSXs3bZ/nSiHvbM1PbrYmHJpF/oAYmfCevGv3QwS0dOSltR5F8YkXPtoZSj4o8gBCA432nceYaJYYD/5yK1T69'
    'qLCkyzoA2klLHkKqGdrRS5BKJcXPccs8lohW9UOvhT3IC8y6D/WAL62wTiOH2eojzutscY1b8fMcFXisA4yf950b/XP0efBAcdxn'
    'rECMo7+pqcxgmbWzFgo39ScvyhAvdzK9GaXHiOP0bo0Slp4byRz0CqYeI8PAtPQWiW+hv5bmmuQDkVKvxMsS/Z6eJQwQb8iszaSm'
    'v3gK+XB6H8Pv06WnJj/1k6cqP7X5acNGPZv4QKHu6uC/UOYJnb/pWB9M8EBsPKCZ12UtT2UBjzTSyhaGwDvZl7uKs5J2ppCc5Pk5'
    '0RMwMvo8HW802UBtLF8XBGq29Au5judzWoHPp3qNvtCMshY5brT6pe0LH7Ztbpv6E+TBjT6H73199g/4MJn/bPJesV9XOBn0UtJg'
    'hp6TTy5SOcffvEmY1xnzeYZn+mR6sUIRpBBYR22xN+S01WC3DO0UWh2l5byVXmtl1lpZVo2PYT4bpgIjhcGIQN7LnlE+MqLTbZ76'
    'oG4Ct9bECh5oTzn8pGXhwaQlaqssg1TgpVTaSX94Kt6ID+hP5f5IcnngOBE4HaQHiorSY/NsFg3arZ+GgT7C7OOZZriR3TZNPWs2'
    'p13hETyDF+c28kDikb6HMklvYnn2s2H2Y01B3oofetDo79TjAlyDXWFc6bf0QrUk1ZIYywE8YQ2Za6hKypgkZcr7Kl4nOdOGvv3s'
    'csYNURHZhyytOZ1GnHU1eJYkCwZZjha1qyXSsiwBKywUSY06r9Wj3uhxQ9QgZ7yt/MwuGp2+VcDbMJM03KKRg5gVSf4XzN0tdUDy'
    'y1HaWKXCukQBe6fNsOXNvvjLDxhOUSwMYwKWfKpbNFpNMz2pKcXQa1UjAoh9g+XoZ2WOEDUdAEntOh3IRg2ILWtSvOUBSiR7gcfQ'
    '1LFAptqaJrFNNCfZLyc0yZEFsGZ8Ff2kjQlgyalUN+0vwVPaCr9N66N1ErSQwztd+b4B+P9y6IHh0e6+fkdEbaZtOq5H96Ghv+Dl'
    'cFm143W7xD3Ban8X9yBcPNvBiVKo+8GqkFHDfMTQqxujPTmXONFVO4xRuKZJtMtLo0Os5H6tl835mdYrhFnnRyCzL/yIbx85nr7N'
    'WXPmyLF5hNqPIwSZ1RUOG2Sa92bEM2e+wiDaD11bZEaWrmj4oQZyJPfbYm+UI1Mr+QJ17R11J+f4oa2tR1tdqAKFzfimKH6Hsmx9'
    'jOA/2uz5D2eO13gfMWkGnJhuwGd+PmIQWvv0NGOI13ORZ2zeNRdDP0hFHsYTMmYWW+VDkgcgAnGCz5aKpoPaSWuSPCmH1SUJQx6o'
    'dfkk+T4tngP7iPyxBB5mHn9akRhj/CLHqqLr+3FW9o0YPC3mSSbrSjaQHw+j8BM/3k19YuynM/N+Oj72w826/ABdiYLSF5u0N5k1'
    'uGul7tt0B96k7rkaPSWy5HsD+AJbRovhqwD4FrAJuzbFCMBL8NnXaVnoGpDDXZ8v8M18DwZObKbe84grIGjGlfFzjM61HGKH/DDy'
    's4Apfe1fwT1PEklmZsXYextVJTGyPxgq+gXpI8VfMheiBtMpftgliQ/eC+pkq7tYNBwLi36PJ2lRVrjmOmL0TlHnsuQULo1P6rs0'
    'K29rzUrOVJ5fgKResCUOBbi6qbQMdjjvnE0hbLt5jGAWkaHxUdx6mE2E9RbUl0vrQzafbVv8Akn2W5ptdKx0ix98L7NNiHq28ZZW'
    'TCsvkoshrgGzUOqEtbtm4cBdoGXQ5S3PcPcR6QUx1u9d8nvC4J+NFMK5ADyQ45FLUi/wHFUH0bT2NKfxOF/Xn9ewypJllOJ0Xaai'
    'Dbx8Mg9Xb9hy72BjxYVeF9+ifIp1ul7Nol/AM7p+m+nvelv62ucmb0v0gr6YGrQHrnepsi1udoxkopXmqqYLX47wJFkGPNCk+V1/'
    'NAnLZV1efUQJ+myTLRJHu5fy5UFCm/FrXD3a5KbEQ9esMI8h9oShbBthsLYfoko+W06DZxdN+m6ig8nnhzhiscmohi81ZBeDVus1'
    'QK3F0XYAoaIyV6KtBvpeRHAgNaMYRceTtZhtNx/yufapnHPg1jx/cm9dw8d7HcCW8/XbBIiw8V4HodvquY5dwFFEleDuQsIK72xT'
    '1erh3tRvFdrUz0NMFqePMo9W5d3vItGEIi0CD7yseUeyyVp52f2AlkU+2lHa9JY4rLqstyxzXuaYYT6iBq0dN652N2XVxuH5huMq'
    'vxpW+YVBLmYxwSlb0uQ6+eWcJJ4MVMpzac86i8d+t2jJ4RNe6kdJUSRuc+8ce455fuDMAn2dbGzqlUrMWKJSHZ5KEi4SPMUSiDY9'
    'yxF+VnRlwIN6wSqy4CEDLhpaNxBoN0jPA0dx2mIGQWxji7K4lfmtMgpc5AYPo8k9Dy0dtZyOQmVblgvmCkVIancpssg9jaxzMo1s'
    'PNJWdTASSbFuj1oLYwrBWd3LgeZd0h4oK+g9YCkztM10ss4ttvSos0POH8AZhHRJ7SxMfwvqt8RaKCJjigbMR/eT9Z9h8jpbWFTq'
    'iidVlYX82+shO4es7nws+lDmhjL6VlaVz0PvQxsVpnnKuQGXi9mcf4OteFl3Uy6tpaTvp418XmZe9EoW6RE7hC+Cd8vyjOvC2AJ5'
    'sDO5Niv4DVX7ET+mwV8MuuQk5aw0ZBO4vsrCzcdFTiyHWOLrUzuq6BLZJNsg2xGyeC05wi/mVkDFZ4PdC3iVs2eqPDMxPUNYDcuQ'
    '8SEKTL3PP1FWSR1dfFJX+fvEzlkqoGWcuM3F5LUkbotN2icO3GYAV2rGbWGQ/Ya3o5wMZe6AcFAh/dboXrsizZkYYdVgiWeq+qGu'
    't8P8q36jWmNVf6H0B/aueKC/UPUXclZa/o5ZLWXnq3poEwDoceJrYPYWG3bQo2U2ZkNkSdxW+U/JvqTSwbNsRZ09RTqj8lpUk2Vm'
    'qylSKfFry7HynFpMfkglIKExCheK8JEg8YTJz6JtyFuLuTVHmctlunO4qMxlrOdNz2U38cZ0eh5brVPkbhyHKvSH+Ve1QmshpvsU'
    'pyF+aayRqhylXGJFvUjyY2w33sPzLlbPh3Z9EMWq8U3VnmNGu+wWrewhsbhxeWScsu6gBJikK5FpSdgqvZT1fSETrReszWxD6gwv'
    'tra2vAHXa3XGJ1JMy/Qb19WxlWrTPY5Cd8MoFCcPG6qXforO6Ke0ke34Vjm0X/bHh3XfToJvk8dUa1I70aSONKnB2HjRpBS9BN5j'
    'LrYyrSD7qTRsfWU1p1y+pljfxSbCu2QnyJB1Mks6uXOphMaAQTiHOpkZh5/Cww9wUIbAdGV7bVUb7YTMExihqfwznb6sXPyJriu1'
    'mFk/MB56xg/gcJ6iTR6MAE15B1qCNLdS9HTfovhuMYWkyT4FyFToPfCGshol4DV9kMqyAH4nwI65xhQjAi8+pmgR7rurshvx/SjP'
    '8S9KGtVyP0oaL+b2IK3H8rIem3KZaznP5bB6C1YFZkEDP/sUv4f536WnCA2oR09fHsfPjqUsTbTYkqwAb7dn+Tf5zqpNeFUW+2F5'
    'BINGTB4jzxG5ST6KTvYVtIox99imWjhLQn4LrsfB+HWrx3VHGFHXlDYSRT/wCmcG++pyu9pSq2cAzhKgZaxndojcjVlZIOpSLDAY'
    'CVYjy88wVyPlRRC8IrcdnqfcNl239WapLXnaldwnyQTzEXzLOPd3veU5p8iOa9o21VdL9Vmpr4esYtWn+nKhPkyyXF+xSQYQyYeF'
    '+l2pP2Yt5z0FGs9PGWEXM7yhpAP7bJBUME+7aeRwLRJKmXd1n6An7Ayffti2mSM0yZ7Eb0DiN+QE9j/9/uTMCxNuao+JhnXGpPdk'
    'r7SObfIqU17NJIavpd08P3oeVQOPBON+Sdt3wKikk4VPJbQun59mye7LHX2jIPBxHVWRbs/RI1w7JL8t30XXjSvqHu2FHMcbcwl9'
    '22Wrw3cYJxU9uhQo49MsB+mGibMgTnSfXX58R+xVlcWP6y5D/CrvXXNhWLX3OfurIU7O2c0lLxc1QZvjLwLGYL3s67H4mMfSIpLT'
    'b6jHynNXnncs4NYlBnp18D+7NhMKbThb4jpjZFF7PS2DN6N+MhGXSPkIn5eqysRz2dgr+eSVpUcZ8CC7G7KmWcpgky77dOgXeIrH'
    'YTlGIVNm0bgC1uGqBLTGVSeBUT2QcQ0TlmhHdcMddUOu61BqTkaSNHrKrWvwr+CUp0/UdbQsUzQF8wM+MJbQ1DQWGZcgX2ReOcs+'
    'RVkzIq0uOMUCBMpxGFDuaxAy0vcMvDiBGa8CcNkKWXKEgA/Sb3xbyP0gFUEA9ENbbQRyYMtLO8rHtJO7XJ8sYXQFUiaWTOsW4Bb2'
    'xRLuMHNWm5DfBbPL9aUtRbZ64Kfcd2w57doAxTipEWjXh85wkFXnxt82w4S8TbHG/PZxDs6j2MWTY53N/RSP1Da1R2ol2if5K21c'
    'uZLtBJ4oWi6CO+IIxx3g2yjeOu7YGHX32Z4B60Y3gpFdw8FaUcZgO1zOQttPgdXUtMTPGHuXZK+gNWiJhwW0DAxnDWAmlulG63bZ'
    'i+WgvIezxigrTQxPUP6W/CPkUZR68Dz1jPt2sOcg22b85in67vgVBHqL5XY8zqpEHcFW06VuB3WAV5oSF0cdA5B1bZu9I1xfVBgh'
    'stlfwplKkR2d891LObZztJriyEx1hInGgmZa350y+BvwruK3ref30VNx31Np73qaucSTlxBH2aTN5M5O7tzkztd3oowDI3IqeyX4'
    'W1S/2fi7i9VvtVAH9/zJwRfDjGWuSE60janzmpOG5TSTEJt6bU1tKW8Vc3DB5lBuyHZY80XSOsIwAt/zheeyer7Qvnhy5Il0DRvv'
    'pG54ddc1YvTEDCt+G0pEtL9Lf6Z4dCB1ZPGz+5Ao0I1YLJ7fWhasQ48PJFD2Irmb7p3rS9Yuahk27hIa99FRvLZ4t+P+PZiJ7bg3'
    'KNfNcoL6on6b0abJvsHgw9FKiCLR5zCDs+SjJqu7C6keE8srU4Jztexf0yri4uoN5ZYDrlg3Yr7JHuRoWaZx+m4yzsUVm7STgJVP'
    'pQGzDrD0S5m2SxypupR7C2MByYLQGlftf0r2MsofWTxdaEu2Qr8Ae8o0IKcy9UcRYVwazBmnZZ9llU+Ame5ou1haRYd3jfDV1jXo'
    'Fi6r3Tsi39HamlZ5dHjXMZHuAJYZNxWfxtO/rclvaVXaIZfWhzvac4lJHl22gUjiohur0C9J+gn0jKPfUKvDJE+ymKA970gb4Yor'
    'MDR9lprxEUOa4hT4qyUNhfvTKF8fPOq4nGs9rPx2CRNM1pjgtsZEZ1NaR8KEjTJHgaKZ5S7beg8k2Ll+wFQap6337zCRpfdSJneZ'
    'NRbXZYakksEO4xgnaqeRxm5c9W1GbqOo5Jhb1EqUS+24EzL7scN6NeiDDB1v6tGTJcirOWuyN+GH3vA7LNX3KlyxGxVRK+2/dZxy'
    'zsmO6YjyvKI8z5T3KedAdrLJveNHYlWxn7UnDkhnyKQ4KS7xtzq/Ree3EH0bfAs0H96Cv/EtmBVb9LygD+9QDsWYUdMqJkYeIw4E'
    'owdjZF41ALuKlrhMZaso2wLAc6kEo0ZY4mLbYAKTF1qZlFa5lHOR1p1BNzQT/yTF9JrqztV3Ispm4s2O68KzDyCiLuZtqk0ar+WD'
    'x69a2pNTesaAi8BNpEDDrg85URR/2/QbcyigjgLuiU2SpS2tCOuSVGpx1bIlSYfvGqBC9oZeNahDqgmmow75DbhGRJGB0gtf+ijS'
    'dMWnieWNdNeUu2ktH+paYPvXd0x6Vq38N2pMjK04O3PCdI1gco7dEFfV/UBl4GFd8rBARvXRSpmyPcwQO27xSeeGA6jgXbjbuUgo'
    'yk8g3oTZYkjKeRqpqfJlPEVlMSY7nGeAuUTVinCsvDhZzWlRQcnqCJUfpYYf1pcHXe3z3geMrkZeZRNaPOFl2Mlpynpg0jgc7KXS'
    'ru8im7UbdjPqZq1dLO0iX2s37nSMeRen4dOxD+cA0PkRDdn8bnwH2D2m6jXZ/W35LDTGZoH/GsyNA9vUlo/TI51ADPeVD9fRuhwv'
    '9A6GpAXOgcjK6RFE1WS3gFCDeWljPg2L8mqQxqTfS/wyywdaqxtSunEH26jTqpgWrUTnzes9zMCGYr/hce1yPpKUrrJENEt5OR04'
    'iK7wHUHp0p79oackm7vCSa0c/D7gMYDB44I47QYaYgYUY+cSZS5oBhuhdbEEcixpyO7kSWtAmXRDzN7Q2Uh5xYBjjh3jFHHCz+N5'
    'pCWjjElcFWt7abPfF7Lf16SSNb+vlGO7kr828/sQv8ZLO8g3PDGBshx1P5aC7OwJRuQdjgHJ0fJMT6If7AXCk1Dp9IbUKtD3exmr'
    'JZUa+h+9Qdoj18fs4YJfaTPV29QGjIxJm0VeoLZCzdsC3TdoW7L/Eu152fODeaBi2KmIVklepyreh06+C6dsVLKXUfu0UZpq7cZQ'
    'mcxlijhj3FO24N9V8oxN5Zlmk1z+hdV5et6r8pRXO6xdM8n5k8NHwMYTRzS7o79Q9aeGPB1d98dy9qmenHkynpVCMKBrMGZU2LQ3'
    '/6ExsJxbjp+1UuGOt+Qy8jPR/jRFO2ebz2b8Y47wsAscGDSSDWDleJaInnmmvNjGhs/yIN1cvw75Y3kbb1kbhkmhq/uyhizSHiVa'
    'YxYgdWWOKKQZi2uZPOXeRLng9aW1hrweTlGycS54ivi0aeZLVvopEZ9hZSn5cSa60PVm1CWiL3wdZv4AHuYx5JHimTAMf5ev4jFH'
    'v7gyRGeHWgHzT9JTlH/0LAweRBy9HDPLBiR/vy90IYts3ByNs7StdtLBSE0YIaA9D/k55WK3OQzOy2pJ30lVr5ZQFDCwZuy/H2do'
    '3u8Qmzrbm3R0oIzAmHM3+pyxN9njkTM6QFMJzqoVf10sBbJ8uZ7gGfMcEjam+E/8TOeljDGclNsqU14dS/3mSKUtn4rBT8FlWHMG'
    'YCnB/VNsrK+G+m6tvhvqh6G+G+qHtfolK0vm/cpW0jnJw845bB9KiWL1+Itc0GzcQULr2SrJirt3S1TSArwm3P0AHMqrzKSAOegl'
    '17STzI9z2pBPS+tEuF1j4LyuZ4OPIDBO0YUo5ag957Es0AdgAtURB/RkMERO2sPVGmcmPSaf7qOsDza+CXeygPVvZa09kEv0wjph'
    'q7lIHizPWeO0alIOHxhtnbLkDjWbbNHAzLXa9uT1RttSLxhr7+gju4M/bGLJJzSe2nmO+wcl/W7wt+4G7xj9V0H+a8sxhg92Hvhr'
    'fPCL8YxVXO3RZG2COUA2ECe/GFcF2HC2lC0RGYEnMIHljW/igbxmR79xfwZDfeLwjRxtX0xELz2ilYJZDuDBiBiS50tPJR5ukk5N'
    'aPLZDv0k1gj+kJrTNXRSZLqmnMquq9bTYzlhCfM5Fc99rq/oru8w84qN69WW8n2sHPYXsVhkWSktsqzmb9wVvryDhvIOlBT102wB'
    'ivV9bbJP/VB7HkNwlWUySLJhnqY57kqWpBosmCQvbJ+smfw70HZc+q0pczP9rj/nge2n+6Wcb3F/XjWOtv6aL7y5geeNq+7heVtp'
    'lzhkO5Vzrbpq3Z4VujXgV0zyIOpTTx2bZF8m/7Q+FbW25kLtt8o67tSPT/JJVXmFdsi5AJsft61Dy4iRQonRWtw3ZWl/TIvcHKXt'
    'TIoNKsr572xAzxx4qSevguax6ZOfEzur8CwbgKAbkm7SqT8wS7wumMX06Ymd19GuHJ9ziqbWIn3tTSXLq6PZpnFvqJcb9zA8qc+m'
    'w4wjFyneU+eKtTOOaGcc0c44op1xRFtzxMR7b/V46t54Et/4ifKBk03FyabiZFNxsplzMg+qnj/zEwpzjDV5dYpGU0k/YDhpG573'
    'utZ2Ic5em9cLcjbVzEKu30I+YDvWFoRfI8o6xNJphSnuDMOzy2seTOAXH5bOH6zei3lhskSC6AQLzAKzZZ0FTZCld1NMQJXR4W4A'
    '4ocCQTnPqEk9L6zHpPO80T9uBwlQNj9Sblnvs5WO2V12iBHfA8va1fMhv4Q0abpyhMIOUZfqL4dJDaoHjPTyP4EmtdYmGow4g6aE'
    'X9Z4+BdopMEwMNzA8IwxPfzGeHMDdxpXeyyDMontoH5vou4VtmsM6AEoA7MfvJa7eja5FvQqpTB4ltOnjQII0xsJz4P+KsYD9z30'
    'wz9pFNxqaqmhl5jaPxNuvs5RyfTX6C9LK51GMuMXBfWMehKm5iMLnxunCRJ15xz4TcI0jhYsdppP2ErhmIfeEdanQSEtmLLUDtQ/'
    '4NFTfeDFZxzxSJevfqxfzwgX6Ix47E2LC8ifiXefSaaMFFca8BoQCpqDhAsrP9PoZ/Nb4agIg0+QjcgbGilxzwjXephzAhhOSDmA'
    'Hes9fjTw/KvS8gvj+Qo068Konk2z+mK/94YugWdj9U6xjS5spzrCkKO5AKNHO0CgZpIDvxqCqoMalqBCT3aQAmhnAiQ8jX4dA3fX'
    'pZnnod/xPkOXrWeCInTg3WK2Kp+O+76/glUIkGt29uQvt63tuHRL+NEurYWWNVG8Otugd9W3+OENXbJoH77wkEwMehr8CxBi3A6j'
    'K0AxRgcAhvQfeRrEMQoXrJD2UrVw7/GrEQlXQ42EY21spSkSvyAebalXl2mgNbXhuJ0a2xmUKdJKoJPCWGC6g+fQVmFNPS6bFXjb'
    '/u45QDTVE84fOEjJNE6UW/fNJIQMa5HGSbD2WhInERaAiwLxTK6nYuZQeX+/aU5DW3qWpCnxOdSxcmIHI186qo+6gt41zAN4y0yS'
    'Eo+Df0cyHUac6jHidg8z1wP3q/RuJfNTgatIBAFCA7RJTzB2QhSAng24ttYL8JJhrA6lvs1rl5hDPs6YWiMQDT9lTsMzoju605og'
    'wsivesxsT/IfTyRDLiAdO8reCmOP6xMh+/Qe75Yzm/b8KF7HNniQLS9PM0dmXiCaDLidQdCmnvNYvZG4ZIw10u8N8fBo+BRqFo3b'
    'jQDzEi25CmOJX0CEJO5aw3mHkADEchFzxqS+OPIk4uausRLPGoI9vQd/J42Z5+qkX4KsjEmRLCB5pUgSsrVRTPpS9CbgEwEjWx/T'
    '/VR4GJsPUHHjGSKzdUZy+x4qo5zJmmFWR9EcJ0n+AMXvrlnLmCfO7ftm4qZ9J9vAse21vbbX9tpe22t7ba/ttb221/baXttre22v'
    '7bW9ttf22l7ba3ttr+21vbbX9tpe22t7ba/ttb221/baXttre22v7bW9ttf22l7ba3ttr+21vbbX9tpe22t7ba/t9XmuF99+8yJc'
    'dfEiXr747hsumXNQ0jW3TS5xePwAFPXnf//44QZKfvxRWLg/ebt3un+4ert39uKv337zo8ZmJ8enZ3Wh57ni3tHZUMi5h9I3uztj'
    'idFQcrY63Tt7e5yLvE1FJ2/pXjgF9zs7fxwaSYGjOj0cS7gQBorgdccHf9rLRUqvFRm1VuTkWpFfayiZnRdZKwiW71ev3+7lMq9Z'
    'Ljva+yENnqtS9CaPVVjO50WOYDzbP9wbyzxDvL5+dTYUSSbnLaUglP5hdbD39iSVSIXtEO07r17tvz46Pkqjk0q4+UukHqAYigyf'
    'A4FnGKzVcmuEk8arOUqk9X55NE5j5VfHhzv7R2O3zmD1ndPD1fHJ3lEucyaX7R/uvMnNPcfC3YOd01N42/Hh6mjnsDwSfngEHa/O'
    '/nxSnkhiLbinB8cv/2NvN7/YW35nf0Scxf68uKM/xRnyVUU8PH8ZSv5yfDxOEiWlXytL7LH7+i9VkczAHp6sXh/lMo/U3IUSeMPZ'
    '252j09fHbw/TM0ezgd4N8zKXOez27M3YrWYSR7QrqiLJ5vNIK5pHABt2N2AFD2ahmq8PhtZ4EuSMZQ3z2OHp672xlrNmzibGeb5W'
    '5tlaPfyWwIw5LTN2rYgm9aQoCYiT3Z2TYSBWaL/OgnhayJwFrXB2jQXxeI47WMYxjfVPT8eXOUZQY9Hp7/fTVHU8CbLTP4zVFAF4'
    'eFSVWE8lb8ciS7h/tV/3b20pe3s8ljol7+IS56yccwmQYSgr09p5YoB9rHS2Ojg+zoP3NK5ZVaL2vCp+aZeKa+x7IefM4jVXU2Hm'
    'DQne/Z0daDpqDW/SkKj45VjsSBVBMSqeqpiESv0mzkSSH6+w6PWbk+O3gJz94aHy1cOXf3z58mCvPNLjo5fTR5IQ8grePeolpgSS'
    '5YfXu2XiQhEBfvDy91jt6I8HB6XcuLmSYcpj3ZMfDsbmWq2pOqaTIHqT3gJlLy6aNl6gzv7ni5+urv62+nAdb87fwz32l0qubm5T'
    'EWmVoVa8vIUyI0rZu9DAPenEm9uP7erjh+vzdz9hHS5kKTwPzcUFdiXUUHQLva1uPlyTKWFKcdNADx2UCS5K2c37XEQWCPDq2fER'
    'tmKGJsjJCkg6lAwv+MfVFY5eMTV0fh17HIUBMqHdct28j6uOwGFqAKCDcSFESVtT0c99oN4VyV4q6q8ub1NFpJiiYZz++XC1e0gK'
    'YP/o9TE908Ty6RkMc/UGeONw72wnjZal8aOE/z1hjCk3lrxMRUT33dVf3u6c7aUS0srQ5/7hUSrQqWD/6E+lwAw1XudeSBqtUMGm'
    'e0JU+GkF5lvsVkDW618IEyQo8MHNLzerBKJNxsZQCKwBpY45lks/hOYD1uOmND6/TUV4vHwueo9WI0gcM9xfX1HJMJTu/Ca14boq'
    'SbUsUQhA2v3+OANpE5CvDnf+TypwrFT5/vjgVS5TpezwT7nElZLTw1RC0+P8lvg7MYQXgsqAHatCZyaFaSp4x0spgLxKs4HEdClq'
    'scgQ79x2t6vbnz5e/o04jKeRnL3KDA087zJDgzA6/P6HVCjFUHhwUMrMWPFkJ5UpNpbtnuy/yqUJAbs7h7/f+3MqKmz3/cFxLshc'
    '9/33+6mAp1f+5fRkbzeXmFxS2uS595fT0maceqH/B848TWoxlVw07z9QYaYtFt6+SyVqmGhBUIlzQ52Li/9Mc8wnMA4O/pCHrH79'
    'FUouY+ySHLt5f3V1+9P55Tv0RAbtXhmmtbUwVey1Qp8o8gUFvm7rLdh4RfMdoOorhnC5yQqsNrYr/bNmDtd2dCXZByeo8nUqR2jq'
    'h808sJnvNXW6XgQQi9dNkZ8/jvbnaLFONUzdYhW7d5GcwcFGrW3TysasbMslG2Rme7wAXbQKVySOfqyVNYoJkF/Do2JLVgZWbVhV'
    'BlVt8E3sj5mNUtmKz8dC94E7s5sIdIKSAMzGX2X01cbe1Mib8lXFOrURlG5HzTRh0dq2WrepXqAaRGF4cdWk0WVbZMYgF1c/ry6a'
    '23gZfqFa2RSZ1erOm4urdx/jpMPBYBrtpJl5ROgcte6S3bZuri1Yab/++v8AEG1gfg=='
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
    if 'P_LLQ' in bl['labels']: struct.pack_into('<I',out,co+bl['labels']['P_LLQ'],1 if enabled.get('low_latency') else 0)
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
    # The resolution menu is two halves: the sizes live in GameAssembly.dll, their names in the asset bundles (one table
    # per language). They must change together, or the menu shows the wrong names for what it applies (v0.29.2: a player
    # whose package install failed saw "1920x1080" as the highest entry of a 1440p monitor). So the bundles go first, and
    # the DLL's resolution patch is applied only while the names are in place.
    rep = {}
    if bundles:
        log("Updating asset bundles (menu text)...")
        try: patch_bundles(game, here_dir(), cfg, log, rep)
        except Exception as e:
            log("Asset bundle step failed: %r. Continuing with the rest of the mod." % (e,)); rep['menu_text'] = rep['taa_menu'] = 'FAILED'
    want_res = bool(cfg.get('resolutions', True)); lst = labels_state(game, here_dir())
    dcfg = dict(cfg)
    if want_res and lst != 'on': dcfg['resolutions'] = False
    log("Patching GameAssembly.dll...")
    out, drep = patch_dll(stock, dcfg, spec)
    rep.update(drep)
    if want_res and lst != 'on':
        why = 'the menu text could not be updated' if bundles else 'the asset bundle step was skipped'
        if lst == 'mixed': why = 'only part of the menu text is updated'
        rep['resolutions'] = 'off (%s, see above; fix that and click Apply again)' % why
        if cfg.get('ultrawide'): rep['ultrawide'] = 'off (needs Improved Resolutions)'
    rep.update(patch_assets(data_dir, stock_dir, cfg))
    _atomic_write(dll, out)
    log("GameAssembly.dll written (sha256 %s)" % hashlib.sha256(out).hexdigest()[:16])
    w = max(len(k) for k in rep)
    log("")
    for k in sorted(rep): log("  %-*s  %s" % (w, k, rep[k]))
    if want_res and lst != 'on':
        log("\nImproved Resolutions stays off until the menu text is updated: the new sizes and their names in the menu"
            "\nmust change together. The rest of the mod is installed.")
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

def labels_state(game, here):
    """are the game's menu files carrying this version's resolution names right now? 'on' (every language table
    rewritten by this version and unchanged since), 'off' (none), 'mixed' (some): read from bundle_state.json and the
    files themselves, so a failed or skipped bundle step, a game update or an older version's edit all count as not on"""
    P = _bundle_paths(game, here)
    try: st = json.load(open(P['stp']))
    except Exception: return 'off'
    on = total = 0
    for f in st.get('labels', []):
        md = (st.get('mod') or {}).get(f)
        if isinstance(md, dict) and not md.get('lbl'): continue    # a table without resolution names (nothing to relabel)
        total += 1
        tag = str(st.get('applied', {}).get(f, '')); gp = os.path.join(P['bdir'], f)
        if tag.split(':')[0] == str(BUNDLE_VER) and 'lbl' in tag.split(':')[-1].split(',') \
                and os.path.exists(gp) and st.get('out', {}).get(f) == _sha(gp): on += 1
    return 'off' if not on else ('on' if on == total else 'mixed')

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
        ('camera_toggle', "F8 Switches to the Stock Camera in Game", "Pull back to the game's wider view when you need to see more of the room; a sound confirms each switch"),
    ]),
    ("Motion", [
        ('smooth_motion', "Smooth Motion", "Moving objects, prop animations, cutscene camera and walking drawn at your frame rate"),
        ('low_latency', "Low Latency (Experimental)", "Fewer frames wait for the graphics card, trimming a few milliseconds of input lag. Can cost a little frame rate when the GPU is at its limit"),
    ]),
    ("Gameplay", [
        ('skip_splash', "Skip Startup Logos", "Boot straight to the title screen (first-launch setup screens still appear)"),
        ('dialogue_preload', "Dialogue Preload", "No hitch on the first line of a conversation"),
        ('font_preload', "Font Preload", "Removes hitching in the game from font loading"),
    ]),
]
GUI_COLUMNS = [["Image Quality", "Graphics", "Gameplay"], ["Camera", "Motion"]]
GUI_SUB = {'ultrawide': 'resolutions'}   # sub-option: indented, greyed out while its parent is unticked
# extra note lines under an option's description
GUI_NOTES = {'resolutions': "Above 4K (DSR/VSR): set your Windows desktop to that resolution and use borderless fullscreen. "
                            "Exclusive Fullscreen works too, but resets after alt-tab. To restore it, pick another resolution "
                            "in the game menu, then yours again."}
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
                if key in GUI_NOTES: tip(lf, GUI_NOTES[key], indent)
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
    # v0.29.2: the window's log is also appended to install_log.txt next to this script, for bug reports (written here, on
    # the window's thread; a folder that can't be written to just leaves the window as the only copy)
    logf = [None]
    def flog(m):
        if logf[0] is False: return
        try:
            if logf[0] is None:
                import time
                logf[0] = open(os.path.join(here_dir(), 'install_log.txt'), 'a', encoding='utf-8', errors='replace')
                logf[0].write('\n=== %s  Belmont Patcher %s ===\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), PATCHER_VERSION))
            logf[0].write(m + '\n'); logf[0].flush()
        except Exception: logf[0] = False
    def pump():
        try:
            while True:
                m = q.get_nowait()
                if m is None:
                    busy[0] = False
                    for b in btns: b.state(['!disabled'])
                    continue
                logw.configure(state='normal'); logw.insert('end', m + '\n'); logw.see('end'); logw.configure(state='disabled')
                flog(m)
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
        if logf[0]:
            try: logf[0].close()
            except Exception: pass
    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == '__main__':
    main()
