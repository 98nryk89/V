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
        self.assertEqual(page.evaluate('M.params.VowelE'), 0)
        self.assertEqual(page.evaluate('M.rig.parts.filter(p=>p.id.startsWith("mouth")).map(p=>p.id).sort()'), ['mouth', 'mouth_vE'])
        self.assertEqual(page.evaluate('M.rig.params.filter(p=>/^Vowel/.test(p.id)).map(p=>p.id)'), ['VowelE'])
        heights = page.evaluate('''()=>{
          const p=M.parts.find(p=>p.id==='mouth_vE');
          return [0,.25,.5,.75,1].map(v=>{M.reset();M.setParam('VowelE',v);M._deform(p);
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
          const t=window.testTracker=new L2DTracker(M,{smooth:0});let result;
          t.landmarker={detectForVideo:()=>result};
          window.feedFace=(jaw,smile)=>{
            const l=Array.from({length:478},()=>({x:.5,y:.5}));
            for(const [i,x,y] of [[33,.4,.4],[263,.6,.4],[1,.5,.45],[152,.5,.65],[61,.46,.57],[291,.54,.57]])l[i]={x,y};
            result={faceLandmarks:[l],faceBlendshapes:[{categories:[['jawOpen',jaw],['mouthSmileLeft',smile],['mouthSmileRight',smile]].map(([categoryName,score])=>({categoryName,score}))}]};
            t.feed({},0);
          };feedFace(0,1);t.calibrate();feedFace(0,1);
        }''')
        self.assertEqual(page.evaluate('[M.params.Smile,M.params.VowelE]'), [0, 0])
        page.keyboard.press('1')
        self.assertEqual(page.evaluate('M.params.Smile'), 1)
        self.assertEqual(page.locator('#smile').get_attribute('aria-pressed'), 'true')
        page.evaluate('for(let i=0;i<12;i++)feedFace(.5,0)')
        self.assertEqual(page.evaluate('[M.params.Smile,M.params.VowelE]'), [1, 1])
        page.keyboard.press('1')
        self.assertEqual(page.evaluate('M.params.Smile'), 0)
        page.locator('#smile').click()
        page.keyboard.press('0')
        self.assertEqual(page.evaluate('M.params.Smile'), 0)
        page.locator('#smile').click()
        page.locator('#neutral').click()
        self.assertEqual(page.evaluate('M.params.Smile'), 0)
        # Text entry must not unexpectedly change the expression.
        page.evaluate('document.body.insertAdjacentHTML("beforeend", "<input id=test-text>")')
        page.locator('#test-text').focus()
        page.keyboard.press('1')
        self.assertEqual(page.evaluate('M.params.Smile'), 0)
        page.evaluate('document.getElementById("test-text").remove()')
        mouth = page.locator('#params .row').filter(has_text='口の開閉').locator('input')
        self.assertEqual(mouth.get_attribute('step'), '0.01')
        for value in ['0', '0.25', '0.5', '0.75', '1']:
            mouth.fill(value)
            mouth.dispatch_event('input')
            self.assertEqual(page.evaluate('M.params.VowelE'), float(value))
        page.locator('#a_mouse').check()
        box = page.locator('#c').bounding_box()
        page.mouse.move(box['x'] + box['width'] * .9, box['y'] + box['height'] * .8)
        self.assertGreater(page.evaluate('M.params.BodyX'), .7)
        self.assertGreater(page.evaluate('M.params.BodyY'), .5)
        self.assertLessEqual(abs(page.evaluate('M.params.AngleX')), 5)
        page.locator('#a_mouse').uncheck()
        page.locator('#reset').click()
        self.assertEqual(page.evaluate('[M.params.Smile,M.params.VowelE,M.params.BodyX,M.params.BodyY]'), [0, 0, 0, 0])
        if capture and os.environ.get('CONTROL_PREVIEW_DIR'):
            out = Path(os.environ['CONTROL_PREVIEW_DIR'])
            out.mkdir(parents=True, exist_ok=True)
            poses = {'neutral': {}, 'left': {'BodyX': -1}, 'right': {'BodyX': 1},
                     'up': {'BodyY': -1}, 'down': {'BodyY': 1}, 'quarter': {'VowelE': .25},
                     'half': {'VowelE': .5}, 'threequarter': {'VowelE': .75}, 'open': {'VowelE': 1},
                     'smile': {'Smile': 1}, 'smile_open': {'Smile': 1, 'VowelE': 1}}
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
