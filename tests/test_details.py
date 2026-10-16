"""Small source-pixel ownership corrections and a bounded owl eyelid."""
from pathlib import Path
import unittest
import cv2
import numpy as np
from live2d_ai.synth import owl_lid

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / 'projects/owl_prince'


class DetailTest(unittest.TestCase):
    def test_brow_strokes_and_black_collar_are_no_longer_hair(self):
        before = cv2.imread(str(P / 'hair_complete_alpha.png'), 0)
        after = cv2.imread(str(P / 'hair_detail_alpha.png'), 0)
        for x, y in [(460, 348), (480, 349), (620, 343), (480, 605)]:
            with self.subTest(x=x, y=y):
                self.assertGreater(before[y, x], 240)
                self.assertEqual(after[y, x], 0)
        self.assertEqual(after[800, 400], before[800, 400])

    def test_only_two_small_existing_tips_are_split_out(self):
        original = cv2.imread(str(P / 'hair_complete_alpha.png'), 0)
        extent = cv2.imread(str(P / 'hair_detail_extent.png'), 0)
        for side in ['L', 'R']:
            tip = cv2.imread(str(P / f'hair_tip_{side}_alpha.png'), 0) > 0
            self.assertGreater(tip.sum(), 100)
            self.assertLess(tip.sum(), (original > 0).sum() * .015)
            self.assertTrue(np.all(original[tip] > 25))
            # A hidden duplicate with the same silhouette would leave a ghost.
            self.assertTrue(np.all(extent[tip] == 0))
            self.assertFalse(tip[750, 510])  # shirt
            self.assertFalse(tip[900, 890])  # watch

    def test_owl_lid_covers_iris_and_never_touches_beak_or_body(self):
        import json
        src = cv2.imread(str(ROOT / 'samples/ref12.png'))[..., ::-1].copy()
        parts = json.loads((P / 'parts_spec.json').read_text())['parts']
        for part, centre in [('owl_lid_L', (270, 564)), ('owl_lid_R', (334, 548))]:
            s = next(p['synthetic'] for p in parts if p['id'] == part)
            rgb, a = owl_lid(src.shape[:2], s, src)
            x, y = centre
            self.assertGreater(a[y, x], .99)
            self.assertGreater(rgb[y, x].mean(), 140)  # feather, no blue pupil
            self.assertLess(a[575, 315], .001)  # beak
            self.assertLess(a[750, 510], .001)  # shirt
            self.assertLess(a[490, 425], .001)  # human earring


if __name__ == '__main__':
    unittest.main()
