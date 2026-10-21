import numpy as np, sys, subprocess, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter
W,H,FPS,D=1280,720,30,22.0
rng=np.random.default_rng(3)
ill=Image.open('illustration_full.jpg').convert('RGB')
logo=Image.open('logo.png')
FB='ShipporiMincho-Bold.ttf'; FX='ShipporiMincho-ExtraBold.ttf'
def clamp(x,a=0,b=1): return max(a,min(b,x))
def ease(x): x=clamp(x); return x*x*(3-2*x)
def eo(x): x=clamp(x); return 1-(1-x)**3
def box(img,cx,cy,w,s=1.0):
    h=w*9/16; w/=s; h/=s
    cx=clamp(cx,w/2,img.width-w/2); cy=clamp(cy,h/2,img.height-h/2)
    return img.resize((W,H),Image.LANCZOS,box=(cx-w/2,cy-h/2,cx+w/2,cy+h/2))
def arr(im): return np.asarray(im).astype(np.float32)
# ---- precomputed layers
ILLA=arr(ill)
bg_dark=None
# letterbox
def letterbox(a,k=1.0):
    bar=int(H*0.115*k)
    if bar>0: a[:bar]=0; a[H-bar:]=0
    return a
# vignette
yy,xx=np.mgrid[0:H,0:W]; vig=1-0.55*(((xx-W/2)/(W/2))**2+((yy-H/2)/(H/2))**2)**1.2; vig=np.clip(vig,0.25,1)[...,None].astype(np.float32)
# gold dust particles
NP=160; px=rng.random(NP)*W; py=rng.random(NP)*H; ps=rng.random(NP)*1.8+0.6; pv=rng.random(NP)*30+10; pph=rng.random(NP)*6.28
def dust(a,t,amt=1.0,bright=1.0):
    layer=np.zeros((H,W,3),np.float32)
    ov=Image.new('RGB',(W,H)); d=ImageDraw.Draw(ov)
    for i in range(NP):
        x=(px[i]+math.sin(t*0.7+pph[i])*20)%W; y=(py[i]-pv[i]*t)%H
        tw=0.5+0.5*math.sin(t*4+pph[i]*3)
        r=ps[i]*(1+tw*.6); c=int(255*tw*bright*amt)
        d.ellipse((x-r,y-r,x+r,y+r),fill=(c,int(c*.82),int(c*.45)))
    g=arr(ov.filter(ImageFilter.GaussianBlur(1.3)))*2.2
    return a+g
def glow_text(a,text,font,cx,cy,alpha,color=(255,236,190),sp=0,glow=1.0,scale=1.0):
    if alpha<=0.003: return a
    lay=Image.new('L',(W,H),0); d=ImageDraw.Draw(lay)
    # letter-spaced draw
    f=font
    ws=[d.textlength(ch,font=f) for ch in text]; tot=sum(ws)+sp*(len(text)-1)
    x=cx-tot/2
    for ch,w_ in zip(text,ws):
        d.text((x,cy),ch,font=f,fill=255,anchor='lm'); x+=w_+sp
    m=arr(lay)[...,None]/255
    gl=arr(lay.filter(ImageFilter.GaussianBlur(14)))[...,None]/255
    col=np.array(color,np.float32)
    a=a+gl*np.array([255,190,90],np.float32)*0.55*glow*alpha
    a=a*(1-m*alpha)+m*col*alpha
    return a
fJ=lambda s,b=FB: ImageFont.truetype(b,s)
# ---- backdrop for logo section: illustration cover crop with slow motion
def illus_crop(t,y0,y1,zoom0,zoom1,x0=512,x1=512,wid=1024):
    k=ease(t); z=zoom0+(zoom1-zoom0)*k; cy=y0+(y1-y0)*k; cx=x0+(x1-x0)*k
    return box(ill,cx,cy,wid,z)
# ---- montage shots: (cx,cy,w,zoom_from,zoom_to, dx)
shots=[(510,175,600,1.0,1.18),(770,215,520,1.0,1.2),(270,230,520,1.1,1.0),(480,650,560,1.0,1.18),
       (850,640,480,1.2,1.0),(280,1110,560,1.0,1.2),(540,1290,520,1.15,1.0),(840,1140,520,1.0,1.25),(500,185,420,1.0,1.5)]
cuts=[5.6,6.2,6.7,7.15,7.55,7.9,8.2,8.45,8.7]; MEND=9.0
def flash_amt(t,at,dur=0.18,peak=1.0):
    d=t-at; return peak*(1-d/dur) if 0<=d<dur else 0
def shake(t,at,amp,dur=0.5):
    d=t-at
    if d<0 or d>dur: return 0,0
    k=(1-d/dur)**2*amp; return math.sin(d*90)*k, math.cos(d*77)*k
