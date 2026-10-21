"""Real UDP -> existing bridge -> WebSocket -> separate HTML in Chromium."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class IphoneInputBrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = subprocess.Popen(['node', 'tests/iphone_bridge_fixture.mjs'], cwd=ROOT,
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        cls.address = json.loads(cls.server.stdout.readline())
        cls.port = cls.address['httpPort']
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path=shutil.which('chromium'), args=[
            '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.terminate()
        cls.server.wait(timeout=10)
        cls.server.stdin.close()
        cls.server.stdout.close()

    def send(self, blends=None, **kw):
        frame = dict(FaceFound=True, Hotkey=-1, Rotation=dict(x=0, y=0, z=0), Position=dict(x=0, y=0, z=0),
                     BlendShapes=[dict(k=k, v=v) for k, v in (blends or {}).items()])
        frame.update(kw)
        self.server.stdin.write(json.dumps(frame) + '\n')
        self.server.stdin.flush()

    def page(self, source=''):
        self.send()
        page = self.browser.new_page(viewport=dict(width=1400, height=1000))
        self.addCleanup(page.close)
        self.errors = []
        page.on('pageerror', lambda e: self.errors.append(str(e)))
        page.route('**/owl_prince_tracking_config.json', lambda route: route.fulfill(
            json=dict(wsUrl=f'ws://localhost:{self.port}', smoothingMs=80)))
        page.goto(f'http://localhost:{self.port}/owl_prince_iphone_test.html{source}')
        page.wait_for_function('window.READY===true', timeout=60000)
        page.evaluate('M.stop()')
        return page

    def test_iphone_end_to_end_and_no_webcam_load(self):
        page = self.page()
        page.wait_for_function('trackingController.found')
        self.assertIsNone(page.evaluate('window.L2DTracker'))
        self.assertEqual(page.evaluate("performance.getEntriesByType('resource').filter(e=>/tracking_webcam|mediapipe|face_landmarker|wasm/.test(e.name)).length"), 0)
        self.send({'JawOpen': .8, 'EyeBlinkLeft': 1}, Rotation=dict(x=8, y=-4, z=2))
        page.wait_for_function('M.params.AngleX>3.8 && M.params.AngleY < -7.8 && M.params.MouthOpen>.9')
        self.assertEqual(page.evaluate('M.params.EyeLOpen'), 0)
        page.keyboard.press('c')
        page.wait_for_function('Math.abs(M.params.AngleX)<.1 && M.params.MouthOpen<.1')
        self.send(Hotkey=2)
        page.wait_for_function('M.params.Surprise===1')
        page.wait_for_timeout(150)
        self.assertEqual(page.evaluate('M.params.Surprise'), 1)
        page.keyboard.press('0')
        page.wait_for_function('M.params.Surprise===0')
        page.click('#auto')
        self.send({'MouthSmileLeft': .95, 'MouthSmileRight': .95})
        page.wait_for_function('M.params.Smile===1')
        self.send(FaceFound=False)
        page.wait_for_timeout(120)
        self.assertGreater(page.evaluate('M.params.Smile'), 0)
        self.assertLess(page.evaluate('M.params.Smile'), 1)
        page.wait_for_function('M.params.Smile<.01 && Math.abs(M.params.AngleX)<.1')
        # Disconnect the client; it must reconnect and resume live data.
        page.evaluate('trackingInput.socket.close()')
        self.send()
        page.wait_for_function('trackingInput.socket.readyState===1 && trackingController.found', timeout=10000)
        page.keyboard.press('c')
        self.send(Rotation=dict(x=8, y=-4, z=2))
        page.wait_for_function('M.params.AngleX>3.8')
        page.evaluate('M.render()')
        Path('/workspace/iphone-integration-check').mkdir(exist_ok=True)
        page.screenshot(path='/workspace/iphone-integration-check/iphone-test.png')
        self.assertEqual(self.errors, [])

    def test_webcam_only_loads_on_start_and_reuses_legacy_tracker(self):
        page = self.page('?source=webcam')
        self.assertIsNone(page.evaluate('window.L2DTracker'))
        page.evaluate("""()=>{
          window.cameraCalls=0;window.stoppedTracks=0;
          navigator.mediaDevices.getUserMedia=async()=>{cameraCalls++;const stream=new MediaStream();stream.getTracks=()=>[{stop:()=>stoppedTracks++}];return stream};
          HTMLMediaElement.prototype.play=async()=>{};
          Object.defineProperty(document.getElementById('vid'),'readyState',{get:()=>2});
          Object.defineProperty(document.getElementById('vid'),'currentTime',{get:()=>performance.now()});
        }""")
        page.route('**/vision_bundle.mjs', lambda route: route.fulfill(content_type='text/javascript', body='''
          export const FilesetResolver={forVisionTasks:async()=>({})};
          export const FaceLandmarker={createFromOptions:async()=>({detectForVideo:()=>({faceLandmarks:[]}),close:()=>{}})};
        '''))
        page.click('#start')
        page.wait_for_function('trackingInput.tracker?.running===true')
        self.assertEqual(page.evaluate('cameraCalls'), 1)
        self.assertEqual(page.evaluate('trackingInput.tracker.opts.autoSurprise'), False)
        self.assertEqual(page.evaluate('trackingInput.tracker.constructor===L2DTracker'), True)
        page.click('#stop')
        self.assertGreater(page.evaluate('stoppedTracks'), 0)
        self.assertFalse(page.evaluate('trackingInput.running'))
        self.assertEqual(self.errors, [])

    def test_old_and_new_model_render_identically_at_five_poses(self):
        page = self.page('?source=iphone')
        page.evaluate('trackingInput.stop()')
        old = self.browser.new_page(viewport=dict(width=1400, height=1000))
        self.addCleanup(old.close)
        old.goto(f'http://localhost:{self.port}/owl_prince.html')
        old.wait_for_function('window.READY===true', timeout=60000)
        render = '''async params=>{
          M.stop();M.auto={blink:false,owlBlink:false,breath:false,idle:false,physics:false};M.reset();
          M.setParams(params);M.render();
          const bytes=new TextEncoder().encode(document.getElementById('c').toDataURL());
          return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).join(',');
        }'''
        for pose in [{}, dict(AngleY=-10), dict(AngleX=-5, BodyX=-1),
                     dict(Smile=1, MouthOpen=.6, MouthForm=1), dict(Surprise=1, AngleZ=5, MouthOpen=1, MouthForm=2)]:
            self.assertEqual(page.evaluate(render, pose), old.evaluate(render, pose), pose)
        self.assertEqual(self.errors, [])


if __name__ == '__main__':
    unittest.main()
