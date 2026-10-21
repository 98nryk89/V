import sys, math, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from multiprocessing import Pool
from render import *
import os
logo.load(); ill.load()
TEXT=not os.environ.get('NOTEXT')
D_OPEN=5.4; D2=20.4
SOFT=np.array([252,243,224],np.float32)
GOLD=(255,214,120)
BG=arr(ill.resize((W,int(W*1.5)),Image.LANCZOS).crop((0,300,W,300+H)).filter(ImageFilter.GaussianBlur(10)))
COVB=BG
WARM=np.array([1,.9,.7],np.float32)*255

def crop_to(img,cx,cy,wc,ow,oh,zoom=1.0):
    wc=wc/zoom; hc=wc*oh/ow
    cx=clamp(cx,wc/2,img.width-wc/2); cy=clamp(cy,hc/2,img.height-hc/2)
    return img.resize((ow,oh),Image.LANCZOS,box=(cx-wc/2,cy-hc/2,cx+wc/2,cy+hc/2))

# ---------- opening card
def render_open(t):
    base=illus_crop(clamp(t/D_OPEN),620,520,1.25,1.05,x0=480,x1=540)
    a=arr(base.filter(ImageFilter.GaussianBlur(6)))*0.22*ease(t/1.0)*vig
    a=dust(a,t,0.9*ease(t/1.2))
    f=fJ(54); fo=1-ease((t-4.7)/0.5)
    if TEXT: a=glow_text(a,'誰かにとっての「無価値」を',f,W/2,H/2-44,eo((t-0.7)/0.9)*fo,sp=9)
    if TEXT: a=glow_text(a,'誰かにとっての「価値」に変える。',f,W/2,H/2+34,eo((t-2.3)/0.9)*fo,sp=9)
    a*=1-ease((t-4.9)/0.5)
    return np.clip(a,0,255).astype(np.uint8)

# ---------- panels
def P(t0,x,y,w,h,k,crop,dirv): return dict(t0=t0,x=x,y=y,w=w,h=h,k=k,crop=crop,dir=dirv)
PANELS=[]
SC=[(500,330,420),(790,340,420),(480,760,440),(520,1240,480)]
for i in range(4):
    PANELS.append(P(4.0+0.5*i,-100+i*345,0,375,720,130,SC[i],(0,-1 if i%2==0 else 1)))
PANELS+=[P(6.0,30,40,720,330,70,(520,200,560),(-1,0)),
         P(6.5,540,240,650,300,70,(260,250,480),(1,0)),
         P(7.0,20,410,620,290,70,(330,1130,540),(-1,1)),
         P(7.5,640,430,590,270,70,(870,640,430),(1,1)),
         P(7.75,390,150,470,380,60,(510,175,300),(0,-1))]
HITS=[p['t0'] for p in PANELS]
CUTS=[8.0,8.25,8.5,8.75,9.0,9.2,9.35]; MEND=9.5
SHOTS=[(510,175,600,1.0,1.18),(770,215,520,1.0,1.2),(270,230,520,1.1,1.0),(480,650,560,1.0,1.18),
       (850,640,480,1.2,1.0),(280,1110,560,1.0,1.2),(500,185,420,1.0,1.5)]
def draw_panel(canvas,p,t):
    d=t-p['t0']
    if d<0: return
    e=eo(d/0.22); dist=800
    X=int(p['x']+p['dir'][0]*dist*(1-e)); Y=int(p['y']+p['dir'][1]*dist*(1-e))
    k=p['k']; bw=int(p['w']+k); bh=int(p['h'])
    zoom=1.0+0.14*clamp(d/1.6)
    im=crop_to(ill,*p['crop'][:2],p['crop'][2],bw,bh,zoom)
    if d<0.08: im=Image.blend(im,Image.new('RGB',im.size,(255,240,200)),0.6*(1-d/0.08))
    m=Image.new('L',(bw,bh),0); poly=[(k,0),(bw,0),(bw-k,bh),(0,bh)]
    ImageDraw.Draw(m).polygon(poly,fill=255)
    sh=m.filter(ImageFilter.GaussianBlur(10)).point(lambda v:int(v*0.6))
    canvas.paste((0,0,0),(X+12,Y+14),sh)
    canvas.paste(im,(X,Y),m)
    dr=ImageDraw.Draw(canvas); pts=[(X+x_,Y+y_) for x_,y_ in poly]+[(X+poly[0][0],Y+poly[0][1])]
    dr.line(pts,fill=(60,35,10),width=11,joint='curve'); dr.line(pts,fill=GOLD,width=6,joint='curve')

