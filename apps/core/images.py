"""Traitement des images envoyées : validation par Pillow, réduction de taille, ré-encodage."""
import io

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

MAX_SIDE = 1600


def compress_image(uploaded, *, max_side=MAX_SIDE, quality=85):
    """Redimensionne (côté max), applique l'orientation EXIF, supprime les métadonnées et renvoie un JPEG.

    Le ré-encodage neutralise aussi les fichiers piégés (polyglottes) : seul le contenu pixel est conservé."""
    uploaded.seek(0)
    image = ImageOps.exif_transpose(Image.open(uploaded))
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        background = Image.new("RGB", image.size, "white")
        background.paste(image, mask=image.split()[-1])
        image = background
    else:
        image = image.convert("RGB")
    image.thumbnail((max_side, max_side))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=quality, optimize=True)
    stem = uploaded.name.rsplit(".", 1)[0][:60] or "image"
    return ContentFile(buffer.getvalue(), name=f"{stem}.jpg")
