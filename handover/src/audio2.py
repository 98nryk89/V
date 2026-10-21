import numpy as np, wave
SR=44100
rng=np.random.default_rng(11)
def t(n): return np.arange(n)/SR
def mf(m): return 440*2**((m-69)/12)
class Bus:
    def __init__(s,D): s.N=int(SR*D); s.L=np.zeros(s.N); s.R=np.zeros(s.N)
    def add(s,sig,at,pan=0.0,g=1.0):
        i=int(round(at*SR)); sig=np.asarray(sig)
        if i>=s.N: return
        seg=sig[:s.N-i]*g
        s.L[i:i+len(seg)]+=seg*(1-max(pan,0)); s.R[i:i+len(seg)]+=seg*(1+min(pan,0))
    def stereo(s): return np.stack([s.L,s.R],1)
def lp(x,k):
    c=np.cumsum(np.insert(x,0,0)); y=(c[k:]-c[:-k])/k; return np.concatenate([np.zeros(k-1),y])
def noise(d): return rng.standard_normal(int(SR*d))
def env(d,a=0.005,dec=3.0):
    x=t(int(SR*d)); return np.minimum(x/a,1)*np.exp(-x*dec)
def thump(d=1.2,f0=110,f1=38,dec=3.5,g=1.0):
    x=t(int(SR*d)); ph=2*np.pi*(f1*x+(f0-f1)*(1-np.exp(-x*18))/18)
    return np.sin(ph)*env(d,0.002,dec)*g
def boom():
    x=thump(3.5,90,30,1.3)*1.2
    n=lp(noise(3.5),6)*env(3.5,0.001,2.0)*0.8
    n=n+noise(3.5)*env(3.5,0.001,5)*0.5
    return x+n
def hit(g=1.0):
    a=thump(0.7,150,45,7,g); n=noise(0.5)*env(0.5,.001,14)*0.45*g; a[:len(n)]+=n; return a
def whoosh(d,up=True,g=0.5):
    n=noise(d); x=t(len(n)); a=lp(n,4)-lp(n,40)
    sh=np.sin(np.pi*x/d)**2 if not up else np.sin(np.pi*x/d)**2*(x/d)**0.5
    return a*sh*g*3
def bell(f,d=2.5,g=0.3):
    x=t(int(SR*d)); s=0
    for r,a in [(1,1),(2.76,.5),(5.4,.25),(8.93,.12)]:
        s=s+a*np.sin(2*np.pi*f*r*x)*np.exp(-x*(2+r*0.8))
    return s*g*np.minimum(x/.003,1)
def reverb(sig,d=2.8,wet=0.25):
    ir=rng.standard_normal(int(SR*d))*np.exp(-t(int(SR*d))*2.2); ir=lp(ir,3)
    n=len(sig)+len(ir); F=1<<(n-1).bit_length()
    y=np.fft.irfft(np.fft.rfft(sig,F)*np.fft.rfft(ir,F),F)[:len(sig)]
    return y/(np.abs(y).max()+1e-9)*np.abs(sig).max()*wet*2
def piano(m,d=2.6,g=1.0):
    x=t(int(SR*d)); f=mf(m); s=0
    for n in range(1,8):
        s=s+(1/n**1.1)*np.sin(2*np.pi*f*n*(1+0.0004*n*n)*x)*np.exp(-x*(1.1+0.9*n))
    return s*np.minimum(x/0.003,1)*g
def strings(ms,d,att=0.6,rel=0.8,g=1.0,k=14):
    x=t(int(SR*d)); s=0
    for m in ms:
        f=mf(m)
        for dt in (-0.7,0.0,0.7): s=s+(2*(((f+dt)*x)%1)-1)
    s=lp(s,k)/ (len(ms)*3)
    return s*np.minimum(x/att,1)*np.clip((d-x)/rel,0,1)*g