def shift(a,dx,dy):
    dx=int(round(dx)); dy=int(round(dy))
    if dx==0 and dy==0: return a
    return np.roll(np.roll(a,dy,0),dx,1)
def lightrays(t,cx,cy,strength):
    n=18; ov=Image.new('L',(W,H),0); d=ImageDraw.Draw(ov)
    for i in range(n):
        ang=(i/n)*2*math.pi+t*0.15; w=0.07
        d.polygon([(cx,cy),(cx+math.cos(ang-w)*1600,cy+math.sin(ang-w)*1600),(cx+math.cos(ang+w)*1600,cy+math.sin(ang+w)*1600)],fill=int(255*strength))
    return arr(ov.filter(ImageFilter.GaussianBlur(12)))[...,None]/255
def shock(a,t,at,cx,cy):
    d=t-at
    if d<0 or d>0.9: return a
    r=eo(d/0.9)*900; thick=40+d*60
    dist=np.sqrt((xx-cx)**2+(yy-cy)**2); m=np.exp(-((dist-r)/thick)**2)*(1-d/0.9)
    return a+m[...,None]*np.array([255,220,150],np.float32)*0.6
def render(t):
    a=np.zeros((H,W,3),np.float32)
    # ---------- 1.0-5.6 : text over dark glimpses
    if t<5.6:
        base=illus_crop(clamp((t)/5.6),620,520,1.25,1.05,x0=480,x1=540)
        b=arr(base.filter(ImageFilter.GaussianBlur(6)))*0.22*ease(t/1.2)*(1-ease((t-5.2)/0.4)*0)
        a=b*vig
        a=dust(a,t,0.9*ease(t/1.5))
        f=fJ(58)
        a=glow_text(a,'誰かにとっての「無価値」が',f,W/2,H/2-40,eo((t-1.0)/0.8)*(1-ease((t-3.1)/0.35)),sp=10)
        a=glow_text(a,'誰かの「価値」になる。',f,W/2,H/2+10,eo((t-3.2)/0.8)*(1-ease((t-5.1)/0.4)),sp=10)
        # fade-to-black glimpse at the very start
    elif t<MEND:
        i=max(j for j,c in enumerate(cuts) if t>=c)
        c0=cuts[i]; c1=cuts[i+1] if i+1<len(cuts) else MEND
        k=(t-c0)/(c1-c0)
        cx,cy,w,z0,z1=shots[i]
        z=z0+(z1-z0)*ease(k)
        im=box(ill,cx,cy,w,z)
        a=arr(im)
        # motion blur on first frames
        if t-c0<0.07: a=arr(im.filter(ImageFilter.GaussianBlur(5)))
        # color grade: warmer, contrast
        a=(a-110)*1.18+120; a=a*np.array([1.05,0.98,0.88],np.float32)
        a=a*vig
        sx,sy=shake(t,c0,10,0.25); a=shift(a,sx,sy)
        a=a+flash_amt(t,c0,0.12,0.9)*255*np.array([1,.9,.7],np.float32)
        a=dust(a,t,0.7)
        if i==len(cuts)-1:  # last: accelerate to black
            a*=1-ease((t-8.75)/0.25)
    # ---------- 9.0-10.0 : black beat
    elif t<10.0:
        a=np.zeros((H,W,3),np.float32)
        # tiny ember glow growing
        k=ease((t-9.0)/1.0); 
        d=np.sqrt((xx-W/2)**2+(yy-H/2)**2)
        a+=(np.exp(-(d/(30+k*40))**2)*120*k)[...,None]*np.array([1,.8,.4],np.float32)
    # ---------- 10.0-22 : logo
    else:
        tt=t-10.0
        # backdrop: illustration tilting up from boots to face, slow
        bd=illus_crop(clamp(tt/10.0),420,1150 if False else 420,1.12,1.3,x0=512,x1=512,wid=1024)
        # tilt: pan y from low to high
        cy=1100-ease(tt/6.0)*820
        bd=box(ill,512,cy,1024,1.0+0.0*tt)
        a=arr(bd)*0.7
        # darken further for final card
        u=ease((t-14.0)/0.8)
        if u>0:
            cov=ill.resize((W,int(W*1.5)),Image.LANCZOS).crop((0,300,W,300+H)).filter(ImageFilter.GaussianBlur(14))
            a=a*(1-u)+arr(cov)*0.42*u
        a=a*np.array([1.05,0.97,0.85],np.float32)*vig
        # light rays at slam
        ray=lightrays(t,W/2,H*0.42,0.6*max(0,1-tt/2.2)+0.12)
        a=a+ray*np.array([255,205,120],np.float32)*0.45*(1 if t<14 else 0.6)
        a=dust(a,t,1.0,1.1)
        # logo placement
        lw=860 if t<13.8 else 860
        # slam anim 10.0-10.35 scale 2.6->1.0 w/ overshoot
        k=clamp(tt/0.22)
        sc=1+1.6*(1-eo(k))**1.0
        if tt>=0.22: sc=1+0.045*math.exp(-(tt-0.22)*5)*math.cos((tt-0.22)*16)
        # move up for date section
        up=u
        scl=1.0-0.28*up
        ly=H*0.45+(235-H*0.45)*up
        lx=W/2+(930-W/2)*up
        lh=int(lw*logo.height/logo.width)
        L=logo.resize((int(lw*sc*scl),int(lh*sc*scl)),Image.LANCZOS)
        la=1.0 if tt>0.0 else 0
        sx,sy=shake(t,10.0,22,0.7)
        sx2,sy2=shake(t,14.0,9,0.4)
        ox=sx+sx2; oy=sy+sy2
        # glow behind logo
        gl=Image.new('L',(W,H),0); gl.paste(L.split()[3],(int(lx-L.width/2),int(ly-L.height/2)))
        glb=arr(gl.filter(ImageFilter.GaussianBlur(30)))[...,None]/255
        a=a+glb*np.array([255,190,80],np.float32)*0.55*clamp(1.2*(1-tt/3)+0.35)
        canvas=Image.fromarray(np.clip(a,0,255).astype(np.uint8))
        if u>0:
            sp_=ill.resize((480,720),Image.LANCZOS); m_=np.ones((720,480),np.float32)
            ramp=np.linspace(0,1,70,dtype=np.float32); m_[:,:70]*=ramp; m_[:,-70:]*=ramp[::-1]
            spm=Image.fromarray((m_*255*u).astype(np.uint8)); ox_=int(120-30*(1-u))
            canvas.paste(sp_,(ox_,0),spm)
        canvas.paste(L.convert('RGB'),(int(lx-L.width/2),int(ly-L.height/2)),mask=L.split()[3])
        a=arr(canvas)
        # shine sweep across logo after settle
        sw=(t-11.3)%3.2
        if t>11.3 and sw<0.7:
            xs=(sw/0.7)*(W+400)-200
            band=np.exp(-((xx-yy*0.5-(xs-300))/45.0)**2)
            alp=arr(gl)[...,0]/255 if False else None
            lm=np.zeros((H,W),np.float32)
            la_=np.asarray(L.split()[3]).astype(np.float32)/255
            x0=int(lx-L.width/2); y0=int(ly-L.height/2)
            ys0=max(0,y0); ye=min(H,y0+L.height); xs0=max(0,x0); xe=min(W,x0+L.width)
            lm[ys0:ye,xs0:xe]=la_[ys0-y0:ye-y0,xs0-x0:xe-x0]
            a=a+(band*lm)[...,None]*np.array([255,240,200],np.float32)*0.9
        a=shock(a,t,10.0,W/2,H*0.45)
        a=shift(a,ox,oy)
        a=a+flash_amt(t,10.0,0.45,1.0)*255*np.array([1,.95,.8],np.float32)
        a=a+flash_amt(t,14.0,0.2,0.5)*255*np.array([1,.9,.7],np.float32)
        # date text
        fd=fJ(58,FX); 
        da=eo((t-14.0)/0.35)
        if t>=14.0:
            # slam-in: slight vertical drop
            a=glow_text(a,'2026年11月15日',fd,930,455+(1-eo((t-14.0)/0.2))*-18,da,sp=4,glow=1.3)
        if t>=15.25:
            f2=fJ(30,FB)
            a=glow_text(a,'活 動 開 始 予 定',f2,930,525+(1-eo((t-15.25)/0.2))*-10,eo((t-15.25)/0.3),color=(255,225,160),sp=10,glow=0.8)
            # thin gold lines
            dd=ImageDraw.Draw(Image.new('L',(1,1)))
        a=a*(vig**(1-0.75*u))
    # global: fade-in from black at very start / end fade
    a=a*(1-ease((t-20.6)/1.3))
    a=letterbox(a,1-ease((t-14.0)/0.7) if t>=14.0 else 1.0)
    return np.clip(a,0,255).astype(np.uint8)
if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='frames':
        for tt in map(float,sys.argv[2:]): Image.fromarray(render(tt)).save(f'f_{tt:05.2f}.png')
    else:
        p=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-c:v','libx264','-crf','16','-preset','medium','-pix_fmt','yuv420p','trailer_v.mp4'],stdin=subprocess.PIPE)
        for n in range(int(D*FPS)):
            p.stdin.write(render(n/FPS).tobytes())
        p.stdin.close(); p.wait()
