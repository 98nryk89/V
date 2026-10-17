"""Exercise the real viewer and exported HTML without a physical webcam.

Build and export first. Set CHROME_PATH to an installed Chromium executable.
"""
import base64
import functools
import http.server
import os
from pathlib import Path
import shutil
import threading
import unittest

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CHROME = os.environ.get('CHROME_PATH') or shutil.which('chromium')


@unittest.skipUnless(CHROME and (ROOT / 'projects/owl_prince/out/rig.json').exists(),
                     'requires built model and installed Chromium')
class ViewerControlsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(ROOT)))
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(executable_path=CHROME, args=[
            '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()

    def check_viewer(self, path, capture=False):
        page = self.browser.new_page(viewport={'width': 1200, 'height': 900})
        self.addCleanup(page.close)
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(f'http://127.0.0.1:{self.server.server_port}/{path}')
        page.wait_for_function('window.READY===true', timeout=60000)
        page.evaluate('M.stop(); M.auto={blink:false,breath:false,idle:false,physics:false}; M.reset();M.render()')
        self.assertEqual(page.evaluate('M.params.Smile'), 0)
        self.assertEqual(page.evaluate('M.params.MouthOpen'), 0)
        self.assertEqual(page.evaluate('M.rig.parts.filter(p=>p.id.startsWith("mouth")).map(p=>p.id).sort()'), ['mouth', 'mouth_vA', 'mouth_vE', 'mouth_vI'])
        self.assertEqual(page.evaluate('M.rig.params.filter(p=>/^Vowel/.test(p.id)).map(p=>p.id)'), [])
        # An invalid/intermediate selector must never blend both vowel textures.
        vowel_states = page.evaluate("""()=>{
          return [0,1,2,.5].map(shape=>{
            M.reset();M.setParams({MouthOpen:1,MouthForm:shape});M.render();
            return [M.byId.mouth_vA._opacity,M.byId.mouth_vI._opacity,M.byId.mouth_vE._opacity];
          });
        }""")
        self.assertEqual(vowel_states, [[1,0,0],[0,1,0],[0,0,1],[0,0,0]])
        closed = page.evaluate("""()=>{
          return [0,1,2].map(shape=>{M.setParams({MouthOpen:0,MouthForm:shape});M.render();
            return [M.byId.mouth_vA._opacity,M.byId.mouth_vI._opacity,M.byId.mouth_vE._opacity]});
        }""")
        self.assertEqual(closed, [[0,0,0],[0,0,0],[0,0,0]])

        heights = page.evaluate('''()=>{
          const p=M.parts.find(p=>p.id==='mouth_vA');
          return [0,.25,.5,.75,1].map(v=>{M.reset();M.setParam('MouthOpen',v);M._deform(p);
            const ys=Array.from(p._pos).filter((_,i)=>i%2);return Math.max(...ys)-Math.min(...ys)});
        }''')
        for small, large in zip(heights, heights[1:]):
            self.assertGreater(large, small + 1)
        ear_geometry = page.evaluate('''()=>{
          const skin=M.parts.find(p=>p.id==='earR_skin'),drop=M.parts.find(p=>p.id==='earR_drop');
          const area=(v,a,b,c)=>(v[2*b]-v[2*a])*(v[2*c+1]-v[2*a+1])-(v[2*b+1]-v[2*a+1])*(v[2*c]-v[2*a]);
          let areaError=0,attachmentError=0;
          for(const angle of [-10,5]){
            M.reset();M.setParams({AngleY:angle,PhysEarR:1});M._deform(skin);
            const t=skin.mesh.tris;
            for(let i=0;i<t.length;i+=3){const rest=area(skin._rest,t[i],t[i+1],t[i+2]);
              if(Math.abs(rest)>.01)areaError=Math.max(areaError,Math.abs(area(skin._pos,t[i],t[i+1],t[i+2])/rest-Math.cos(angle*Math.PI/180)))}
            const atStud=p=>{const q={...p,_rest:new Float32Array([699,446]),_pos:new Float32Array(2),_z:new Float32Array([p._zmean])};M._deform(q);return q._pos};
            const a=atStud(skin),b=atStud(drop);attachmentError=Math.max(attachmentError,Math.hypot(a[0]-b[0],a[1]-b[1]));
          }
          return {areaError,attachmentError};
        }''')
        self.assertLess(ear_geometry['areaError'], .005)
        self.assertLess(ear_geometry['attachmentError'], .001)
        # Hair pixels crossing the brows remain attached to skin even with
        # breathing, nodding and bangs physics. Test the built vertex depths.
        brow_attachment = page.evaluate("""()=>{
          const hair=M.byId.hair_head,face=M.byId.face;
          const ids=[];
          for(let i=0;i<hair._rest.length/2;i++){
            const x=hair._rest[2*i],y=hair._rest[2*i+1];
            if((x>=440&&x<=510&&y>=345&&y<=352)||(x>=605&&x<=655&&y>=337&&y<=344))ids.push(i);
          }
          let error=0;
          for(const sign of [-1,1]){
            M.reset();M.setParams({AngleX:sign*5,AngleY:-10,AngleZ:sign*5,Breath:1,PhysBangs:sign});M._deform(hair);
            for(const i of ids){
              const q={...face,_rest:new Float32Array(hair._rest.slice(2*i,2*i+2)),_pos:new Float32Array(2),_z:new Float32Array([hair._z[i]])};
              M._deform(q);error=Math.max(error,Math.hypot(q._pos[0]-hair._pos[2*i],q._pos[1]-hair._pos[2*i+1]));
            }
          }
          return {count:ids.length,error};
        }""")
        self.assertGreater(brow_attachment['count'], 10)
        self.assertLess(brow_attachment['error'], .01)
        # A continuous hair mesh must move below the ears without dragging body/owl.
        hair_motion = page.evaluate('''()=>{
          const hair=M.byId.hair_head;
          const area=(v,a,b,c)=>(v[2*b]-v[2*a])*(v[2*c+1]-v[2*a+1])-(v[2*b+1]-v[2*a+1])*(v[2*c]-v[2*a]);
          let minRatio=Infinity,maxRatio=0,lowerShift=0,bodyError=0;
          for(const sign of [-1,1]){
            M.reset();M.setParams({AngleX:sign*5,AngleY:-10,AngleZ:sign*5});M._deform(hair);
            const t=hair.mesh.tris;
            for(let i=0;i<t.length;i+=3){const a=area(hair._rest,t[i],t[i+1],t[i+2]);
              if(Math.abs(a)>1){const r=area(hair._pos,t[i],t[i+1],t[i+2])/a;minRatio=Math.min(minRatio,r);maxRatio=Math.max(maxRatio,r)}}
            const at=(part,x,y)=>{const q={...part,_rest:new Float32Array([x,y]),_pos:new Float32Array(2),_z:new Float32Array([100])};M._deform(q);return q._pos};
            const a=at(hair,350,1100),b=at(M.byId.body,350,1100),c=at(M.byId.owl,350,1100);
            lowerShift=Math.max(lowerShift,Math.hypot(a[0]-b[0],a[1]-b[1]));
            bodyError=Math.max(bodyError,Math.hypot(b[0]-c[0],b[1]-c[1]));
          }
          return {minRatio,maxRatio,lowerShift,bodyError};
        }''')
        self.assertGreater(hair_motion['minRatio'], .6)
        self.assertLess(hair_motion['maxRatio'], 1.5)
        self.assertGreater(hair_motion['lowerShift'], 1)
        self.assertLess(hair_motion['lowerShift'], 20)
        self.assertLess(hair_motion['bodyError'], .001)
        # Owl blinking continues when camera tracking disables human auto-blink.
        detail_motion = page.evaluate('''()=>{
          M.reset();M.auto={blink:false,owlBlink:true,breath:false,idle:false,physics:false};
          M.setParams({EyeLOpen:.43,EyeROpen:.72});M.owlBlink={next:.01,t:-1};
          let closed=0,minimum=1;
          for(let i=0;i<30;i++){M._drive(1/60);minimum=Math.min(minimum,M.params.OwlEyeOpen);if(M.params.OwlEyeOpen===0)closed++}
          const finalOpen=M.params.OwlEyeOpen,human=[M.params.EyeLOpen,M.params.EyeROpen];
          M.auto.owlBlink=false;M.setParam('OwlEyeOpen',.3);M._drive(.01);const held=M.params.OwlEyeOpen;
          M.reset();const ids=['hair_head','body','earL','earR_skin','hair_tip_L','hair_tip_R'];
          const rest=ids.map(id=>{M._deform(M.byId[id]);return Array.from(M.byId[id]._pos)});
          M.setParams({PhysHairL:1,PhysHairR:1});
          const shifts=ids.map((id,k)=>{M._deform(M.byId[id]);return Math.max(...M.byId[id]._pos.map((v,i)=>Math.abs(v-rest[k][i])))});
          const stages=[.9,.75,.5,.25,0].map(v=>{M.reset();M.setParam('EyeLOpen',v);return [1,2,3,4].map(k=>{const p=M.byId['eyeL_k'+k];M._deform(p);return p._opacity})});
          M.auto={blink:false,owlBlink:false,breath:false,idle:false,physics:false};M.reset();
          return {closed,minimum,finalOpen,human,held,shifts,stages};
        }''')
        self.assertGreaterEqual(detail_motion['closed'], 2)
        self.assertEqual(detail_motion['minimum'], 0)
        self.assertEqual(detail_motion['finalOpen'], 1)
        self.assertEqual(detail_motion['human'], [.43, .72])
        self.assertEqual(detail_motion['held'], .3)
        self.assertTrue(all(v < .001 for v in detail_motion['shifts'][:4]))
        for shift in detail_motion['shifts'][4:]:
            self.assertGreater(shift, 1)
            self.assertLess(shift, 9)
        # At each quarter state the top visible drawing is opaque, never a ghosted blend.
        for row, stage in zip(detail_motion['stages'], [0,1,2,3,4]):
            self.assertEqual(row, [1 if i < stage else 0 for i in range(4)])
        # At maximum pitch/yaw/tilt the upper white collar must stay opaque.
        # These samples lay in a visible transparent slit in the accepted baseline.
        collar_alpha = page.evaluate('''()=>{
          M.reset();M.setParams({AngleX:5,AngleY:5,AngleZ:5,BodyX:1,BodyY:1});M.render();
          const c=M.canvas,v=M.opts.view||[0,0,...M.rig.size],s=Math.min(c.width/v[2],c.height/v[3]);
          const ox=(c.width-v[2]*s)/2,oy=(c.height-v[3]*s)/2,gl=M.gl;
          return [[516,580],[521,585],[530,590],[535,595],[542,600],[550,605]].map(([x,y])=>{
            const px=Math.round(ox+(x+90-v[0])*s),py=Math.round(oy+(y+70-v[1])*s),rgba=new Uint8Array(4);
            gl.readPixels(px,c.height-1-py,1,1,gl.RGBA,gl.UNSIGNED_BYTE,rgba);return rgba[3];
          });
        }''')
        self.assertTrue(all(a > 230 for a in collar_alpha), collar_alpha)
        # All parts must translate together, without shearing the ears or neck.
        error = page.evaluate('''()=>{
          M.reset(); const before=M.parts.map(p=>{M._deform(p);return Array.from(p._pos)});
          M.setParams({BodyX:1,BodyY:-1});let error=0;
          M.parts.forEach((p,n)=>{M._deform(p);p._pos.forEach((v,i)=>{error=Math.max(error,Math.abs(v-before[n][i]-(i%2?-70:90)))})});
          return error;
        }''')
        self.assertLess(error, .001)
        self.assertEqual(page.evaluate('[M.params.AngleX,M.params.AngleY,M.params.AngleZ]'), [0, 0, 0])
        page.evaluate('M.reset()')
        # Synthetic detector output uses the same browser-side tracker as a webcam.
        page.evaluate('''()=>{
          const t=window.testTracker=new L2DTracker(M,{smooth:0,autoSmile:false});let result;
          t.landmarker={detectForVideo:()=>result};
          window.feedFace=(jaw,smile,stretch=0)=>{
            const l=Array.from({length:478},()=>({x:.5,y:.5}));
            for(const [i,x,y] of [[33,.4,.4],[263,.6,.4],[1,.5,.45],[152,.5,.65],[61,.46,.57],[291,.54,.57]])l[i]={x,y};
            result={faceLandmarks:[l],faceBlendshapes:[{categories:[['jawOpen',jaw],['mouthSmileLeft',smile],['mouthSmileRight',smile],['mouthStretchLeft',stretch],['mouthStretchRight',stretch]].map(([categoryName,score])=>({categoryName,score}))}]};
            t.feed({},0);
          };feedFace(0,1);t.calibrate();feedFace(0,1);
        }''')
        self.assertEqual(page.evaluate('[M.params.Smile,M.params.MouthOpen]'), [0, 0])
        self.assertTrue(page.locator('#a_smile').is_checked())
        page.evaluate('testTracker.setAutoSmile(true);for(let i=0;i<40;i++)feedFace(.15,.8)')
        self.assertEqual(page.evaluate('[M.params.Smile,M.params.MouthOpen]'), [0,0])
        page.evaluate('for(let i=0;i<8;i++)feedFace(0,.83)')
        self.assertEqual(page.evaluate('M.params.Smile'), 0)
        page.evaluate('for(let i=0;i<13;i++)feedFace(0,.83);M.render()')
        self.assertEqual(page.evaluate('M.params.Smile'), 1)
        page.wait_for_function("document.getElementById('smile').getAttribute('aria-pressed')==='true'")
        page.evaluate('for(let i=0;i<14;i++)feedFace(0,.1)')
        self.assertEqual(page.evaluate('M.params.Smile'), 0)
        page.evaluate('testTracker.setAutoSmile(false)')
        page.keyboard.press('1')
        self.assertFalse(page.locator('#a_smile').is_checked())
        self.assertEqual(page.evaluate('M.params.Smile'), 1)
        self.assertEqual(page.locator('#smile').get_attribute('aria-pressed'), 'true')
        page.evaluate('for(let i=0;i<12;i++)feedFace(.7,0)')
        self.assertEqual(page.evaluate('[M.params.Smile,M.params.MouthOpen]'), [1, 1])
        page.keyboard.press('1')
        self.assertEqual(page.evaluate('M.params.Smile'), 0)
        for _ in range(4):
            page.evaluate('feedFace(.28,0,.8)')
        page.evaluate('M.render()')
        self.assertEqual(page.evaluate('[M.params.MouthForm,M.byId.mouth_vA._opacity]'), [1,0])
        self.assertGreater(page.evaluate('M.byId.mouth_vI._opacity'), 0)
        for _ in range(4):
            page.evaluate('feedFace(.6,0,.8)')
        page.evaluate('M.render()')
        self.assertEqual(page.evaluate('[M.params.MouthForm,M.byId.mouth_vI._opacity]'), [0,0])
        self.assertGreater(page.evaluate('M.byId.mouth_vA._opacity'), 0)
        for _ in range(4):
            page.evaluate('feedFace(.4,0,.55)')
        page.evaluate('M.render()')
        self.assertEqual(page.evaluate('[M.params.MouthForm,M.byId.mouth_vA._opacity,M.byId.mouth_vI._opacity]'), [2,0,0])
        self.assertGreater(page.evaluate('M.byId.mouth_vE._opacity'), 0)
        page.locator('#smile').click()
        page.keyboard.press('0')
        self.assertEqual(page.evaluate('M.params.Smile'), 0)
        page.locator('#smile').click()
        page.locator('#neutral').click()
        self.assertEqual(page.evaluate('M.params.Smile'), 0)
        # Manual expressions are exclusive, survive tracking, and close cleanly.
        page.keyboard.press('2')
        self.assertEqual(page.evaluate('[M.params.Smile,M.params.Surprise]'), [0,1])
        self.assertEqual(page.locator('#surprise').get_attribute('aria-pressed'), 'true')
        page.evaluate('feedFace(0,1)')
        self.assertEqual(page.evaluate('M.params.Surprise'), 1)
        states = page.evaluate("""()=>{
          M.setParams({EyeLOpen:1,EyeROpen:1,MouthOpen:0,MouthForm:0});M.render();
          const open=[M.byId.eyeL_surprise._opacity,M.byId.eyeR_surprise._opacity];
          M.setParams({EyeLOpen:0,EyeROpen:0,MouthOpen:1});M.render();
          return {open,closed:[M.byId.eyeL_surprise._opacity,M.byId.eyeR_surprise._opacity],blink:M.byId.eyeL_k4._opacity,mouth:M.byId.mouth_vA._opacity};
        }""")
        self.assertEqual(states, dict(open=[1,1],closed=[0,0],blink=1,mouth=1))
        page.keyboard.press('1')
        self.assertEqual(page.evaluate('[M.params.Smile,M.params.Surprise]'), [1,0])
        page.locator('#surprise').click()
        self.assertEqual(page.evaluate('[M.params.Smile,M.params.Surprise]'), [0,1])
        page.keyboard.press('2')
        self.assertEqual(page.evaluate('M.params.Surprise'), 0)
        page.locator('#surprise').click()
        page.keyboard.press('0')
        self.assertEqual(page.evaluate('[M.params.Smile,M.params.Surprise]'), [0,0])
        page.locator('#surprise').click()
        page.locator('#reset').click()
        self.assertEqual(page.evaluate('M.params.Surprise'), 0)

        # Text entry must not unexpectedly change the expression.
        page.evaluate('document.body.insertAdjacentHTML("beforeend", "<input id=test-text>")')
        page.locator('#test-text').focus()
        page.keyboard.press('1')
        self.assertEqual(page.evaluate('M.params.Smile'), 0)
        page.evaluate('document.getElementById("test-text").remove()')
        mouth = page.locator('#params .row').filter(has_text='口の開き').locator('input')
        self.assertEqual(mouth.get_attribute('step'), '0.01')
        for value in ['0', '0.25', '0.5', '0.75', '1']:
            mouth.fill(value)
            mouth.dispatch_event('input')
            self.assertEqual(page.evaluate('M.params.MouthOpen'), float(value))
        page.locator('#a_mouse').check()
        box = page.locator('#c').bounding_box()
        page.mouse.move(box['x'] + box['width'] * .9, box['y'] + box['height'] * .8)
        self.assertGreater(page.evaluate('M.params.BodyX'), .7)
        self.assertGreater(page.evaluate('M.params.BodyY'), .5)
        self.assertLessEqual(abs(page.evaluate('M.params.AngleX')), 5)
        page.locator('#a_mouse').uncheck()
        page.locator('#reset').click()
        self.assertEqual(page.evaluate('[M.params.Smile,M.params.MouthOpen,M.params.BodyX,M.params.BodyY]'), [0, 0, 0, 0])
        matrix_motion = page.evaluate('''()=>{
          const tracker=new L2DTracker(M,{smooth:0});let result;
          tracker.landmarker={detectForVideo:()=>result};
          const feed=(yaw,pitch)=>{
            const d=Math.PI/180,cy=Math.cos(yaw*d),sy=Math.sin(yaw*d),cp=Math.cos(pitch*d),sp=Math.sin(pitch*d);
            const l=Array.from({length:478},()=>({x:.5,y:.5}));
            for(const [i,x,y] of [[33,.4,.4],[263,.6,.4],[1,.5,.45],[152,.5,.65],[61,.46,.57],[291,.54,.57]])l[i]={x,y};
            result={faceLandmarks:[l],facialTransformationMatrixes:[{data:[cy,0,-sy,0,sy*sp,cp,cy*sp,0,sy*cp,-sp,cy*cp,0,0,0,-50,1]}]};
            tracker.feed({},0);
          };
          M.reset();feed(0,0);const f=M.byId.face;M._deform(f);const rest=Array.from(f._pos);
          return [[20,0],[-20,0],[0,-20],[0,20]].map(([x,y])=>{feed(x,y);M._deform(f);
            const movement=Math.max(...f._pos.map((v,i)=>Math.abs(v-rest[i])));
            return {angle:[M.params.AngleX,M.params.AngleY],body:[M.params.BodyX,M.params.BodyY],movement};
          });
        }''')
        for result, expected in zip(matrix_motion, [[-5,0],[5,0],[0,5],[0,-10]]):
            self.assertEqual(result['angle'], expected)
            self.assertEqual(result['body'], [0,0])
            self.assertGreater(result['movement'], 1)
        page.evaluate('M.reset();M.render()')
        if capture and os.environ.get('CONTROL_PREVIEW_DIR'):
            out = Path(os.environ['CONTROL_PREVIEW_DIR'])
            out.mkdir(parents=True, exist_ok=True)
            poses = {'neutral': {}, 'left': {'BodyX': -1}, 'right': {'BodyX': 1},
                     'up': {'BodyY': -1}, 'down': {'BodyY': 1}, 'quarter': {'MouthOpen': .25},
                     'half': {'MouthOpen': .5}, 'threequarter': {'MouthOpen': .75}, 'open': {'MouthOpen': 1},
                     'smile': {'Smile': 1}, 'smile_open': {'Smile': 1, 'MouthOpen': 1}}
            for name, params in poses.items():
                data = page.evaluate('(p)=>{M.reset();M.setParams(p);M.renderStill(0);return document.getElementById("c").toDataURL().split(",")[1]}', params)
                (out / f'{name}.png').write_bytes(base64.b64decode(data))
        self.assertEqual(errors, [])

    def test_repository_viewer(self):
        self.check_viewer('viewer/index.html?model=../projects/owl_prince/out')

    def test_exported_viewer(self):
        self.check_viewer('dist/owl_prince.html', capture=True)


if __name__ == '__main__':
    unittest.main()