def cutin_section(t):
    a=BG*0.75
    a=a+lightrays(t,W/2,H/2,0.5)*np.array([255,205,120],np.float32)*0.35
    a=dust(a,t,0.9)
    canvas=Image.fromarray(np.clip(a,0,255).astype(np.uint8))
    for p in PANELS: draw_panel(canvas,p,t)
    a=arr(canvas)
    return a
def fullcut(t):
    i=max(j for j,c in enumerate(CUTS) if t>=c)
    c0=CUTS[i]; c1=CUTS[i+1] if i+1<len(CUTS) else MEND
    cx,cy,w,z0,z1=SHOTS[i]; z=z0+(z1-z0)*ease((t-c0)/(c1-c0))
    im=box(ill,cx,cy,w,z)
    a=arr(im.filter(ImageFilter.GaussianBlur(5)) if t-c0<0.06 else im)
    a=(a-110)*1.18+120; a=a*np.array([1.05,0.98,0.88],np.float32)*vig
    return dust(a,t,0.7)
def intro(t):
    k=clamp(t/4.0); cy=1300-ease(k)*950
    im=box(ill,512,cy,1024,1.15)
    a=arr(im)*(0.04+0.62*ease(t/3.0))*np.array([1.05,0.97,0.85],np.float32)*vig
    a=a+lightrays(t,W*0.5,H*0.5,0.4)*np.array([255,205,120],np.float32)*0.12*ease(t/3)
    return dust(a,t,1.0)
def logo_section(t):
    tt=t-10.0; u=ease((t-14.0)/0.8)
    cy=1100-ease(tt/6.0)*820
    a=arr(box(ill,512,cy,1024,1.0))*0.7
    if u>0:
        a=a*(1-u)+COVB*0.42*u
    a=a*np.array([1.05,0.97,0.85],np.float32)*vig
    a=a+lightrays(t,W/2,H*0.42,0.6*max(0,1-tt/2.2)+0.12)*np.array([255,205,120],np.float32)*0.45*(1 if t<14 else 0.6)
    a=dust(a,t,1.0,1.1)
    lw=860; k=clamp(tt/0.22); sc=1+1.6*(1-eo(k))
    if tt>=0.22: sc=1+0.045*math.exp(-(tt-0.22)*5)*math.cos((tt-0.22)*16)
    scl=1.0-0.28*u; ly=H*0.45+(235-H*0.45)*u; lx=W/2+(930-W/2)*u
    lh=int(lw*logo.height/logo.width)
    L=logo.resize((int(lw*sc*scl),int(lh*sc*scl)),Image.LANCZOS)
    sx,sy=shake(t,10.0,22,0.7); sx2,sy2=shake(t,14.0,9,0.4); ox=sx+sx2; oy=sy+sy2
    gl=Image.new('L',(W,H),0); gl.paste(L.split()[3],(int(lx-L.width/2),int(ly-L.height/2)))
    glb=arr(gl.filter(ImageFilter.GaussianBlur(30)))[...,None]/255
    a=a+glb*np.array([255,190,80],np.float32)*0.55*clamp(1.2*(1-tt/3)+0.35)
    canvas=Image.fromarray(np.clip(a,0,255).astype(np.uint8))
    if u>0:
        sp_=ill.resize((480,720),Image.LANCZOS); m_=np.ones((720,480),np.float32)
        ramp=np.linspace(0,1,70,dtype=np.float32); m_[:,:70]*=ramp; m_[:,-70:]*=ramp[::-1]
        canvas.paste(sp_,(int(120-30*(1-u)),0),Image.fromarray((m_*255*u).astype(np.uint8)))
    canvas.paste(L.convert('RGB'),(int(lx-L.width/2),int(ly-L.height/2)),mask=L.split()[3])
    a=arr(canvas)
    sw=(t-11.3)%3.2
    if t>11.3 and sw<0.7:
        xs=(sw/0.7)*(W+400)-200
        band=np.exp(-((xx-yy*0.5-(xs-300))/45.0)**2)
        lm=np.zeros((H,W),np.float32); la_=np.asarray(L.split()[3]).astype(np.float32)/255
        x0=int(lx-L.width/2); y0=int(ly-L.height/2)
        ys0=max(0,y0); ye=min(H,y0+L.height); xs0=max(0,x0); xe=min(W,x0+L.width)
        lm[ys0:ye,xs0:xe]=la_[ys0-y0:ye-y0,xs0-x0:xe-x0]
        a=a+(band*lm)[...,None]*np.array([255,240,200],np.float32)*0.9
    a=shock(a,t,10.0,W/2,H*0.45)
    a=shift(a,ox,oy)
    a=a+flash_amt(t,10.0,0.45,1.0)*255*np.array([1,.95,.8],np.float32)
    a=a+flash_amt(t,14.0,0.2,0.5)*255*WARM/255*255/255*1
    if TEXT and t>=14.0:
        a=glow_text(a,'2026年11月15日',fJ(58,FX),930,455+(1-eo((t-14.0)/0.2))*-18,eo((t-14.0)/0.35),sp=4,glow=1.3)
    if TEXT and t>=15.25:
        a=glow_text(a,'活 動 開 始 予 定',fJ(30,FB),930,525+(1-eo((t-15.25)/0.2))*-10,eo((t-15.25)/0.3),color=(255,225,160),sp=10,glow=0.8)
    a=a*(vig**(1-0.75*u))
    return letterbox(a,1-ease((t-14.0)/0.7) if t>=14.0 else 1.0)

