# -*- coding: utf-8 -*-
"""앱 아이콘 생성기. 실행하면 icon.ico / icon_preview.png 를 만든다."""
import os
from PIL import Image, ImageDraw, ImageFont

S = 1024                      # 작업 해상도 (마지막에 축소)
BG_TOP = (26, 31, 46)
BG_BOT = (13, 15, 21)
GOLD = (255, 210, 63)
GOLD_DARK = (214, 168, 20)
CARD_L = (86, 122, 196)
CARD_R = (214, 92, 124)
INK = (20, 22, 30)


def font(size, bold=True):
    for name in (("malgunbd.ttf", "arialbd.ttf") if bold else ("malgun.ttf", "arial.ttf")):
        p = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", name)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def rounded(size, radius, fill):
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius, fill=fill)
    return im


def card(w, h, base):
    """사진 카드 한 장: 테두리 + 안쪽 사진 느낌의 그라데이션 + 인물 실루엣."""
    im = rounded((w, h), int(w * 0.13), (245, 246, 250, 255))
    pad = int(w * 0.075)
    inner = Image.new("RGBA", (w - pad * 2, h - pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(inner)
    iw, ih = inner.size
    for y in range(ih):                                    # 세로 그라데이션
        t = y / max(ih - 1, 1)
        d.line([(0, y), (iw, y)],
               fill=tuple(int(base[i] + (255 - base[i]) * 0.45 * (1 - t)) for i in range(3)) + (255,))
    # 인물 실루엣 (머리 + 어깨)
    sil = tuple(int(c * 0.55) for c in base) + (255,)
    hr = iw * 0.22
    cx, cy = iw / 2, ih * 0.42
    d.ellipse([cx - hr, cy - hr, cx + hr, cy + hr], fill=sil)
    d.ellipse([cx - iw * 0.40, cy + hr * 0.55, cx + iw * 0.40, cy + hr * 0.55 + ih * 0.72], fill=sil)

    mask = rounded(inner.size, int(w * 0.075), (255, 255, 255, 255))
    im.paste(inner, (pad, pad), mask)
    return im


def build_small(size):
    """16/24px용 단순화 버전. 왕관·실루엣·글자를 빼고 색 대비만 남긴다."""
    W = 256
    im = rounded((W, W), int(W * 0.22), BG_BOT + (255,))
    d = ImageDraw.Draw(im)
    m, g = int(W * 0.11), int(W * 0.035)
    cw = (W - m * 2 - g) // 2
    d.rounded_rectangle([m, m + int(W * 0.03), m + cw, W - m - int(W * 0.03)],
                        int(W * 0.07), fill=CARD_L)
    d.rounded_rectangle([m + cw + g, m + int(W * 0.03), m + cw * 2 + g, W - m - int(W * 0.03)],
                        int(W * 0.07), fill=CARD_R)
    r = int(W * 0.20)
    cx, cy = W // 2, W // 2
    d.ellipse([cx - r - int(W * 0.035), cy - r - int(W * 0.035),
               cx + r + int(W * 0.035), cy + r + int(W * 0.035)], fill=BG_BOT + (255,))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GOLD)
    return im.resize((size, size), Image.LANCZOS)


def build():
    # 배경
    bg = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    grad = Image.new("RGBA", (S, S))
    gd = ImageDraw.Draw(grad)
    for y in range(S):
        t = y / (S - 1)
        gd.line([(0, y), (S, y)],
                fill=tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * t) for i in range(3)) + (255,))
    bg.paste(grad, (0, 0), rounded((S, S), int(S * 0.22), (255, 255, 255, 255)))

    # 좌우 카드 (안쪽으로 살짝 기울여 마주 보게)
    cw, ch = int(S * 0.42), int(S * 0.58)
    left = card(cw, ch, CARD_L).rotate(7, Image.BICUBIC, expand=True)
    right = card(cw, ch, CARD_R).rotate(-7, Image.BICUBIC, expand=True)
    y = int(S * 0.235)
    bg.alpha_composite(left, (int(S * 0.055), y))
    bg.alpha_composite(right, (int(S * 0.945) - right.width, y))

    # 중앙 VS 배지
    r = int(S * 0.165)
    cx, cy = S // 2, int(S * 0.575)
    d = ImageDraw.Draw(bg)
    d.ellipse([cx - r - int(S * 0.022), cy - r - int(S * 0.022),
               cx + r + int(S * 0.022), cy + r + int(S * 0.022)], fill=(13, 15, 21, 255))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GOLD, outline=GOLD_DARK, width=int(S * 0.008))
    f = font(int(S * 0.17))
    d.text((cx, cy + int(S * 0.004)), "VS", font=f, fill=INK, anchor="mm")

    # 상단 왕관 (우승 느낌)
    w2, h2 = int(S * 0.20), int(S * 0.115)
    kx, ky = cx - w2 // 2, int(S * 0.095)
    pts = [(kx, ky + h2), (kx, ky + h2 * 0.15), (kx + w2 * 0.25, ky + h2 * 0.62),
           (kx + w2 * 0.5, ky), (kx + w2 * 0.75, ky + h2 * 0.62),
           (kx + w2, ky + h2 * 0.15), (kx + w2, ky + h2)]
    d.polygon(pts, fill=GOLD)
    d.rounded_rectangle([kx, ky + h2 * 0.92, kx + w2, ky + h2 * 1.32], int(S * 0.012), fill=GOLD)

    here = os.path.dirname(os.path.abspath(__file__))
    bg.resize((512, 512), Image.LANCZOS).save(os.path.join(here, "icon_preview.png"))
    # 크기별 이미지를 모두 직접 렌더해서 넘긴다. (Pillow의 ICO 저장은 빠진 크기를
    # 마지막 append_images 기준으로 축소해버려서, 하나라도 비우면 결과가 망가진다.)
    big = [(s, bg.resize((s, s), Image.LANCZOS)) for s in (256, 128, 64, 48, 32)]
    small = [(s, build_small(s)) for s in (24, 16)]
    frames = big + small
    bg.save(os.path.join(here, "icon.ico"), format="ICO",
            sizes=[(s, s) for s, _ in frames],
            append_images=[im for _, im in frames])
    print("saved:", os.path.join(here, "icon.ico"))


if __name__ == "__main__":
    build()
