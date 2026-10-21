from PIL import Image, ImageDraw, ImageFont, ImageFilter
W,H=1280,720
def make(path,text,fontfile,size,cx,cy,sp,color=(255,236,190),glow=1.0):
    f=ImageFont.truetype(fontfile,size)
    m=Image.new('L',(W,H),0); d=ImageDraw.Draw(m)
    ws=[d.textlength(c,font=f) for c in text]; tot=sum(ws)+sp*(len(text)-1); x=cx-tot/2
    for c,w in zip(text,ws): d.text((x,cy),c,font=f,fill=255,anchor='lm'); x+=w+sp
    g=m.filter(ImageFilter.GaussianBlur(14)).point(lambda v:int(min(255,v*0.55*glow)))
    out=Image.new('RGBA',(W,H),(0,0,0,0))
    out=Image.alpha_composite(out,Image.merge('RGBA',[Image.new('L',(W,H),255),Image.new('L',(W,H),190),Image.new('L',(W,H),90),g]))
    out=Image.alpha_composite(out,Image.merge('RGBA',[Image.new('L',(W,H),color[0]),Image.new('L',(W,H),color[1]),Image.new('L',(W,H),color[2]),m]))
    out.save(path)
import os; os.makedirs('ov',exist_ok=True)
B='ShipporiMincho-Bold.ttf'; X='ShipporiMincho-ExtraBold.ttf'
make('ov/opening_line1.png','誰かにとっての「無価値」を',B,54,W/2,H/2-44,9)
make('ov/opening_line2.png','誰かにとっての「価値」に変える。',B,54,W/2,H/2+34,9)
make('ov/trailer_date.png','2026年11月15日',X,58,930,455,4,glow=1.3)
make('ov/trailer_date_sub.png','活動開始予定'.replace('','')[:0]+'活 動 開 始 予 定',B,30,930,525,10,color=(255,225,160),glow=0.8)
print('ok')