def render_trailer(t):
    if t<4.0: a=intro(t)
    elif t<8.0:
        a=cutin_section(t)
        for h in HITS:
            if 0<=t-h<0.12: a=a+flash_amt(t,h,0.12,0.55)*WARM
            sx,sy=shake(t,h,7,0.2); 
            if sx or sy: a=shift(a,sx,sy)
    elif t<MEND:
        a=fullcut(t)
        c=max(c for c in CUTS if t>=c)
        sx,sy=shake(t,c,10,0.2); a=shift(a,sx,sy)
        a=a+flash_amt(t,c,0.12,0.9)*WARM
        if t>9.35: a*=1-ease((t-9.4)/0.1)
    elif t<10.0:
        d=np.sqrt((xx-W/2)**2+(yy-H/2)**2); k=ease((t-9.5)/0.5)
        a=(np.exp(-(d/(20+k*40))**2)*110*k)[...,None]*np.array([1,.8,.4],np.float32)*np.ones((H,W,3),np.float32)
    else:
        a=logo_section(t)
    wf=ease((t-(D2-1.0))/0.85)
    if wf>0: a=a*(1-wf)+SOFT*wf
    return np.clip(a,0,255).astype(np.uint8)

def job(args):
    kind,n=args
    return (render_open if kind=='o' else render_trailer)(n/FPS).tobytes()
def encode(kind,total,out):
    print('encoding',out,flush=True)
    p=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-c:v','libx264','-crf','16','-preset','medium','-pix_fmt','yuv420p',out],stdin=subprocess.PIPE)
    with Pool(4) as pool:
        for fr in pool.imap(job,[(kind,n) for n in range(total)],chunksize=4): p.stdin.write(fr)
    p.stdin.close(); p.wait()
if __name__=='__main__':
    if sys.argv[1]=='frames':
        k=sys.argv[2]
        for tt in map(float,sys.argv[3:]): Image.fromarray((render_open if k=='o' else render_trailer)(tt)).save(f'g_{k}{tt:05.2f}.png')
    elif sys.argv[1]=='open': encode('o',int(D_OPEN*FPS),sys.argv[2])
    else: encode('t',int(D2*FPS),sys.argv[2])
