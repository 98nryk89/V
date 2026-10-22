"""Apply the HTML-only update to the previously distributed launcher, then feed VTS axes."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from zipfile import ZipFile
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class IphoneConnectionV21BrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='iphone connection v21 ')
        with ZipFile(ROOT / 'dist/lunaris_iphone_mac.zip') as archive:
            archive.extractall(cls.tmp.name)
        cls.package = Path(cls.tmp.name) / 'Lunaris_iPhone'
        original_launcher = (cls.package / '起動.command').read_bytes()
        original_bridge = (cls.package / 'bridge/src/bridge.js').read_bytes()
        with ZipFile(ROOT / 'dist/lunaris_iphone_connection_v21_update.zip') as archive:
            for name in ['owl_prince_iphone_test.html', 'owl_prince_tracking_config_v2.json']:
                (cls.package / 'html' / name).write_bytes(archive.read('iPhone_v21_update/' + name))
        assert (cls.package / '起動.command').read_bytes() == original_launcher
        assert (cls.package / 'bridge/src/bridge.js').read_bytes() == original_bridge
        cls.config = json.loads((cls.package / 'html/owl_prince_tracking_config_v2.json').read_text())
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

    def test_axes_center_return_and_expressions_from_existing_launcher(self):
        self.send()
        setup = self.context.new_page(); self.addCleanup(setup.close)
        errors = []; setup.on('pageerror', lambda e: errors.append(str(e)))
        setup.goto(self.url)
        setup.fill('#ip', '127.0.0.1'); setup.click('#save')
        setup.wait_for_function("document.getElementById('state').textContent.includes('顔を検出')")
        with setup.expect_popup() as popup:
            setup.click('#model')
        model = popup.value; self.addCleanup(model.close)
        model.on('pageerror', lambda e: errors.append(str(e)))
        model.wait_for_function('window.READY===true && trackingController.found', timeout=60000)
        self.assertIn('v2.1', model.title())
        self.assertEqual(model.evaluate('trackingInput.endpoint'), f'ws://127.0.0.1:{self.port}/')
        self.assertEqual(model.evaluate('trackingInput.phase'), 'tracking')
        model.evaluate('M.stop(); M.auto={blink:false,owlBlink:false,breath:false,idle:false,physics:false}')
        model.wait_for_timeout(450); model.keyboard.press('c')
        model.wait_for_function("document.getElementById('calibrationStatus').textContent.includes('記録しました')")
        self.assertGreaterEqual(model.evaluate('trackingInput.mapper.calibrationSamples'), 10)
        output = Path('/workspace/iphone-connection-v21-check'); output.mkdir(exist_ok=True)

        self.send(Rotation=dict(x=0, y=-8, z=0))
        model.wait_for_function('M.params.AngleY < -7.5 && Math.abs(M.params.AngleX)<.01 && Math.abs(M.params.BodyX)<.01')
        model.evaluate('M.render()'); model.screenshot(path=str(output / 'down.png'))
        self.send(dict(JawOpen=.8, EyeBlinkLeft=1), Rotation=dict(x=0, y=-8, z=0))
        model.wait_for_function('M.params.MouthOpen>.95 && M.params.EyeLOpen===0')
        self.send(Rotation=dict(x=-4, y=0, z=0))
        model.wait_for_function('M.params.AngleX>3.5 && Math.abs(M.params.AngleY)<.01')
        model.evaluate('M.render()'); model.screenshot(path=str(output / 'turn.png'))
        self.send(Rotation=dict(x=-12, y=-15, z=4), Position=dict(x=3, y=-3, z=0))
        model.wait_for_function('M.params.AngleX>4.9 && M.params.AngleY < -9.9 && M.params.BodyX < -.55')
        saved = model.evaluate('JSON.stringify(trackingInput.mapper.neutral)')
        model.wait_for_timeout(400)
        self.send()
        model.wait_for_function('Math.abs(M.params.AngleX)<.01 && Math.abs(M.params.AngleY)<.01 && Math.abs(M.params.BodyX)<.01 && Math.abs(M.params.BodyY)<.01')
        self.assertEqual(model.evaluate('JSON.stringify(trackingInput.mapper.neutral)'), saved)
        self.send(Rotation=dict(x=.2, y=-.2, z=.1), Position=dict(x=.04, y=-.03, z=0))
        model.wait_for_function('trackingInput.mapper.latest.rotation.x===.2')
        model.wait_for_timeout(200)
        for param in ['AngleX', 'AngleY', 'AngleZ', 'BodyX', 'BodyY']:
            self.assertLess(abs(model.evaluate(f'M.params.{param}')), .005, param)
        model.evaluate('M.render()'); model.screenshot(path=str(output / 'returned.png'))
        self.send(Hotkey=2); model.wait_for_function('M.params.Surprise===1')
        self.send(Hotkey=4); model.wait_for_function('trackingController.autoSmile===true')
        self.send(dict(MouthSmileLeft=.95, MouthSmileRight=.95)); model.wait_for_function('M.params.Smile===1')
        self.assertIsNone(model.evaluate('window.L2DTracker'))
        self.send(FaceFound=False); model.wait_for_function('M.params.Smile<.01')
        self.assertEqual(errors, [])

    def test_direct_opening_notice_without_websocket_attempts(self):
        page = self.context.new_page(); self.addCleanup(page.close)
        page.set_content((ROOT / 'dist/owl_prince_iphone_v21.html').read_text(), wait_until='load')
        page.wait_for_function("window.READY===true && trackingInput.phase==='blocked'", timeout=60000)
        self.assertEqual(page.locator('#openRelay').get_attribute('href'), 'http://localhost:8765/')
        self.assertIn('接続画面', page.locator('#status').inner_text())
        self.assertEqual(page.evaluate('trackingInput.attempts'), 0)

    def test_v2_uses_the_exact_same_model_rendering_at_five_poses(self):
        v2 = self.context.new_page(); self.addCleanup(v2.close)
        v2.goto(self.url + '/owl_prince_iphone_test.html')
        v2.wait_for_function('window.READY===true', timeout=60000)
        v2.evaluate('trackingInput.stop()')
        # Serve the unchanged reference HTML through the already running test server.
        (self.package / 'html/reference_webcam.html').write_bytes((ROOT / 'dist/owl_prince.html').read_bytes())
        old = self.context.new_page(); self.addCleanup(old.close)
        old.goto(self.url + '/reference_webcam.html'); old.wait_for_function('window.READY===true', timeout=60000)
        render = '''async params=>{M.stop();M.auto={blink:false,owlBlink:false,breath:false,idle:false,physics:false};M.reset();M.setParams(params);M.render();
          return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(document.getElementById('c').toDataURL())))).join(',')}'''
        for pose in [{}, dict(AngleY=-10), dict(AngleX=-5, BodyX=-1),
                     dict(Smile=1, MouthOpen=.6, MouthForm=1), dict(Surprise=1, AngleZ=5, MouthOpen=1, MouthForm=2)]:
            self.assertEqual(v2.evaluate(render, pose), old.evaluate(render, pose), pose)


if __name__ == '__main__':
    unittest.main()
