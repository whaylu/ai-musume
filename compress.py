"""
压缩 static/imgs/ 下的所有 PNG。
无损压缩（optimize=True），不损画质，通常能省 10~40%。
"""
from PIL import Image
from pathlib import Path

IMGS = Path("static/imgs")

total_before = 0
total_after = 0

for p in sorted(IMGS.glob("*.png")):
    before = p.stat().st_size
    try:
        img = Image.open(p)
    except Exception as e:
        print(f"{p.name:30} 跳过：{e}")
        continue

    # PNG 保留透明通道
    if img.mode not in ("RGBA", "P"):
        img = img.convert("RGBA")

    # optimize=True 是无损压缩
    img.save(p, "PNG", optimize=True)

    after = p.stat().st_size
    total_before += before
    total_after += after
    pct = (1 - after / before) * 100 if before else 0
    print(f"{p.name:30} {before // 1024:>6} KB -> {after // 1024:>6} KB  (-{pct:.0f}%)")

print()
print(f"总计: {total_before // 1024} KB -> {total_after // 1024} KB  "
      f"(-{(1 - total_after / total_before) * 100:.0f}%)")