def lead(m,d,g=1.0,att=0.05,rel=0.25):
    x=t(int(SR*d)); f=mf(m)
    vib=1+0.004*np.sin(2*np.pi*5.5*x)*np.minimum(x/0.5,1)
    ph=np.cumsum(f*vib)/SR; s=0
    for dt in (0.996,1.0,1.004): s=s+(2*((ph*dt)%1)-1)
    s=lp(s,8)/3
    return s*np.minimum(x/att,1)*np.clip((d-x)/rel,0,1)*g
def bass(m,d=1.2,g=1.0):
    x=t(int(SR*d)); f=mf(m)
    s=np.sin(2*np.pi*f*x)+0.5*lp(2*((f*x)%1)-1,30)
    return s*np.minimum(x/0.01,1)*np.exp(-x*1.8)*g
CH={'Bm':(47,[59,62,66]),'G':(43,[55,59,62]),'D':(38,[62,66,69]),'A':(45,[57,61,64])}
def arp(bus,at,name,notes=8,step=0.25,g=0.14,vel_curve=None):
    tr=CH[name][1]; pat=[tr[0],tr[1],tr[2],tr[0]+12,tr[1]+12,tr[0]+12,tr[2],tr[1]]
    for i in range(notes):
        v=g*(0.85+0.15*(i%2==0))
        bus.add(piano(pat[i%8],2.0,v),at+i*step,pan=(-0.3 if i%2 else 0.3))
def melody(bus,at,notes,gp=0.22,gb=0.10,gl=0.0):
    for b,m,dur in notes:
        s=at+b*0.5; d=dur*0.5
        if gp: bus.add(piano(m,2.6,gp),s)
        if gb: bus.add(bell(mf(m+12) if False else mf(m),2.2,gb),s)
        if gl: bus.add(lead(m,d+0.15,gl),s)
