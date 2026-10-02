"""Region names: the kinds of extraction task (a task's prefix, "tile:p3:2" is a tile), the families judges compare
claims by, and the names of the crops a task renders (code review 2026-10-01, A1: four region tables, the prefix
open-coded in five places, the crop stem written twice and globbed by the store's clean-up).
"""
# Every region; those read from images; those read from the text layer.
ALL = frozenset({"text", "table", "tile", "figure", "overview", "vision", "table-detection"})
VISUAL = frozenset({"tile", "figure", "overview", "vision"})
TEXTUAL = frozenset({"text", "table"})

# The families a round's units are judged by: text, table, or anything read from an image.
FAMILY = {"text": "text", "table": "table", "tile": "visual", "figure": "visual", "overview": "visual"}

def region_of(task):
    """'tile:p3:2-r0' -> 'tile'; 'table-detection' and 'vision' are their own regions."""
    return (task or "").split(":")[0]

def family_of(task):
    return FAMILY.get(region_of(task))

def crop_stem(content):
    """The start of every crop a content item's tasks render (a content id's hash, shortened)."""
    return content.split(":", 1)[1][:12]

def crop_name(stem, tag, suffix=""):
    """A crop's file name: 'tile:p3:2' rendered for stem s is 's-tile-p3-2.png' (suffix before the extension)."""
    return f"{stem}-{tag.replace(':', '-')}{suffix}.png"

def crops_of(content):
    """The glob that finds a content item's crops in an assets folder."""
    return crop_stem(content) + "-*.png"
