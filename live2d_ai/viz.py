import numpy as np, cv2

PALETTE = [(230,25,75),(60,180,75),(255,225,25),(0,130,200),(245,130,48),(145,30,180),(70,240,240),(240,50,230),
           (210,245,60),(250,190,212),(0,128,128),(220,190,255),(170,110,40),(255,250,200),(128,0,0),(170,255,195)]

def label_overlay(rgb, visibles, ids, alpha_img=0.55):
    out = rgb.astype(np.float32).copy()
    for i, pid in enumerate(ids):
        c = np.array(PALETTE[i % len(PALETTE)], np.float32)
        v = visibles[pid][..., None]
        out = out * (1 - v * alpha_img) + c * v * alpha_img
    return out.astype(np.uint8)
