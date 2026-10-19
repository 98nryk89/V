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
        ribbon=cv2.imread(str(P/'ribbon_only_alpha.png'),0)
        for x,y in [(735,550),(734,570),(735,572),(734,574)]:
            self.assertGreater(ribbon[y,x],240)  # dark cloth rim moves with cloth
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

    def test_ribbon_does_not_have_a_reconstructed_hair_backing(self):
        rig=json.loads((P/'out/rig.json').read_text())
        part=next(p for p in rig['parts'] if p['id']=='hair_head')
        image=cv2.imread(str(P/'out'/part['tex']),-1)
        ox,oy,_,_=part['bbox']
        for x,y in [(800,400),(755,545)]:
            self.assertEqual(image[y-oy,x-ox,3],0)
        self.assertGreater(image[590-oy,740-ox,3],240)  # real adjacent hair stays
        # The strand under the lowest fold must remain connected when it swings.
        hsv=cv2.cvtColor(image[...,:3],cv2.COLOR_BGR2HSV)
        for x,y in [(738,553),(740,560),(742,566),(735,550),(734,570),(735,572),(734,574)]:
            with self.subTest(tip_hair=(x,y)):
                self.assertGreater(image[y-oy,x-ox,3],240)
                self.assertLess(hsv[y-oy,x-ox,1],60)  # silver, not purple cloth

    def test_hidden_tassel_backing_is_cloth_and_preserves_the_collar(self):
        backing=cv2.imread(str(P/'costume_body_backing.png'),-1)
        collar=cv2.imread(str(P/'collar_underlap.png'),-1)
        np.testing.assert_array_equal(backing[:800],collar[:800])
        lab=cv2.cvtColor(backing[...,:3],cv2.COLOR_BGR2LAB)
        for x,y in [(976,1000),(960,1250),(1040,1300)]:
            self.assertEqual(backing[y,x,3],255)
            self.assertLess(lab[y,x,0],135)
