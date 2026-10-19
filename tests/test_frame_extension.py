"""An external costume layer must keep old coordinates and inner artwork intact."""
import copy
import tempfile
from pathlib import Path
import unittest

import cv2
import numpy as np

from live2d_ai.build import extend_frame


class FrameExtensionTest(unittest.TestCase):
    def test_extension_keeps_inner_pixels_and_geometry_and_feathers_crop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'parts').mkdir()
            original = np.full((20, 20, 4), [30, 60, 90, 255], np.uint8)
            cv2.imwrite(str(root / 'parts/body.png'), original)
            extension = np.full((30, 40, 4), [100, 80, 60, 255], np.uint8)
            cv2.imwrite(str(root / 'wide.png'), extension)
            part = dict(id='body', tex='parts/body.png', bbox=[0,0,20,20],
                        mesh={'verts':[0,0,20,20]}, effects=[])
            rig = dict(size=[20,20], parts=[part])
            before = copy.deepcopy(part)
            effects = [{'type':'translate', 'param':'BodyX', 'map':[[-1,-90,0],[1,90,0]]}]
            extend_frame(rig, directory, directory,
                         dict(image='wide.png', origin=[-10,-3], blend=4), effects)
            self.assertEqual(part, before)
            baked = cv2.imread(str(root / 'parts/body.png'), -1)
            np.testing.assert_array_equal(baked[0:15,4:16], original[0:15,4:16])
            np.testing.assert_array_equal(baked[...,:3], original[...,:3])
            self.assertEqual(baked[10,0,3], 0)
            self.assertGreater(baked[10,2,3], 0)
            self.assertLess(baked[10,2,3], 255)
            self.assertEqual(baked[-1,10,3], 0)
            added = rig['parts'][-1]
            self.assertEqual(added['bbox'], [-10,-3,40,30])
            self.assertEqual(added['effects'], effects)
            self.assertEqual(added['z'], -1)
            vertices = np.array(added['mesh']['verts']).reshape(-1,2)
            self.assertEqual(vertices[:,0].min(), -10)
            self.assertEqual(vertices[:,0].max(), 30)
            np.testing.assert_array_equal(cv2.imread(str(root / added['tex']),-1), extension)

    def test_extension_requires_real_transparency(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cv2.imwrite(str(root / 'rgb.png'), np.zeros((4,4,3), np.uint8))
            with self.assertRaisesRegex(ValueError, 'RGBA'):
                extend_frame(dict(size=[4,4], parts=[]), directory, directory,
                             dict(image='rgb.png', origin=[0,0]), [])
