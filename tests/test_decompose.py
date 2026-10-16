"""Regression checks for artist-supplied pixels used beneath moving cutouts."""
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from live2d_ai.decompose import decompose


class ArtistFillTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'skin.png'
        self.rgb = np.full((24, 24, 3), [210, 170, 150], dtype=np.uint8)
        self.alpha = np.ones((24, 24), dtype=np.float32)
        self.specs = [
            {'id': 'skin', 'z': 0, 'zone': None, 'extent': 'all', 'bleed': 0,
             'fill_layer': {'mask': str(self.path)}},
            {'id': 'hair', 'z': 1, 'zone': [[8, 8], [15, 8], [15, 15], [8, 15]], 'bleed': 0},
        ]

    def save_reference(self, opacity=255):
        ref = np.empty((24, 24, 4), dtype=np.uint8)
        ref[..., :3] = [50, 80, 230]  # BGRA: intentionally different from the source
        ref[..., 3] = opacity
        cv2.imwrite(str(self.path), ref)

    def test_reference_fills_occluded_skin_without_replacing_visible_source(self):
        self.save_reference()
        out = decompose(self.rgb, self.alpha, self.specs)
        self.assertTrue(out['skin']['hidden'][11, 11])
        np.testing.assert_allclose(out['skin']['rgb'][11, 11], [230, 80, 50])
        np.testing.assert_array_equal(out['skin']['rgb'][2, 2], self.rgb[2, 2])
        np.testing.assert_array_equal(out['hair']['rgb'][11, 11], self.rgb[11, 11])

    def test_reference_alpha_blends_without_expanding_the_cutout(self):
        self.save_reference(128)
        out = decompose(self.rgb, self.alpha, self.specs)
        weight = 128 / 255
        expected = np.array([230, 80, 50]) * weight + self.rgb[11, 11] * (1 - weight)
        np.testing.assert_allclose(out['skin']['rgb'][11, 11], expected, atol=0.001)
        base_specs = [{k: v for k, v in s.items() if k != 'fill_layer'} for s in self.specs]
        baseline = decompose(self.rgb, self.alpha, base_specs)
        np.testing.assert_array_equal(out['skin']['alpha'], baseline['skin']['alpha'])

    def test_reference_requires_correct_canvas_and_real_alpha(self):
        for shape in [(12, 12, 4), (24, 24, 3)]:
            with self.subTest(shape=shape):
                cv2.imwrite(str(self.path), np.zeros(shape, dtype=np.uint8))
                with self.assertRaisesRegex(ValueError, 'aligned RGBA'):
                    decompose(self.rgb, self.alpha, self.specs)

    def test_soft_hair_matte_reconstructs_source_over_supplied_skin(self):
        self.save_reference()
        self.rgb[:] = [35, 60, 70]
        self.alpha[:] = 253 / 255  # the supplied cutout is nearly opaque, not 255 everywhere
        mask = np.zeros((24, 24), dtype=np.uint8)
        mask[8:16, 8:16] = 160
        mask_path = self.path.parent / 'hair.png'
        cv2.imwrite(str(mask_path), mask)
        self.specs[1]['zone'] = {'mask': str(mask_path)}
        self.specs[1]['preserve_source'] = True
        out = decompose(self.rgb, self.alpha, self.specs)
        a = out['hair']['alpha'][11, 11]
        composite = out['hair']['rgb'][11, 11] * a + out['skin']['rgb'][11, 11] * (1 - a)
        np.testing.assert_allclose(composite, self.rgb[11, 11], atol=0.001)
        self.assertGreater(a, 160 / 255)  # this dark strand needs more coverage
        self.assertLessEqual(a, 1)
        np.testing.assert_array_equal(out['skin']['rgb'][2, 2], self.rgb[2, 2])

    def test_partial_backing_does_not_retain_a_stationary_cutout_halo(self):
        self.save_reference()
        self.rgb[:] = [30, 40, 90]
        mask = np.zeros((24, 24), dtype=np.uint8)
        mask[8:16, 8:16] = 64
        mask_path = self.path.parent / 'soft-object.png'
        cv2.imwrite(str(mask_path), mask)
        self.specs[0]['fill_layer']['include_partial'] = True
        self.specs[1].update(zone={'mask': str(mask_path)}, preserve_source=True)
        out = decompose(self.rgb, self.alpha, self.specs)
        self.assertFalse(out['skin']['hidden'][11, 11])
        np.testing.assert_array_equal(out['skin']['rgb'][11, 11], [230, 80, 50])
        a = out['hair']['alpha'][11, 11]
        composite = out['hair']['rgb'][11, 11] * a + out['skin']['rgb'][11, 11] * (1 - a)
        np.testing.assert_allclose(composite, self.rgb[11, 11], atol=.001)
        np.testing.assert_array_equal(out['skin']['rgb'][2, 2], self.rgb[2, 2])

    def test_explicit_backing_extension_is_bounded_and_keeps_reference_edge_colour(self):
        self.alpha[:] = 0
        ref = np.zeros((24, 24, 4), np.uint8)
        ref[8:16, 8:16] = [180, 170, 190, 160]
        cv2.imwrite(str(self.path), ref)
        self.specs[0]['fill_layer']['extend_alpha'] = True
        out = decompose(self.rgb, self.alpha, self.specs)
        self.assertAlmostEqual(float(out['skin']['alpha'][11, 11]), 160 / 255)
        self.assertEqual(out['skin']['alpha'][2, 2], 0)
        np.testing.assert_array_equal(out['skin']['rgb'][11, 11], [190, 170, 180])

    def test_backing_extension_does_not_make_intentional_cutout_holes_opaque(self):
        self.save_reference()
        self.specs[0].pop('extent')
        self.specs[0]['fill_layer']['extend_alpha'] = True
        out = decompose(self.rgb, self.alpha, self.specs)
        self.assertEqual(out['skin']['alpha'][11, 11], 0)


if __name__ == '__main__':
    unittest.main()
