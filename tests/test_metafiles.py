"""Pictures drawn as metafiles (metafiles.py and the vendored metafile_render's fixes, vendor/README.md): small WMF and
EMF files built here record by record, each checked for what a page drawn from it shows."""
import stubs  # noqa: F401 (a clean environment)
import struct
import unittest

try:
    import pyclipper  # noqa: F401
    from PIL import Image  # noqa: F401
except ImportError:  # the office extra
    pyclipper = None

import pymupdf

# --- WMF ----------------------------------------------------------------------------------------------------

def wmf_record(function, *params):
    return struct.pack("<IH", 3 + len(params), function) + struct.pack(f"<{len(params)}h", *params)

def wmf_text(x, y, text):
    raw = text.encode("cp1252")
    padded = raw + b"\0" * (len(raw) % 2)
    words = struct.unpack(f"<{len(padded) // 2}h", padded)
    return wmf_record(0x0521, len(raw), *words, y, x)

def wmf(records, box=(0, 0, 1000, 500), inch=1000):
    """A placeable WMF: its bounding box (left, top, right, bottom) in units of 1/inch inch."""
    eof = wmf_record(0x0000)
    body = b"".join(records) + eof
    head = struct.pack("<IHhhhhHI", 0x9AC6CDD7, 0, *box, inch, 0)
    checksum = 0
    for (word,) in struct.iter_unpack("<H", head):
        checksum ^= word
    standard = struct.pack("<HHHIHIH", 1, 9, 0x0300, (18 + len(body)) // 2, 2,
                           max(len(r) for r in records + [eof]) // 2, 0)
    return head + struct.pack("<H", checksum) + standard + body

RED_BRUSH = wmf_record(0x02FC, 0, 0x00FF, 0x0000, 0)  # BS_SOLID, COLORREF 0x000000FF (red)
NULL_PEN = wmf_record(0x02FA, 5, 0, 0, 0, 0)            # PS_NULL
WINDOW = [wmf_record(0x0103, 8), wmf_record(0x020B, 0, 0), wmf_record(0x020C, 500, 1000)]  # anisotropic, no viewport

# --- EMF and EMF+ -------------------------------------------------------------------------------------------

def emf_record(kind, data=b""):
    data += b"\0" * (-len(data) % 4)
    return struct.pack("<II", kind, 8 + len(data)) + data

def plus(kind, flags=0, data=b""):
    return struct.pack("<HHII", kind, flags, 12 + len(data), len(data)) + data

def plus_comment(*records):
    data = b"EMF+" + b"".join(records)
    return emf_record(70, struct.pack("<I", len(data)) + data)

PLUS_HEADER = plus(0x4001, 1, struct.pack("<IIII", 0xDBC01002, 0, 96, 96))  # dual, 96 dpi
PLUS_EOF = plus(0x4002)

def emf(records, size=(400, 200)):
    """An EMF of `size` device pixels at 96 dpi (its frame in hundredths of a millimetre)."""
    width, height = size
    frame = (0, 0, round(width / 96 * 2540), round(height / 96 * 2540))
    body = b"".join(records) + emf_record(14, struct.pack("<III", 0, 0, 20))
    header = struct.pack("<II4i4iIIIIHHIIIiiii", 1, 88, 0, 0, width - 1, height - 1, *frame, 0x464D4520, 0x10000,
                         88 + len(body), 2 + len(records), 2, 0, 0, 0, 0, 1920, 1080, 508, 286)
    return header + body

def emf_text(x, y, text, advance=7):
    """EMR_EXTTEXTOUTW at (x, y), each character `advance` apart."""
    chars = text.encode("utf-16-le")
    chars += b"\0" * (-len(chars) % 4)
    offset_string = 76
    offset_dx = offset_string + len(chars)
    data = struct.pack("<4iIff", 0, 0, -1, -1, 1, 1.0, 1.0)
    data += struct.pack("<iiIII4iI", x, y, len(text), offset_string, 0, 0, 0, -1, -1, offset_dx)
    return emf_record(84, data + chars + struct.pack(f"<{len(text)}I", *[advance] * len(text)))

def rect_f(x, y, w, h):
    return struct.pack("<ffff", x, y, w, h)

@unittest.skipIf(pyclipper is None, "needs the office extra (Pillow, pyclipper)")
class Metafiles(unittest.TestCase):
    def page(self, data):
        from semantic_pdf_diff.metafiles import draw
        picture = draw(data)
        return picture, pymupdf.open("pdf", picture.pdf)[0]

    def color_at(self, page, x, y):
        pixmap = page.get_pixmap(dpi=72)
        return pixmap.pixel(int(x), int(y))

    def test_a_placeable_wmf_that_sets_only_its_window_fills_its_box(self):
        records = WINDOW + [RED_BRUSH, wmf_record(0x012D, 0), NULL_PEN, wmf_record(0x012D, 1),
                            wmf_record(0x041B, 500, 1000, 0, 0)]
        picture, page = self.page(wmf(records))
        self.assertEqual((picture.width, picture.height), (72.0, 36.0))  # 1 by 0.5 inch
        self.assertEqual(self.color_at(page, 36, 18), (255, 0, 0))   # the rectangle covers the box, not a corner

    def test_text_is_text_where_the_record_puts_it(self):
        picture, page = self.page(wmf(WINDOW + [wmf_text(100, 100, "Hello")]))
        (x0, y0, x1, y1, word, *_), = page.get_text("words")
        self.assertEqual(word, "Hello")
        self.assertAlmostEqual(x0, 7.2, delta=0.5)  # 100 of 1,000 units across 72 points
        self.assertEqual(picture.drawn["text"], 1)

    def test_an_excluded_rectangle_is_left_unpainted(self):
        records = WINDOW + [RED_BRUSH, wmf_record(0x012D, 0), NULL_PEN, wmf_record(0x012D, 1),
                            wmf_record(0x0415, 300, 600, 200, 400),  # ExcludeClipRect: bottom, right, top, left
                            wmf_record(0x041B, 500, 1000, 0, 0)]
        _, page = self.page(wmf(records))
        self.assertEqual(self.color_at(page, 36, 18), (255, 255, 255))  # the excluded middle
        self.assertEqual(self.color_at(page, 7, 7), (255, 0, 0))

    def test_a_dual_emf_draws_its_getdc_text_in_gdi_coordinates(self):
        # EMF+ scales its page by 2; the GDI text the GetDC window draws keeps GDI's own coordinates
        records = [plus_comment(PLUS_HEADER, plus(0x4030, 2, struct.pack("<f", 2.0)),
                                plus(0x400A, 0x8000, struct.pack("<II", 0xFF0000FF, 1) + rect_f(0, 0, 10, 10)),
                                plus(0x4004)),
                   emf_text(200, 100, "Label"),
                   plus_comment(PLUS_EOF)]
        picture, page = self.page(emf(records))
        self.assertEqual(picture.emfplus_mode, "dual")
        (x0, *_, word, _b, _l, _w), = page.get_text("words")
        self.assertEqual(word, "Label")
        self.assertAlmostEqual(x0 / page.rect.width, 200 / 400, delta=0.02)  # half way across, not off the edge

    def test_a_dual_emf_without_emfplus_drawing_draws_its_emf_records(self):
        black_brush = emf_record(37, struct.pack("<I", 0x80000004))     # SelectObject(BLACK_BRUSH)
        rectangle = emf_record(43, struct.pack("<4i", 0, 0, 400, 200))  # Rectangle
        picture, page = self.page(emf([plus_comment(PLUS_HEADER), black_brush, rectangle, plus_comment(PLUS_EOF)]))
        self.assertGreaterEqual(picture.drawn["path"], 1)
        self.assertEqual(self.color_at(page, page.rect.width / 2, page.rect.height / 2), (0, 0, 0))

    def test_an_emfplus_region_clips(self):
        # a region: the whole picture less a rectangle in its middle; a fill over everything leaves that hole
        region = struct.pack("<III", 0xDBC01002, 3, 4) + struct.pack("<I", 0x10000000) + rect_f(0, 0, 400, 200) + \
            struct.pack("<I", 0x10000000) + rect_f(150, 50, 100, 100)
        records = [plus_comment(PLUS_HEADER, plus(0x4008, (4 << 8) | 0, region), plus(0x4034, 0),
                                plus(0x400A, 0x8000, struct.pack("<II", 0xFFFF0000, 1) + rect_f(0, 0, 400, 200)),
                                PLUS_EOF)]
        picture, page = self.page(emf(records))
        width, height = page.rect.width, page.rect.height
        self.assertEqual(self.color_at(page, width / 2, height / 2), (255, 255, 255))  # the region's hole
        self.assertEqual(self.color_at(page, width / 10, height / 10), (255, 0, 0))

    def test_a_character_no_built_in_font_shows_is_counted(self):
        picture, page = self.page(emf([plus_comment(PLUS_HEADER, plus(0x4004)), emf_text(10, 10, "a→b"),
                                       plus_comment(PLUS_EOF)]))
        self.assertEqual(picture.skipped["characters a built-in font can't show"], 1)

if __name__ == "__main__":
    unittest.main()
