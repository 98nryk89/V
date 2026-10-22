"""Run the actual packaged Node entry point, including replacement of an old running kit."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from urllib.request import urlopen, Request
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
URL='http://127.0.0.1:8765/'

class V5LauncherTest(unittest.TestCase):
    def test_actual_launcher_replaces_old_folder_and_then_new_folder(self):
        for kind,port in [(socket.SOCK_STREAM,8765),(socket.SOCK_DGRAM,11125)]:
            with socket.socket(socket.AF_INET,kind) as sock:
                try:sock.bind(('127.0.0.1',port))
                except OSError:self.skipTest(f'port {port} belongs to an existing process; do not stop it')
        processes=[]
        with tempfile.TemporaryDirectory(prefix='verified launch ') as tmp:
            base=Path(tmp)
            with ZipFile(ROOT/'dist/lunaris_iphone_motion_v4_mac.zip') as z:z.extractall(base/'old')
            with ZipFile(ROOT/'dist/lunaris_iphone_motion_v5_mac.zip') as z:z.extractall(base/'new')
            old=base/'old/Lunaris_MOTION4';new=base/'new/Lunaris_MOTION5';new2=base/'new second folder/Lunaris_MOTION5'
            env={**os.environ,'KAMIKAN_NO_OPEN':'1','KAMIKAN_SETTINGS_FILE':str(base/'settings/connection.json')}
            def launch(folder):
                process=subprocess.Popen(['node',str(folder/'bridge/portable/run.js')],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
                processes.append(process);return process
            def status_until(predicate):
                deadline=time.monotonic()+10
                while time.monotonic()<deadline:
                    try:
                        with urlopen(URL+'api/status',timeout=.5) as response:state=json.load(response)
                        if predicate(state):return state
                    except Exception:pass
                    time.sleep(.05)
                self.fail('packaged launcher did not start the expected distribution')
            try:
                legacy=launch(old);status_until(lambda s:s.get('version')=='4.0.0')
                current=launch(new);state=status_until(lambda s:s.get('version')=='5.0.0')
                self.assertEqual(legacy.wait(timeout=5),0)
                self.assertEqual(state['modelVersion'],'MOTION-5')
                with urlopen(URL+state['modelFile']) as response:self.assertEqual(response.read(),(ROOT/'dist/owl_prince_iphone_motion_v5.html').read_bytes())
                same=launch(new);self.assertEqual(same.wait(timeout=5),0)
                self.assertIsNone(current.poll())
                shutil.copytree(new,new2)
                replacement=launch(new2)
                second=status_until(lambda s:s.get('instanceKey') and s['instanceKey']!=state['instanceKey'])
                self.assertEqual(second['modelSha256'],state['modelSha256'])
                self.assertEqual(current.wait(timeout=5),0)
                request=Request(URL+'api/stop',data=b'{}',headers={'Origin':URL.rstrip('/'),'Content-Type':'application/json'})
                with urlopen(request) as response:self.assertEqual(response.status,200)
                self.assertEqual(replacement.wait(timeout=5),0)
                # Packaged metadata also rejects a mismatched model before binding any port.
                with (new2/'html/owl_prince_iphone_motion_v5.html').open('a') as stream:stream.write('tampered')
                broken=launch(new2);self.assertEqual(broken.wait(timeout=5),1)
                self.assertIn('配布版と一致しません',broken.stdout.read())
            finally:
                for process in processes:
                    if process.poll() is None:process.terminate();process.wait(timeout=5)
                    process.stdout.close()

if __name__=='__main__':unittest.main()
