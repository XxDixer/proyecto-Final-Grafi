import time, math
import numpy as np
import cv2

W, H = 800, 600
FPS = 30
DURATION = 60.0

def clamp01(x):
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)

def smoothstep(a, b, x):
    x = clamp01((x - a) / (b - a))
    return x * x * (3 - 2 * x)

def poly_param(fx, fy, t0, t1, n, cx, cy, sx, sy):
    ts = np.linspace(t0, t1, n, dtype=np.float32)
    xs = fx(ts) * sx + cx
    ys = fy(ts) * sy + cy
    return np.round(np.stack([xs, ys], 1)).astype(np.int32).reshape((-1, 1, 2))

def hsv_to_bgr(h, s, v):
    hsv = np.uint8([[[h % 180, np.clip(s, 0, 255), np.clip(v, 0, 255)]]])
    return tuple(int(x) for x in cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)[0, 0])

def affine_transform_pts(pts, angle=0.0, scale=1.0, tx=0, ty=0, shear=0.0):
    ca, sa = math.cos(angle), math.sin(angle)
    M = np.array([
        [scale * ca + shear * sa, -scale * sa + shear * ca, tx],
        [scale * sa,               scale * ca,               ty]
    ], dtype=np.float32)
    p = pts.reshape(-1, 2).astype(np.float32)
    ones = np.ones((len(p), 1), dtype=np.float32)
    p_h = np.hstack([p, ones])
    transformed = (M @ p_h.T).T
    return transformed.reshape(-1, 1, 2).astype(np.int32)

def post_vignette(img, strength=0.7):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    nx = (xx - W * 0.5) / (W * 0.5)
    ny = (yy - H * 0.5) / (H * 0.5)
    r2 = nx * nx + ny * ny
    mask = np.clip(1.0 - strength * r2, 0.0, 1.0)
    return (img.astype(np.float32) * mask[..., None]).astype(np.uint8)

def post_scanlines(img, strength=0.22):
    out = img.astype(np.float32)
    y = np.arange(H, dtype=np.float32)
    m = 1.0 - strength * (0.5 + 0.5 * np.sin(2 * np.pi * y / 3.0))
    out *= m[:, None, None]
    return np.clip(out, 0, 255).astype(np.uint8)

