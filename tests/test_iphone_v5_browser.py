"""Apply the HTML-only update to the previously distributed launcher, then feed VTS axes."""
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from zipfile import ZipFile
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class IphoneV5BrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='iphone v5 ')
        with ZipFile(ROOT / 'dist/lunaris_iphone_motion_v5_mac.zip') as archive:
            archive.extractall(cls.tmp.name)
        cls.package=Path(cls.tmp.name)/'Lunaris_MOTION5'
        assert (cls.package/'起動.command').read_bytes()==(ROOT/'kamikan-bridge/portable/起動.command').read_bytes()
        assert (cls.package/'bridge/src/bridge.js').read_bytes()==(ROOT/'kamikan-bridge/src/bridge.js').read_bytes()
        cls.config = json.loads((cls.package / 'html/owl_prince_tracking_config_v5.json').read_text())
        cls.fixture = subprocess.Popen(['node', str(ROOT / 'tests/portable_iphone_fixture.mjs'), str(cls.package),
                                        str(Path(cls.tmp.name) / 'settings/connection.json')],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        cls.port = json.loads(cls.fixture.stdout.readline())['httpPort']
        cls.url = f'http://localhost:{cls.port}'
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path=shutil.which('chromium'), args=[
            '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])
        cls.context = cls.browser.new_context(viewport=dict(width=1400, height=1000))

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop()
        cls.fixture.terminate(); cls.fixture.wait(timeout=10)
        cls.fixture.stdin.close(); cls.fixture.stdout.close(); cls.tmp.cleanup()

    def send(self, blends=None, **kw):
        frame = dict(FaceFound=True, Hotkey=-1, Rotation=dict(x=0, y=0, z=0), Position=dict(x=0, y=0, z=0),
                     BlendShapes=[dict(k=k, v=v) for k, v in (blends or {}).items()])
        frame.update(kw)
        self.fixture.stdin.write(json.dumps(frame) + '\n'); self.fixture.stdin.flush()

    def movement(self, right=0, down=0, tilt=0, position=None, blends=None):
        # Deliberately mixed raw axes: a fixed swap cannot solve this fixture.
        v=[.6*right-.8*down,.8*right+.6*down,-tilt]
        angle=math.hypot(*v);scale=math.sin(math.radians(angle)/2)/angle if angle else 0
        x,y,z=[a*scale for a in v];w=math.cos(math.radians(angle)/2)
        base=[10,-15,20];angle=math.hypot(*base);scale=math.sin(math.radians(angle)/2)/angle
        a,b,c=[value*scale for value in base];d=math.cos(math.radians(angle)/2)
        x,y,z,w=(w*a+x*d+y*c-z*b,w*b-x*c+y*d+z*a,w*c+x*b-y*a+z*d,w*d-x*a-y*b-z*c)
        rotation=dict(x=-math.degrees(math.atan2(2*(x*z+w*y),1-2*(x*x+y*y))),
                      y=-math.degrees(math.asin(max(-1,min(1,2*(w*x-y*z))))),
                      z=math.degrees(math.atan2(2*(x*y+w*z),1-2*(x*x+z*z))))
        self.send(blends,Rotation=rotation,Position=position or dict(x=0,y=0,z=0))

    def test_01_setup_then_horizontal_and_vertical_parameter_isolation(self):
        self.send()
        setup=self.context.new_page();self.addCleanup(setup.close)
        setup.goto(self.url);setup.fill('#ip','127.0.0.1');setup.click('#save')
        setup.evaluate("localStorage.setItem('lunaris.iphone.pitch.v22',JSON.stringify({pitchAxis:'x',pitchSign:1}))")
        setup.wait_for_function("document.getElementById('state').textContent.includes('顔を検出')")
        with setup.expect_popup() as popup:setup.click('#model')
        page=popup.value;self.addCleanup(page.close)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.wait_for_function('window.READY===true && trackingController.found',timeout=60000)
        self.assertIn('MOTION-5',page.title())
        page.wait_for_function("document.getElementById('verifiedVersion').textContent.includes('実行版 MOTION-5')")
        self.assertEqual(page.evaluate('trackingInput.mapper.motion.stage'),'front')
        self.movement(right=20,down=15,tilt=10,position=dict(x=100,y=-100,z=0))
        page.wait_for_timeout(450)
        for key in ['AngleX','AngleY','AngleZ','BodyX','BodyY']:self.assertEqual(abs(page.evaluate('M.params.'+key)),0)
        for movement,stage in [({},'down'),(dict(down=10),'right'),(dict(right=10),'tilt'),(dict(tilt=10),'ready')]:
            self.movement(**movement);page.wait_for_timeout(450);page.keyboard.press('Space')
            page.wait_for_function('(stage)=>trackingInput.mapper.motion.stage===stage',arg=stage)
        page.wait_for_function("document.getElementById('motionError').textContent.includes('保存しました')")
        self.assertIsNone(page.evaluate('window.L2DTracker'))
        page.evaluate('M.stop();M.auto={blink:false,owlBlink:false,breath:false,idle:false,physics:false}')
        output=Path('/workspace/iphone-v5-check');output.mkdir(exist_ok=True)
        trace=[]
        for label,move,expected in [
            ('right',dict(right=4),[3.65,0,0]),('left',dict(right=-4),[-3.65,0,0]),
            ('down',dict(down=4),[0,-3.65,0]),('up',dict(down=-4),[0,3.65,0]),
            ('tilt',dict(tilt=4),[0,0,3.65]),
            ('max_sideways',dict(right=60,position=dict(x=100,y=-100,z=0)),[5,0,0]),
            ('max_tilt',dict(tilt=30),[0,0,5]),
            ('left_cross',dict(right=-12,down=-3),[-5,0,0]),
            ('tilt_right_cross',dict(tilt=12,down=3),[0,0,5]),
            ('tilt_left_cross',dict(tilt=-12,down=-3),[0,0,-5]),
            ('up_no_squint',dict(down=-4,blends=dict(EyeBlinkLeft=.55,EyeBlinkRight=.6)),[0,3.65,0]),
            ('front',{},[0,0,0])]:
            self.movement(**move)
            page.wait_for_function('(p)=>Math.abs(M.params.AngleX-p[0])<.00009 && Math.abs(M.params.AngleY-p[1])<.00009 && Math.abs(M.params.AngleZ-p[2])<.00009',arg=expected)
            if label=='up_no_squint':
                self.assertEqual(page.evaluate('M.params.EyeLOpen'),1)
                self.assertEqual(page.evaluate('M.params.EyeROpen'),1)
                self.assertIn('上下 3.65',page.locator('#directionValues').inner_text())
            actual=page.evaluate('({AngleX:M.params.AngleX,AngleY:M.params.AngleY,AngleZ:M.params.AngleZ})')
            targets=page.evaluate('({AngleX:trackingController.target.AngleX,AngleY:trackingController.target.AngleY,AngleZ:trackingController.target.AngleZ})')
            trace.append(dict(input=label,expected=expected,target=targets,actual=actual))
            if label in ['right','left','down','up','front','up_no_squint','left_cross','tilt_left_cross']:
                page.evaluate('M.render()');page.screenshot(path=str(output/(label+'.png')))
        (output/'parameter-trace.json').write_text(json.dumps(trace,indent=2))
        self.movement();page.wait_for_timeout(450);page.keyboard.press('c')
        page.wait_for_function("document.getElementById('calibrationStatus').textContent.includes('記録しました')")
        self.send(dict(JawOpen=.8,EyeBlinkLeft=1));page.wait_for_function('M.params.MouthOpen>.95 && M.params.EyeLOpen===0')
        self.send(Hotkey=2);page.wait_for_function('M.params.Surprise===1')
        self.send(Hotkey=4);page.wait_for_function('trackingController.autoSmile===true')
        self.send(dict(MouthSmileLeft=.95,MouthSmileRight=.95));page.wait_for_function('M.params.Smile===1')
        self.send(FaceFound=False);page.wait_for_function('M.params.Smile<.01')
        self.assertEqual(errors,[])

    def test_02_saved_directions_survive_reload_and_C(self):
        self.movement()
        page=self.context.new_page();self.addCleanup(page.close)
        page.goto(self.url+'/owl_prince_iphone_test.html')
        page.wait_for_function('window.READY===true && trackingController.found',timeout=60000)
        self.assertEqual(page.evaluate('trackingInput.mapper.motion.stage'),'ready')
        page.evaluate('M.stop()')
        page.wait_for_timeout(450);page.keyboard.press('c')
        page.wait_for_function("document.getElementById('calibrationStatus').textContent.includes('記録しました')")
        self.movement(right=4);page.wait_for_function('M.params.AngleX>3.6 && Math.abs(M.params.AngleY)<.01')
        self.movement(down=4);page.wait_for_function('M.params.AngleY < -3.6 && Math.abs(M.params.AngleX)<.01')
        self.movement();page.wait_for_function('Math.abs(M.params.AngleY)<.01')
        page.evaluate("localStorage.setItem('lunaris.iphone.motion.verified.3',localStorage.getItem('lunaris.iphone.motion.verified.4'));localStorage.removeItem('lunaris.iphone.motion.verified.4')")
        page.reload();page.wait_for_function('window.READY===true && trackingController.found',timeout=60000)
        self.assertEqual(page.evaluate('trackingInput.mapper.motion.stage'),'ready')
        self.movement(down=-4);page.wait_for_function('M.params.AngleY>3.6 && Math.abs(M.params.AngleX)<.01')

    def test_03_same_character_rendering_at_five_poses(self):
        page=self.context.new_page();self.addCleanup(page.close)
        page.goto(self.url+'/owl_prince_iphone_test.html');page.wait_for_function('window.READY===true',timeout=60000)
        page.evaluate('trackingInput.stop()')
        (self.package/'html/reference_webcam.html').write_bytes((ROOT/'dist/owl_prince.html').read_bytes())
        old=self.context.new_page();self.addCleanup(old.close)
        old.goto(self.url+'/reference_webcam.html');old.wait_for_function('window.READY===true',timeout=60000)
        render="""async params=>{M.stop();M.auto={blink:false,owlBlink:false,breath:false,idle:false,physics:false};M.reset();M.setParams(params);M.render();
          return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(document.getElementById('c').toDataURL())))).join(',')}"""
        old.evaluate('(v)=>M.opts.view=v',page.evaluate('M.opts.view'))
        for pose in [{},dict(AngleY=-10),dict(AngleX=-5),dict(Smile=1,MouthOpen=.6,MouthForm=1),dict(Surprise=1,AngleZ=5,MouthOpen=1,MouthForm=2)]:
            self.assertEqual(page.evaluate(render,pose),old.evaluate(render,pose),pose)

    def test_035_upward_pupil_offset_is_zero(self):
        page=self.context.new_page();self.addCleanup(page.close)
        page.goto(self.url+'/owl_prince_iphone_motion_v5.html');page.wait_for_function('window.READY===true',timeout=60000)
        page.evaluate('trackingInput.stop();M.stop();M.auto={blink:false,owlBlink:false,breath:false,idle:false,physics:false};M.reset();M.setParams({AngleY:5});M.render()')
        result=page.evaluate("""()=>{const result={};for(const id of ['eyeL_iris','eyeR_iris','eyeL_surprise_iris','eyeR_surprise_iris']){
          const p=M.byId[id],enabled=Array.from(p._pos),gaze=p.effects.find(e=>e.gaze&&e.param==='AngleY');
          const save=gaze.map;gaze.map=[[-10,0,0],[5,0,0]];M._deform(p);result[id]={enabled,disabled:Array.from(p._pos)};gaze.map=save;
        }M.render();return result}""")
        for name,data in result.items():self.assertEqual(data['enabled'],data['disabled'],name)
        output=Path('/workspace/iphone-v5-check');output.mkdir(exist_ok=True)
        page.screenshot(path=str(output/'up_no_pupil_offset.png'))

    def test_036_lateral_travel_is_wider_and_stays_inside_the_view(self):
        page=self.context.new_page();self.addCleanup(page.close)
        page.goto(self.url+'/owl_prince_iphone_motion_v5.html');page.wait_for_function('window.READY===true',timeout=60000)
        page.evaluate('trackingInput.stop();M.stop();M.auto={blink:false,owlBlink:false,breath:false,idle:false,physics:false};M.reset();M.render()')
        output=Path('/workspace/iphone-v5-check');output.mkdir(exist_ok=True)
        for side in [-1,1]:
            page.evaluate('(x)=>{M.setParams({BodyX:0,AngleX:x*5,AngleY:-10,AngleZ:x*5});M.render()}',side)
            reference=page.evaluate('M.byId.frame_extension._pos[0]')
            page.evaluate('(x)=>{M.setParam("BodyX",x);M.render()}',side)
            self.assertAlmostEqual(page.evaluate('M.byId.frame_extension._pos[0]')-reference,side*135,places=3)
            bounds=page.evaluate("""()=>{let left=Infinity,right=-Infinity;for(const p of M.parts)for(let i=0;i<p._pos.length;i+=2){left=Math.min(left,p._pos[i]);right=Math.max(right,p._pos[i])}return {left,right,view:M.opts.view}}""")
            self.assertGreaterEqual(bounds['left'],bounds['view'][0]);self.assertLessEqual(bounds['right'],bounds['view'][0]+bounds['view'][2])
            page.screenshot(path=str(output/('travel_left.png' if side<0 else 'travel_right.png')))
        ranges=page.evaluate("Object.fromEntries(['AngleX','AngleY','AngleZ'].map(k=>[k,[M.paramDefs[k].min,M.paramDefs[k].max]]))")
        self.assertEqual(ranges,dict(AngleX=[-5,5],AngleY=[-10,5],AngleZ=[-5,5]))

    def test_037_sensitive_mouth_shapes_do_not_overlap(self):
        self.movement()
        page=self.context.new_page();self.addCleanup(page.close)
        page.goto(self.url+'/owl_prince_iphone_motion_v5.html');page.wait_for_function('window.READY===true && trackingController.found',timeout=60000)
        page.evaluate('M.stop();M.auto={blink:false,owlBlink:false,breath:false,idle:false,physics:false}')
        page.wait_for_timeout(450);page.keyboard.press('c')
        page.wait_for_function("document.getElementById('calibrationStatus').textContent.includes('記録しました')")
        page.evaluate("""()=>{window.mouthOverlapErrors=[];function watch(){const active=['mouth_vA','mouth_vI','mouth_vE'].filter(id=>{M._deform(M.byId[id]);return M.byId[id]._opacity>.00001});if(active.length>1)mouthOverlapErrors.push(active);requestAnimationFrame(watch)}watch()}""")
        output=Path('/workspace/iphone-v5-check');output.mkdir(exist_ok=True)
        values=[]
        for label,form,jaw,stretch in [('a',0,.04,0),('i',1,.02,.08),('e',2,.10,.05)]:
            self.movement(blends=dict(JawOpen=jaw,MouthStretchLeft=stretch,MouthStretchRight=stretch))
            page.wait_for_function('(form)=>M.params.MouthForm===form && M.params.MouthOpen>.04 && M.params.MouthOpen<1',arg=form)
            page.wait_for_timeout(300);page.evaluate('M.render()')
            active=page.evaluate("['mouth_vA','mouth_vI','mouth_vE'].filter(id=>M.byId[id]._opacity>0)")
            self.assertEqual(active,[['mouth_vA','mouth_vI','mouth_vE'][form]])
            values.append(dict(shape=label,jaw=jaw,stretch=stretch,open=page.evaluate('M.params.MouthOpen'),active=active))
            page.screenshot(path=str(output/('mouth_'+label+'.png')))
        self.movement();page.wait_for_function('M.params.MouthOpen===0')
        self.assertEqual(page.evaluate('mouthOverlapErrors'),[])
        (output/'mouth-values.json').write_text(json.dumps(values,indent=2))

    def test_04_file_opening_explains_correct_connection(self):
        page=self.context.new_page();self.addCleanup(page.close)
        page.set_content((ROOT/'dist/owl_prince_iphone_motion_v5.html').read_text(),wait_until='load')
        page.wait_for_function("window.READY===true && trackingInput.phase==='blocked'",timeout=60000)
        self.assertEqual(page.locator('#openRelay').get_attribute('href'),'http://localhost:8765/')
        self.assertEqual(page.evaluate('trackingInput.attempts'),0)

    def test_05_wrong_bridge_version_prevents_tracking(self):
        page=self.context.new_page();self.addCleanup(page.close)
        page.route('**/api/status',lambda route:route.fulfill(json=dict(appId='KamikanPortable:owl-prince',version='1.0.0',fps=0,faceFound=False)))
        page.goto(self.url+'/owl_prince_iphone_motion_v5.html')
        page.wait_for_function('window.READY===true',timeout=60000)
        page.wait_for_function("document.getElementById('status').textContent.includes('以前の中継')")
        self.assertEqual(page.evaluate('trackingInput.attempts'),0)
        self.assertFalse(page.evaluate('trackingInput.running'))



if __name__=='__main__':unittest.main()
