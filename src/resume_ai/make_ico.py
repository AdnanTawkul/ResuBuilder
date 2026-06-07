from pathlib import Path
import subprocess
from PIL import Image

SVG_FILE = Path(r"G:\Python\ResuBuilder\ResuBuilder\src\resume_ai\assets\resubuilder_logo.svg")
PNG_FILE = Path(r"G:\Python\ResuBuilder\ResuBuilder\src\resume_ai\assets\logo_1024.png")
ICO_FILE = Path(r"G:\Python\ResuBuilder\ResuBuilder\src\resume_ai\assets\logo.ico")

INKSCAPE = Path(r"C:\Program Files\Inkscape\bin\inkscape.exe")

SIZES = [(16, 16), (32, 32), (48, 48), (256, 256)]


def main():
    if ICO_FILE.exists():
        ICO_FILE.unlink()

    subprocess.run(
        [
            str(INKSCAPE),
            str(SVG_FILE),
            "--export-type=png",
            f"--export-filename={PNG_FILE}",
            "--export-width=1024",
            "--export-height=1024",
        ],
        check=True,
    )

    img = Image.open(PNG_FILE).convert("RGBA")

    img.save(
        ICO_FILE,
        format="ICO",
        sizes=SIZES,
    )

    PNG_FILE.unlink()

    check = Image.open(ICO_FILE)
    print("ICO created:", ICO_FILE)
    print("Included sizes:", check.ico.sizes())


if __name__ == "__main__":
    main()