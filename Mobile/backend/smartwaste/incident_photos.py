from base64 import b64decode
from binascii import Error
from io import BytesIO

from fastapi import HTTPException
from PIL import Image


def normalized_jpeg(encoded):
    """Bound pixel/byte counts, decode the input, and remove EXIF and other metadata."""
    try:
        original = b64decode(encoded, validate=True)
        if len(original) > 512 * 1024:
            raise ValueError()
        with Image.open(BytesIO(original), formats=['JPEG']) as image:
            if not (0 < image.width <= 1600 and 0 < image.height <= 1600):
                raise ValueError()
            output = BytesIO()
            image.convert('RGB').save(output, format='JPEG', quality=82, optimize=True)
            jpeg = output.getvalue()
        if len(jpeg) > 512 * 1024:
            raise ValueError()
        return jpeg
    except (Error, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(422, 'Fotografia trebuie să fie un JPEG valid de maximum 512 KB.') from None
