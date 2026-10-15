"""Crop + zoom an image with a labelled coordinate grid, so regions can be read off precisely."""
import sys, cv2, numpy as np

def zoom(path, x0, y0, x1, y1, scale=3, step=20, out='zoom.png', bg=None):
    im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if im.shape[2] == 4:
        a = im[..., 3:4].astype(np.float32) / 255
        col = np.array(bg or (200, 160, 255), np.float32)
        im = (im[..., :3] * a + col * (1 - a)).astype(np.uint8)
    c = im[y0:y1, x0:x1]
    c = cv2.resize(c, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    for gx in range((x0 // step + 1) * step, x1, step):
        X = (gx - x0) * scale
        major = gx % (step * 5) == 0
        cv2.line(c, (X, 0), (X, c.shape[0]), (0, 255, 255) if major else (0, 200, 0), 1)
        if major or step >= 20:
            cv2.putText(c, str(gx), (X + 2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
    for gy in range((y0 // step + 1) * step, y1, step):
        Y = (gy - y0) * scale
        major = gy % (step * 5) == 0
        cv2.line(c, (0, Y), (c.shape[1], Y), (0, 255, 255) if major else (0, 200, 0), 1)
        cv2.putText(c, str(gy), (2, Y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)
    cv2.imwrite(out, c)

if __name__ == '__main__':
    p, x0, y0, x1, y1 = sys.argv[1], *map(int, sys.argv[2:6])
    scale = int(sys.argv[6]) if len(sys.argv) > 6 else 3
    step = int(sys.argv[7]) if len(sys.argv) > 7 else 20
    zoom(p, x0, y0, x1, y1, scale, step, sys.argv[8] if len(sys.argv) > 8 else 'zoom.png')
