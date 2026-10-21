"""Extract the actual distribution and operate the setup GUI -> UDP -> model."""
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


class PortableIphoneBrowserTest(unittest.TestCase):
    def test_extracted_distribution_setup_and_actual_model(self):
        with tempfile.TemporaryDirectory(prefix='lunaris portable ') as tmp:
            with ZipFile(ROOT / 'dist/lunaris_iphone_mac.zip') as archive:
                self.assertIsNone(archive.testzip())
                self.assertTrue((archive.getinfo('Lunaris_iPhone/起動.command').external_attr >> 16) & 0o111)
                archive.extractall(tmp)
            package = Path(tmp) / 'Lunaris_iPhone'
            manifest = json.loads((package / 'MANIFEST.json').read_text())
            for name, expected in manifest['files'].items():
                self.assertEqual(hashlib.sha256((package / name).read_bytes()).hexdigest(), expected)
            self.assertEqual((package / 'html/owl_prince_iphone_test.html').read_bytes(), (ROOT / 'dist/owl_prince_iphone_test.html').read_bytes())
            settings = Path(tmp) / 'saved/connection.json'
            fixture = subprocess.Popen(['node', str(ROOT / 'tests/portable_iphone_fixture.mjs'), str(package), str(settings)],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            try:
                ports = json.loads(fixture.stdout.readline())
                url = f'http://localhost:{ports["httpPort"]}'

                def send(blends=None, **kw):
                    frame = dict(FaceFound=True, Hotkey=-1, Rotation=dict(x=0, y=0, z=0), Position=dict(x=0, y=0, z=0),
                                 BlendShapes=[dict(k=k, v=v) for k, v in (blends or {}).items()])
                    frame.update(kw)
                    fixture.stdin.write(json.dumps(frame) + '\n'); fixture.stdin.flush()

                with sync_playwright() as pw:
                    browser = pw.chromium.launch(executable_path=shutil.which('chromium'), args=[
                        '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])
                    page = browser.new_page(viewport=dict(width=1400, height=1000))
                    errors = []; page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(url)
                    page.wait_for_function("document.getElementById('state').textContent.includes('IPを入力')")
                    page.fill('#ip', 'not-an-ip'); page.click('#save')
                    page.wait_for_function("document.getElementById('message').textContent.includes('IPv4')")
                    page.fill('#ip', '127.0.0.1'); page.click('#save')
                    page.wait_for_function("document.getElementById('state').textContent.includes('顔を検出')")
                    self.assertEqual(json.loads(settings.read_text()), dict(iphoneIp='127.0.0.1'))
                    with page.expect_popup() as popup:
                        page.click('#model')
                    model = popup.value
                    model.on('pageerror', lambda error: errors.append(str(error)))
                    model.wait_for_function('window.READY===true && trackingController.found', timeout=60000)
                    model.evaluate('M.stop()')
                    model.keyboard.press('c')
                    send(dict(JawOpen=.8, EyeBlinkLeft=1), Rotation=dict(x=8, y=-4, z=2))
                    model.wait_for_function('M.params.AngleX>3.8 && M.params.AngleY < -7.8 && M.params.MouthOpen>.9')
                    self.assertEqual(model.evaluate('M.params.EyeLOpen'), 0)
                    send(Hotkey=2); model.wait_for_function('M.params.Surprise===1')
                    send(Hotkey=4); model.wait_for_function('trackingController.autoSmile===true')
                    send(dict(MouthSmileLeft=.95, MouthSmileRight=.95))
                    model.wait_for_function('M.params.Smile===1 && M.params.Surprise===0')
                    self.assertIsNone(model.evaluate('window.L2DTracker'))
                    self.assertEqual(model.evaluate("performance.getEntriesByType('resource').filter(e=>/mediapipe|face_landmarker|tracking_webcam/.test(e.name)).length"), 0)
                    model.evaluate('M.render()')
                    output = Path('/workspace/iphone-portable-check'); output.mkdir(exist_ok=True)
                    model.screenshot(path=str(output / 'model.png'))
                    page.screenshot(path=str(output / 'setup.png'))
                    page.click('#stop')
                    page.wait_for_function("document.getElementById('state').textContent.includes('終了しました')")
                    model.wait_for_function('M.params.Smile<.01 && Math.abs(M.params.AngleX)<.1')
                    self.assertEqual(errors, [])
                    browser.close()
            finally:
                fixture.terminate(); fixture.wait(timeout=10)
                fixture.stdin.close(); fixture.stdout.close()


if __name__ == '__main__':
    unittest.main()
