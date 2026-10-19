"""Asset regressions for accessory/hair separation and a complete moving tassel."""
from pathlib import Path
import json
import unittest
import cv2
import numpy as np
from scipy import ndimage as ndi

P=Path(__file__).resolve().parents[1]/'projects/owl_prince'


class CostumeTest(unittest.TestCase):
    def test_shoulder_hair_is_not_part_of_either_mask_accessory(self):
        for name in ['ribbon_only_alpha','orn_chain_only_alpha']:
            mask=cv2.imread(str(P/(name+'.png')),0)
            for x,y in [(747,640),(760,638),(745,619),(740,590),(725,490)]:
                with self.subTest(name=name,x=x,y=y):
                    self.assertEqual(mask[y,x],0)
        chain=cv2.imread(str(P/'orn_chain_only_alpha.png'),0)
        self.assertGreater(chain[580,775],240)

    def test_tassel_has_a_connected_skirt_and_a_complete_hem(self):
        tassel=cv2.imread(str(P/'tassel_full.png'),-1)
        labels,_=ndi.label(tassel[...,3]>127)
        # The cap and skirt stay connected; the hem is inside the image, not cut.
        self.assertGreater(labels[280,45],0)
        self.assertEqual(labels[280,45],labels[520,45])
        self.assertFalse(np.any(tassel[-3:,:,3]))
        self.assertFalse(np.any(tassel[:,0,3]))
        self.assertFalse(np.any(tassel[:,-1,3]))
        spec=json.loads((P/'parts_spec.json').read_text())
        self.assertEqual(spec['frame_extension']['attachments'][0]['id'],'hangR3')
