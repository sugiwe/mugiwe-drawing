# mugiwe-drawing engine v3 — stroke data in, pen physics out. "tool" per brush simulates the writing instrument.
# Tools: brush (毛筆, v2 behaviour), brushpen (筆ペン: firmer, narrower width range),
# fountain (万年筆: gentle swell, steady flow), calligraphy (flat nib: width follows
# stroke direction vs nib angle), pencil (鉛筆: graphite particles, pressure -> darkness),
# felt (フェルト/サインペン: near-constant width, dwell pooling, slight bleed).
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
        br = st['brush']
        tool = br.get('tool', 'brush')
        size = br.get('size', 16)
        ink_rgb = tuple(br.get('ink', [96, 64, 40]))
        tone = br.get('tone', 1.0); load = br.get('load', 1.0)
        nib = math.radians(br.get('nib_angle', -30))
        rnd = random.Random(doc.get('seed', 7) * 10000 + si)
        pts = catmull([list(map(float, p)) for p in st['points']])
        ink = load
        for i in range(len(pts) - 1):
            x0, y0, pr0, sp0, dw0 = pts[i]
            x1, y1, pr, sp, dw = pts[i+1]
            seg = math.hypot(x1-x0, y1-y0)
            if seg == 0: continue
            theta = math.atan2(y1-y0, x1-x0)
            jx, jy = rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6)
            if tool in ('pencil', 'colorpencil'):
                w = size * (0.55 + 0.75 * pr)
                steps = max(1, int(seg / 2.5))
                for s in range(steps):
                    t = s / steps
                    cx, cy = x0 + (x1-x0)*t + jx, y0 + (y1-y0)*t + jy
                    density = int(10 + 16 * pr)
                    for _ in range(density):
                        ang = rnd.uniform(0, 6.283); rad = abs(rnd.gauss(0, w/3.4))
                        px_, py_ = cx + rad*math.cos(ang), cy + rad*math.sin(ang)
                        a = int(rnd.uniform(28, 105) * tone * (0.45 + 0.55*pr))
                        rr = rnd.uniform(0.7, 1.7)
                        col = ink_rgb
                        if tool == 'colorpencil':
                            f = rnd.uniform(0.90, 1.10)
                            col = tuple(max(0, min(255, int(c*f))) for c in ink_rgb)
                            if rnd.random() < 0.10:  # paper tooth: a few pale grains
                                col = tuple(int(c*0.6 + p*0.4) for c, p in zip(col, (247, 241, 226)))
                            rr = rnd.uniform(0.9, 2.2)
                        dr.ellipse([px_-rr, py_-rr, px_+rr, py_+rr], fill=col + (a,))
                continue
            # ink depletion / kasure by tool
            if tool in ('brush',):
                ink = max(0.18, ink - seg * 0.00038 * sp / max(load, 0.2))
                dry = (sp - 1.15) * 0.30 + (1.0 - min(ink, 1.0)) * 0.55
                if rnd.random() < dry * 0.8: continue
                w = max(1.0, size * pr)
            elif tool == 'brushpen':
                ink = max(0.3, ink - seg * 0.00016 * sp / max(load, 0.2))
                dry = (sp - 1.5) * 0.22 + (1.0 - min(ink, 1.0)) * 0.35
                if rnd.random() < dry * 0.8: continue
                w = max(1.0, size * (0.38 + 0.72 * pr))
            elif tool == 'fountain':
                w = max(1.0, size * (0.78 + 0.34 * pr))
            elif tool == 'calligraphy':
                f = abs(math.sin(theta - nib))
                w = max(1.2, size * (0.16 + 1.08 * f) * (0.85 + 0.25 * pr))
            elif tool == 'felt':
                w = max(1.0, size * (0.92 + 0.13 * pr))
            else:
                w = max(1.0, size * pr)
            alpha = int(240 * tone * (min(1.0, ink * 0.75 + 0.35) if tool in ('brush', 'brushpen') else 1.0))
            r = w / 2
            if tool == 'felt':  # slight bleed halo
                dr.line([x0+jx, y0+jy, x1+jx, y1+jy], fill=ink_rgb + (int(alpha*0.16),), width=int(w*1.18))
            dr.line([x0+jx, y0+jy, x1+jx, y1+jy], fill=ink_rgb + (alpha,), width=int(w))
            dr.ellipse([x1-r+jx, y1-r+jy, x1+r+jx, y1+r+jy], fill=ink_rgb + (alpha,))
            pool = 0.0
            if tool in ('brush', 'brushpen'):
                pool = dw * 1.6 + max(0.0, 0.45 - sp) * 0.35
            elif tool == 'fountain':
                pool = dw * 0.9 + max(0.0, 0.35 - sp) * 0.2
            elif tool == 'felt':
                pool = dw * 0.8
            if pool > 0.12:
                pr_r = r * (1.0 + pool * (0.8 if tool == 'felt' else 1.0))
                dr.ellipse([x1-pr_r+jx, y1-pr_r+jy, x1+pr_r+jx, y1+pr_r+jy],
                           fill=ink_rgb + (min(255, int(alpha * (0.55 + pool * 0.4))),))
    img.save(path, 'WEBP', quality=90)
    print('saved', path)

if __name__ == '__main__':
    doc = json.load(open(sys.argv[1], encoding='utf-8'))
    render(doc, sys.argv[2])
