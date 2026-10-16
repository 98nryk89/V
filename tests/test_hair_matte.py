"""The refined matte must move the original hair, not leave it on body."""
import unittest
import numpy as np
from tools.refine_cutouts import refine_hair


class HairMatteTest(unittest.TestCase):
    def setUp(self):
        self.alpha = np.zeros((24, 24), np.float32)
        self.artist = np.zeros_like(self.alpha)
        self.face = np.zeros_like(self.alpha)
        self.lab = np.full((24, 24, 3), [150, 128, 122], np.float32)
        self.alpha[5:18, 7:15] = 253 / 255
        self.artist[5:18, 7:15] = .8

    def test_outer_hair_consumes_source_coverage_instead_of_leaving_body_ghost(self):
        refined = refine_hair(self.alpha, self.artist, self.face, self.lab)
        np.testing.assert_allclose(refined[6:17, 8:14], self.alpha[6:17, 8:14])

    def test_thin_connected_strands_survive_but_near_transparent_dust_does_not(self):
        self.alpha[10, 3:7] = .3
        self.artist[10, 3:7] = .25
        self.alpha[1, 1] = .004
        self.artist[1, 1] = .2
        refined = refine_hair(self.alpha, self.artist, self.face, self.lab)
        self.assertGreater(refined[10, 4], .25)
        self.assertEqual(refined[1, 1], 0)

    def test_support_expansion_does_not_turn_visible_skin_into_hair(self):
        self.alpha[5:18, 15:18] = 1
        self.face[:, 15:] = 1
        self.lab[:, 15:, 2] = 138
        refined = refine_hair(self.alpha, self.artist, self.face, self.lab)
        np.testing.assert_array_equal(refined[5:18, 15:18], 0)

    def test_diagonal_single_pixel_strands_remain_connected_to_the_hair_mass(self):
        for y, x in [(2, 4), (3, 5), (4, 6)]:
            self.alpha[y, x] = .3
            self.artist[y, x] = .25
        refined = refine_hair(self.alpha, self.artist, self.face, self.lab)
        self.assertGreater(refined[2, 4], .25)


if __name__ == '__main__':
    unittest.main()