def post_posterize(img, q=32):
    q = max(1, int(q))
    return ((img // q) * q).astype(np.uint8)

def post_chromatic_aberration(img, shift=3):
    result = img.copy()
    result[:, shift:, 2] = img[:, :-shift, 2]
    result[:, :-shift, 0] = img[:, shift:, 0]
    return result

def background_hsv_gradient(img, t, hue0=10, hue1=140):
    hsv = np.zeros((H, W, 3), np.uint8)
    ys = np.linspace(0, 1, H, dtype=np.float32)
    hue = (hue0 + (hue1 - hue0) * ys + 10 * np.sin(t * 0.4 + ys * 2.0)).astype(np.float32)
    hsv[:, :, 0] = np.clip(hue, 0, 179).astype(np.uint8)[:, None]
    hsv[:, :, 1] = 200
    hsv[:, :, 2] = (40 + 120 * (1 - ys)).astype(np.uint8)[:, None]
    img[:] = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

def scene_credits(img, t):
    background_hsv_gradient(img, t, hue0=165, hue1=105)
    rng = np.random.default_rng(1)
    xs = rng.integers(0, W, 380)
    ys = rng.integers(0, int(H * 0.65), 380)
    img[ys, xs] = (255, 255, 255)
    img[:] = cv2.GaussianBlur(img, (0, 0), 0.6)
    pulse = 0.85 + 0.15 * math.sin(t * 3.0)
    col = (int(245 * pulse), int(245 * pulse), int(245 * pulse))
    cv2.putText(img, "DEMO PROCEDURAL", (80, 230), cv2.FONT_HERSHEY_SIMPLEX, 1.2, col, 2, cv2.LINE_AA)
    cv2.putText(img, "Graficacion  OpenCV + NumPy", (80, 285), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (200, 200, 220), 2, cv2.LINE_AA)
    cv2.putText(img, "Enero - Junio 2026", (80, 340), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (160, 160, 180), 1, cv2.LINE_AA)
    spiral_n = 300
    for i in range(spiral_n):
        angle = i * 0.15 + t * 0.8
        r = i * 0.55
        x = int(W * 0.88 + r * math.cos(angle))
        y = int(H * 0.2 + r * math.sin(angle))
        if 0 <= x < W and 0 <= y < H:
            c = hsv_to_bgr(int((angle * 30 + t * 20) % 180), 200, 200)
            cv2.circle(img, (x, y), 1, c, -1)

def scene_lissajous(img, t):
    background_hsv_gradient(img, t, hue0=18, hue1=60)
    a = 3 + 0.7 * math.sin(t * 0.6)
    b = 2 + 0.7 * math.cos(t * 0.8)
    delta = math.pi / 2 + 0.4 * math.sin(t * 0.3)
    fx = lambda x: np.sin(a * x + delta)
    fy = lambda x: np.sin(b * x)
    pts = poly_param(fx, fy, 0, 2 * math.pi, 900, W * 0.5, H * 0.45, 260, 180)
    col = hsv_to_bgr(int(20 + 30 * np.sin(t * 0.8)), 210, 240)
    cv2.polylines(img, [pts], False, col, 2, cv2.LINE_AA)
    a2 = 5 + math.sin(t * 0.4)
    b2 = 4 + math.cos(t * 0.5)
    pts2 = poly_param(fx=lambda x: np.sin(a2 * x + t * 0.5),
                      fy=lambda x: np.sin(b2 * x),
                      t0=0, t1=2 * math.pi, n=700,
                      cx=W * 0.5, cy=H * 0.45, sx=80, sy=55)
    col2 = hsv_to_bgr(int(50 + 20 * math.sin(t * 1.2)), 180, 220)
    cv2.polylines(img, [pts2], False, col2, 1, cv2.LINE_AA)
    cv2.putText(img, f"Lissajous  a={a:.1f} b={b:.1f}", (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 180), 1, cv2.LINE_AA)

def scene_rose_polar(img, t):
    background_hsv_gradient(img, t, hue0=120, hue1=165)
    k = 5
    theta0 = t * 0.6
    fx = lambda th: np.cos(k * th) * np.cos(th + theta0)
    fy = lambda th: np.cos(k * th) * np.sin(th + theta0)
    pts = poly_param(fx, fy, 0, 2 * math.pi, 1200, W * 0.5, H * 0.45, 240, 240)
    col = hsv_to_bgr(int(145 + 25 * np.sin(t * 0.5)), 220, 245)
    cv2.polylines(img, [pts], False, col, 2, cv2.LINE_AA)
    for i in range(6):
        r = int(18 + 10 * np.sin(t * 2.0 + i))
        cv2.circle(img, (int(W * 0.18 + i * 110), int(H * 0.78)), max(1, r), (230, 230, 230), 1, cv2.LINE_AA)
    k2 = 7
    pts2 = poly_param(fx=lambda th: np.cos(k2 * th) * np.cos(th - theta0 * 0.7),
                      fy=lambda th: np.cos(k2 * th) * np.sin(th - theta0 * 0.7),
                      t0=0, t1=2 * math.pi, n=1400,
                      cx=W * 0.5, cy=H * 0.45, sx=100, sy=100)
    col2 = hsv_to_bgr(int(160 + 15 * math.sin(t * 0.9)), 180, 180)
    cv2.polylines(img, [pts2], False, col2, 1, cv2.LINE_AA)
    cv2.putText(img, "Rosa polar  r = cos(k*theta)", (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 240, 200), 1, cv2.LINE_AA)

def scene_transformations(img, t):
    background_hsv_gradient(img, t, hue0=200, hue1=140)
    star_n = 8
    angles_base = np.linspace(0, 2 * math.pi, star_n * 2, endpoint=False)
    radii = np.array([1.0 if i % 2 == 0 else 0.45 for i in range(star_n * 2)])
    star_xs = np.cos(angles_base) * radii * 80
    star_ys = np.sin(angles_base) * radii * 80
    star_pts_base = np.stack([star_xs, star_ys], axis=1).reshape(-1, 1, 2).astype(np.float32)
    angle_rot = t * 1.2
    scale_v = 1.0 + 0.4 * math.sin(t * 1.8)
    shear_v = 0.3 * math.sin(t * 0.9)
    cx, cy = W * 0.25, H * 0.45
    pts1 = affine_transform_pts(star_pts_base, angle=angle_rot, scale=scale_v, tx=cx, ty=cy)
    col1 = hsv_to_bgr(int(140 + 20 * math.sin(t)), 220, 240)
    cv2.fillPoly(img, [pts1], col1)
    cx2, cy2 = W * 0.5, H * 0.45
    pts2 = affine_transform_pts(star_pts_base, angle=-angle_rot * 0.7, scale=1.0,
                                 tx=cx2, ty=cy2, shear=shear_v)
    col2 = hsv_to_bgr(int(20 + 20 * math.sin(t * 0.7)), 210, 230)
    cv2.polylines(img, [pts2], True, col2, 2, cv2.LINE_AA)
    cx3, cy3 = W * 0.75, H * 0.45
    mirror_pts = star_pts_base.copy()
    mirror_pts[:, :, 0] *= -1
    pts3 = affine_transform_pts(mirror_pts, angle=angle_rot * 0.5, scale=scale_v * 0.8,
                                 tx=cx3, ty=cy3)
    col3 = hsv_to_bgr(int(80 + 20 * math.cos(t * 1.1)), 200, 220)
    cv2.fillPoly(img, [pts3], col3)
    cv2.putText(img, "Rotacion  Escala  Shear  Espejo", (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 220, 255), 1, cv2.LINE_AA)
    for label, px in [("Rotacion+Escala", int(W*0.18)), ("Shear", int(W*0.47)), ("Espejo", int(W*0.71))]:
        cv2.putText(img, label, (px, int(H * 0.82)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 200), 1, cv2.LINE_AA)

def scene_spirograph(img, t):
    background_hsv_gradient(img, t, hue0=80, hue1=20)
    R, r, d = 8.0, 3.0, 5.0
    w = (R - r) / r
    fx = lambda x: (R - r) * np.cos(x) + d * np.cos(w * x + 0.4 * np.sin(t * 0.7))
    fy = lambda x: (R - r) * np.sin(x) - d * np.sin(w * x + 0.4 * np.cos(t * 0.6))
    pts = poly_param(fx, fy, 0, 14 * math.pi, 1600, W * 0.5, H * 0.46, 26, 26)
    col = hsv_to_bgr(int(10 + 140 * (0.5 + 0.5 * np.sin(t * 0.4))), 240, 240)
    cv2.polylines(img, [pts], False, col, 2, cv2.LINE_AA)
    R2, r2, d2 = 7.0, 2.0, 6.0
    w2 = (R2 - r2) / r2
    offset = t * 0.3
    fx2 = lambda x: (R2 - r2) * np.cos(x + offset) + d2 * np.cos(w2 * x + offset)
    fy2 = lambda x: (R2 - r2) * np.sin(x + offset) - d2 * np.sin(w2 * x + offset)
    pts2 = poly_param(fx2, fy2, 0, 10 * math.pi, 1200, W * 0.5, H * 0.46, 30, 30)
    col2 = hsv_to_bgr(int(50 + 80 * math.sin(t * 0.6)), 200, 200)
    cv2.polylines(img, [pts2], False, col2, 1, cv2.LINE_AA)
    img[:] = post_scanlines(img, 0.18)
    cv2.putText(img, "Hipotrocoide (Spirograph)", (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 200, 100), 1, cv2.LINE_AA)

def scene_fire(img, t, state):
    heat = state["heat"]
    rng = state["rng"]
    heat[:] = (heat * 0.93).astype(np.float32)
    base_n = 1400
    xs = rng.integers(0, W, base_n)
    ys = rng.integers(int(H * 0.82), H, base_n)
    heat[ys, xs] += rng.random(base_n) * (0.8 + 0.6 * (0.5 + 0.5 * math.sin(t * 2.0)))
    heat[:] = cv2.GaussianBlur(heat, (0, 0), 2.2)
    heat[:-2, :] = heat[2:, :]
    heat[-2:, :] *= 0.0
    h_ch = (20 - 20 * np.clip(heat, 0, 1)).astype(np.uint8)
    s_ch = (220 - 80 * np.clip(heat, 0, 1)).astype(np.uint8)
    v_ch = (60 + 195 * np.clip(heat, 0, 1)).astype(np.uint8)
    hsv = np.dstack([h_ch, s_ch, v_ch]).astype(np.uint8)
    img[:] = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    cv2.rectangle(img, (0, int(H * 0.83)), (W, H), (10, 10, 10), -1)
    sparks = 160
    sx = rng.integers(0, W, sparks)
    sy = rng.integers(int(H * 0.55), int(H * 0.9), sparks)
    img[sy, sx] = (255, 255, 255)
    img[:] = cv2.GaussianBlur(img, (0, 0), 0.6)
    cv2.putText(img, "Fuego procedural  (heatmap HSV)", (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (240, 200, 80), 1, cv2.LINE_AA)

SCENE_NAMES = [
    "Credits",
    "Lissajous",
    "Rosa Polar",
    "Transformaciones",
    "Spirograph",
    "Fuego Procedural",
]

def render_scene(buf, scene_id, t, rng, fire_state):
    if scene_id == 0:
        scene_credits(buf, t)
    elif scene_id == 1:
        scene_lissajous(buf, t)
    elif scene_id == 2:
        scene_rose_polar(buf, t)
    elif scene_id == 3:
        scene_transformations(buf, t)
    elif scene_id == 4:
        scene_spirograph(buf, t)
    else:
        scene_fire(buf, t, fire_state)

def timeline(t, rng, bufA, bufB, fire_state):
    block = int(min(5, max(0, t // 10)))
    t_in = t - block * 10
    render_scene(bufA, block, t, rng, fire_state)
    frame = bufA
    if block < 5 and t_in >= 8.8:
        render_scene(bufA, block, t, rng, fire_state)
        render_scene(bufB, block + 1, t, rng, fire_state)
        a = smoothstep(8.8, 10.0, t_in)
        frame = cv2.addWeighted(bufA, 1 - a, bufB, a, 0)
        flash = smoothstep(9.6, 10.0, t_in)
        if flash > 0:
            frame = cv2.addWeighted(frame, 1.0, np.full_like(frame, 255), 0.12 * flash, 0)
    fin = smoothstep(0.0, 1.5, t)
    fout = 1.0 - smoothstep(DURATION - 1.5, DURATION, t)
    f = fin * fout
    if f < 0.999:
        frame = (frame.astype(np.float32) * f).astype(np.uint8)
    return frame

def main():
    import os
    os.makedirs("renders", exist_ok=True)

    rng = np.random.default_rng(123)
    bufA = np.zeros((H, W, 3), np.uint8)
    bufB = np.zeros((H, W, 3), np.uint8)
    fire_state = {
        "heat": np.zeros((H, W), np.float32),
        "rng": np.random.default_rng(999),
    }

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter("renders/demo_final.mp4", fourcc, FPS, (W, H))

    total_frames = int(DURATION * FPS)
    saved_scenes = set()
    t0 = time.perf_counter()

    for i in range(total_frames):
        t = i / FPS
        frame = timeline(t, rng, bufA, bufB, fire_state)
        frame = post_vignette(frame, 0.72)
        frame = post_scanlines(frame, 0.16)
        frame = post_posterize(frame, 24)
        frame = post_chromatic_aberration(frame, shift=2)

        block = int(min(5, max(0, t // 10)))
        capture_t = block * 10 + 2.0
        if block not in saved_scenes and t >= capture_t:
            cv2.imwrite(f"renders/escena_{block}_{SCENE_NAMES[block].replace(' ', '_')}.png", frame)
            saved_scenes.add(block)

        writer.write(frame)
        cv2.imshow("Demo Procedural  (ESC para salir)", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break

    writer.release()
    cv2.destroyAllWindows()
    print(f"Tiempo total: {time.perf_counter() - t0:.1f}s")
    print("Video guardado en: C:\Users\diego\OneDrive\Desktop\Proyecto Final\renders")
    print("Capturas guardadas en: renders/")

if __name__ == "__main__":
    main()
    