def finish(st,path,gain=-18.0,pre=None):
    r=np.sqrt((st**2).mean()); st=st*(10**(gain/20)/r)
    st=np.tanh(st/0.9)*0.9
    w=wave.open(path,'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((np.clip(st,-1,1)*32767).astype('<i2').tobytes()); w.close()
    print(path,st.shape,'peak',np.abs(st).max(),'rms dB',20*np.log10(np.sqrt((st**2).mean())))
    return 10**(gain/20)/r
def fadeenv(N,pts):
    x=np.arange(N)/SR; return np.interp(x,[p[0] for p in pts],[p[1] for p in pts])

# ================= OPENING CARD (5.4s) =================
def opening():
    D=5.4; m=Bus(D); fx=Bus(D)
    m.add(strings([59,62,66,71],3.2,1.3,1.2,0.5),0.0); m.add(strings([55,59,62,67],3.2,1.0,1.4,0.5),2.4)
    m.add(bass(35+12,3.0,0.5),0.0); m.add(bass(43,3.0,0.5),2.5)
    for b,mm,dur in [(1.4,71,1),(2.4,74,1),(3.4,79,1.5)]:
        pass
    for tt,mm,g in [(0.7,71,.30),(1.15,74,.28),(1.6,79,.30),(2.05,78,.22)]:
        m.add(piano(mm,2.6,g),tt); m.add(bell(mf(mm+12),2.2,0.07),tt)
    for tt,mm in [(2.4,83),(2.85,86),(3.3,90),(3.75,86)]:
        m.add(piano(mm,2.6,0.2),tt); m.add(bell(mf(mm),2.2,0.09),tt)
    for tt,f in [(0.7,1976),(2.35,2349),(3.3,2637)]:
        fx.add(bell(f,2.5,0.28),tt,0.3)
    fx.add(whoosh(0.8,True,0.3),0.0)
    mus=m.stereo(); rv=np.stack([reverb(m.L,2.8,0.35),reverb(m.R,2.8,0.35)],1)
    st=mus+rv+fx.stereo()
    st*=fadeenv(m.N,[(0,0),(0.25,1),(4.6,1),(5.4,0)])[:,None]
    finish(st,'open.wav',-21)
# ================= TRAILER (20.4s) =================
D=20.4
def trailer():
    m=Bus(D); fx=Bus(D)
    chords=[('Bm',0,2),('G',2,2),('D',4,2),('A',6,2),('G',8,1),('A',9,1),('D',10,2),('A',12,2),('Bm',14,2),('G',16,1),('A',17,1),('D',18,2.4)]
    for name,s,d in chords:
        bar=int(s//2)
        # arpeggios
        if s<10 or s>=14 and s<18:
            g=[0.10,0.12,0.14,0.15,0.16,0,0,0,0.11,0.12,0.12,0][min(bar,11)] if False else (0.10+0.012*min(bar,4) if s<10 else 0.11)
            arp(m,s,name,notes=int(d/0.25),g=g)
        if 10<=s<14: arp(m,s,name,notes=int(d/0.25),g=0.10)
        if s==18: arp(m,s,name,notes=8,g=0.12)
        # pad strings (enter bar 2)
        tr=CH[name][1]
        if s>=4:
            pg=0.10 if s<8 else (0.14 if s<10 else 0.17)
            m.add(strings(tr+[tr[0]+12],d+0.4,0.5,0.9,pg),s)
        # bass
        b=CH[name][0]
        if s>=4:
            if 10<=s<18 :
                for k in range(int(d/0.5)): m.add(bass(b+(12 if k%4==3 else 0),0.7,0.30),s+k*0.5)
            else:
                for k in range(int(d/1.0)): m.add(bass(b,1.2,0.30),s+k*1.0)
        elif s>=2: m.add(bass(b,2.0,0.22),s)
    # ---- melody
    B=lambda bar:bar*2.0
    mel1=[(1,[(0,71,1),(1,74,1),(2,79,1.5),(3.5,78,.5)]),
          (2,[(0,78,1),(1,81,1),(2,86,2)]),
          (3,[(0,85,1),(1,83,1),(2,81,2)]),
          (4,[(0,83,1),(1,81,.5),(1.5,79,.5),(2,81,2)])]
    for bar,notes in mel1: melody(m,B(bar),notes,gp=0.26,gb=0.11)
    mel2=[(5,[(0,81,1),(1,86,1),(2,90,2)]),
          (6,[(0,88,1),(1,86,1),(2,85,1),(3,81,1)]),
          (7,[(0,86,1),(1,83,1),(2,86,1),(3,90,1)]),
          (8,[(0,91,1.5),(1.5,90,.5),(2,88,1),(3,85,1)]),
          (9,[(0,86,6)])]
    for bar,notes in mel2:
        melody(m,B(bar),notes,gp=0.18,gb=0.12,gl=0.30)
        # octave-down string double for weight
        for b_,mm,dur in notes: m.add(lead(mm-12,dur*0.5+0.2,0.12),B(bar)+b_*0.5)
    # ---- percussion / sfx
    PENT=[86,88,90,93,95,98]
    hits=[4.0,4.5,5.0,5.5,6.0,6.5,7.0,7.5,7.75]
    cuts=[8.0,8.25,8.5,8.75,9.0,9.2,9.35]
    for i,h in enumerate(hits+cuts):
        fx.add(hit(0.6+i*0.03),h,(-1)**i*0.4,0.8)
        fx.add(whoosh(0.28,True,0.32),h-0.26,(-1)**i*0.5)
        fx.add(bell(mf(PENT[i%6]),2.0,0.22),h+0.02,(-1)**i*0.5)
    # riser + snare roll
    d=2.0; r=noise(d); xr=t(len(r)); ph=np.cumsum(np.interp(xr,[0,d],[300,2200]))/SR
    tone=sum(np.sin(2*np.pi*ph*mm)*a for mm,a in [(1,1),(1.5,.6),(2,.4)])*np.interp(xr,[0,d],[0,1])**2*0.10
    rn=(lp(r,3)-lp(r,30))*np.interp(xr,[0,d],[0,1])**2.5*1.6
    fx.add(tone+rn,7.5)
    tt=8.0; step=0.125
    while tt<9.5:
        v=0.15+0.5*((tt-8.0)/1.5); fx.add(noise(0.12)*env(0.12,0.001,25)*v,tt); fx.add(thump(0.25,120,60,10,v*0.6),tt)
        step=0.125 if tt<8.9 else 0.0625; tt+=step
    fx.add(whoosh(1.0,True,0.7),8.6)
    # black-beat suspension then slam
    m.add(strings([57,61,64,69],0.9,0.2,0.4,0.18),9.0)
    for tt in (9.6,9.82): fx.add(thump(.5,90,40,9,0.7),tt)
    fx.add(whoosh(0.5,False,0.9),9.75)
    fx.add(boom(),10.0,0,0.95)
    fx.add(reverb(boom()[:int(SR*2)],3.0,0.5),10.0)
    st_=0; x2=t(int(SR*3.0))
    for f in [65.4,98,130.8,196]:
        for dt in [-0.4,0.4]: st_=st_+(2*(((f+dt)*x2)%1)-1)
    st_=lp(st_,10)*np.exp(-x2*1.1)*np.minimum(x2/.02,1)*0.10
    fx.add(st_,10.0)
    for k,(tt,f) in enumerate([(10.05,1568),(10.2,2093),(10.35,2637),(10.5,3136),(10.7,3951)]): fx.add(bell(f,2.5,0.22),tt,(-1)**k*0.6)
    # date hits
    fx.add(hit(1.2),14.0,0,0.9); fx.add(thump(1.5,100,34,2.5,0.8),14.0); fx.add(whoosh(0.4,False,.6),13.7)
    fx.add(hit(0.7),15.25,0,0.7); fx.add(whoosh(0.3,False,.4),15.0)
    for k,tt in enumerate(np.arange(15.4,19.2,0.5)): fx.add(bell(mf(PENT[k%6]+(0 if k%2 else 0)),2.0,0.12),tt,(-1)**k*0.7)
    # final tonic + sweep to white
    fx.add(thump(2.5,100,34,1.8,0.9),18.0); fx.add(hit(1.0),18.0,0,0.7)
    fx.add(whoosh(1.0,True,0.6),18.8)
    for k,mm in enumerate([74,78,81,86,90,93]): m.add(bell(mf(mm),2.4,0.14),18.0+k*0.12,(-1)**k*0.5)
    mus=m.stereo(); rv=np.stack([reverb(m.L,3.0,0.30),reverb(m.R,3.0,0.30)],1)
    st=mus+rv+fx.stereo()*1.0
    st*=fadeenv(m.N,[(0,0),(0.4,1),(20.0,1),(20.4,0.0)])[:,None]
    k=finish(st,'trailer2.wav',-17)
    fe=fadeenv(m.N,[(0,0),(0.4,1),(20.0,1),(20.4,0.0)])[:,None]
    for nm,x in (('trailer_music.wav',(mus+rv)),('trailer_sfx.wav',fx.stereo())):
        y=np.clip(x*fe*k*0.708,-1,1)
        w=wave.open(nm,'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((y*32767).astype('<i2').tobytes()); w.close()
# ================= END CARD (3.6s) =================
def endcard():
    D=3.6; m=Bus(D); fx=Bus(D)
    m.add(strings([62,66,69,74,78],3.6,0.15,1.8,0.22),0.0); m.add(bass(38,2.5,0.3),0.0)
    for k,mm in enumerate([74,78,81,86,90]):
        m.add(piano(mm,2.6,0.22),0.0+k*0.11); m.add(bell(mf(mm+12),2.2,0.10),0.0+k*0.11,(-1)**k*0.5)
    for mm in (62,66,69): m.add(piano(mm,2.6,0.2),0.02)
    mus=m.stereo(); rv=np.stack([reverb(m.L,2.5,0.35),reverb(m.R,2.5,0.35)],1)
    st=mus+rv+fx.stereo()
    st*=fadeenv(m.N,[(0,1),(2.6,0.9),(3.6,0)])[:,None]
    finish(st,'endcard.wav',-23)
if __name__=='__main__':
    opening(); trailer(); endcard()
