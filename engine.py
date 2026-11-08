# mugiwe-drawing engine — "LLM authors stroke data; the engine simulates the pen."
# Stroke data (JSON): {"brush": {"size": px, "ink": [r,g,b], "tone": 0..1, "load": 0..1.5},
#                      "points": [[x, y, pressure, speed, dwell], ...]}
# Physics (simplified sho-like): width ~ pressure x size; ink depletes with
# distance x speed; fast+dry -> kasure gaps; dwell/low speed -> ink pooling;
# deterministic per-stroke jitter (seeded by stroke index + a global seed).
import json, math, random, sys
from PIL import Image, ImageDraw

W, H = 1200, 800

def catmull(points, samples=16):
    pts = [points[0]] + points + [points[-1]]
    out = []
    for i in range(len(pts) - 3):
        p = [pts[i], pts[i+1], pts[i+2], pts[i+3]]
        for j in range(samples):
            t = j / samples; t2, t3 = t*t, t*t*t
            out.append([0.5*((2*p[1][k]) + (-p[0][k]+p[2][k])*t + (2*p[0][k]-5*p[1][k]+4*p[2][k]-p[3][k])*t2 + (-p[0][k]+3*p[1][k]-3*p[2][k]+p[3][k])*t3) for k in range(5)])
    out.append(points[-1])
    return out

def paper():
    img = Image.new('RGB', (W, H), (247, 241, 226))
    rnd = random.Random(42)
    px = img.load()
    for _ in range(2600):
        x, y = rnd.randrange(W), rnd.randrange(H)
        d = rnd.choice([-6, -4, 4, 6])
        r, g, b = px[x, y]
        px[x, y] = (max(0, min(255, r+d)), max(0, min(255, g+d)), max(0, min(255, b+d)))
    return img

def render(doc, path):
    img = paper()
    dr = ImageDraw.Draw(img, 'RGBA')
    for si, st in enumerate(doc['strokes']):
        br = st['brush']; size = br.get('size', 16)
        ink_rgb = tuple(br.get('ink', [96, 64, 40])); tone = br.get('tone', 1.0); load = br.get('load', 1.0)
        rnd = random.Random(doc.get('seed', 7) * 10000 + si)
        pts = catmull([list(map(float, p)) for p in st['points']])
        ink = load
        for i in range(len(pts) - 1):
            x0, y0, pr0, sp0, dw0 = pts[i]
            x1, y1, pr, sp, dw = pts[i+1]
            seg = math.hypot(x1-x0, y1-y0)
            ink = max(0.18, ink - seg * 0.00038 * sp / max(load, 0.2))
            w = max(1.0, size * pr)
            dry = (sp - 1.15) * 0.30 + (1.0 - min(ink, 1.0)) * 0.55
            if rnd.random() < dry * 0.8:
                continue
            jx, jy = rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6)
            alpha = int(240 * tone * min(1.0, ink * 0.75 + 0.35))
            r = w / 2
            dr.line([x0+jx, y0+jy, x1+jx, y1+jy], fill=ink_rgb + (alpha,), width=int(w))
            dr.ellipse([x1-r+jx, y1-r+jy, x1+r+jx, y1+r+jy], fill=ink_rgb + (alpha,))
            # pooling: dwell or slow movement lets ink gather and round out
            pool = dw * 1.6 + max(0.0, 0.45 - sp) * 0.35
            if pool > 0.12:
                pr_r = r * (1.0 + pool)
                dr.ellipse([x1-pr_r+jx, y1-pr_r+jy, x1+pr_r+jx, y1+pr_r+jy],
                           fill=ink_rgb + (min(255, int(alpha * (0.55 + pool * 0.4))),))
    img.save(path, 'WEBP', quality=90)
    print('saved', path)

if __name__ == '__main__':
    doc = json.load(open(sys.argv[1], encoding='utf-8'))
    render(doc, sys.argv[2])
