"""Real-asset checks for hair ownership and clothing exclusions."""
import json
from pathlib import Path
import unittest

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'projects/owl_prince'


class LongHairTest(unittest.TestCase):
    def test_long_hair_contains_dark_roots_and_both_lower_locks(self):
        matte = cv2.imread(str(PROJECT / 'hair_long_alpha.png'), 0)
        for x, y in [(450, 510), (460, 510), (400, 800), (730, 780), (340, 1100), (820, 1200), (230, 1184), (250, 1175), (230, 1245), (260, 1220)]:
            with self.subTest(x=x, y=y):
                self.assertGreater(matte[y, x], 240)

    def test_shirt_lapel_owl_watch_and_chains_are_excluded(self):
        matte = cv2.imread(str(PROJECT / 'hair_long_alpha.png'), 0)
        for x, y in [(510, 750), (720, 985), (330, 550), (890, 900), (470, 1015), (430, 1200)]:
            with self.subTest(x=x, y=y):
                self.assertEqual(matte[y, x], 0)

    def test_one_hair_mask_contains_the_full_locks_without_a_horizontal_split(self):
        long = cv2.imread(str(PROJECT / 'hair_long_alpha.png'), 0)
        complete = cv2.imread(str(PROJECT / 'hair_complete_alpha.png'), 0)
        np.testing.assert_array_equal(complete[long == 255], 255)
        parts = json.loads((PROJECT / 'parts_spec.json').read_text())['parts']
        active = [p for p in parts if p['id'].startswith('hair')]
        self.assertEqual([p['id'] for p in active], ['hair_head', 'hair_under_face', 'hair_tip_L', 'hair_tip_R'])
        self.assertEqual(active[0]['zone'], {'mask': 'hair_detail_alpha.png'})
        self.assertEqual(next(p for p in parts if p['id'] == 'body')['fill_layer'], {'mask': 'collar_underlap.png'})


if __name__ == '__main__':
    unittest.main()
