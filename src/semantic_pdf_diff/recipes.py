"""A query's recipe: the caller's key tuple saying how the pipeline built a query (role, region, content, task, ...).
Labels only: answers are found by the query itself (llm.query_hash), never by its recipe, so recipes can change
without re-recording.

The first four places are shared slots, read by every role alike (logs, the store's query log, fixture labels):
the role; the region (a triage's kind, a comparison's mode); the content (extraction and triage only); the task (a
triage's id, a comparison's first claim). By role, the places after the role have names (RECIPES), and the rest are
the role's extras (code review 2026-10-08, C14: these were read by position in six places with two parsers).
"""

RECIPES = {"extract": ("region", "content", "task", "text", "crop", "heading"),
           "triage": ("kind", "content", "id", "inputs"),
           "compare": ("mode", "settings", "a", "b")}

class Recipe(tuple):
    """A recipe, its shared slots read by name. Equal to, and stored as, the plain tuple."""
    __slots__ = ()

    @property
    def role(self):
        return self[0] if self else ""

    @property
    def region(self):
        """The second place: an extraction's region, a triage's kind, a comparison's mode."""
        return self[1] if len(self) > 1 else ""

    @property
    def content(self):
        """The content read, for extraction and triage; otherwise ""."""
        return self[2] if self.role in ("extract", "triage") and len(self) > 2 else ""

    @property
    def task(self):
        """The fourth place: an extraction's task, a triage's id, a comparison's first claim."""
        return self[3] if len(self) > 3 else ""

    @property
    def label(self):
        """What logs name a query by: role, region and task, those present."""
        return self[:2] + self[3:4]

def recipe_fields(parts):
    """{role, its named fields, extras} of a recipe."""
    parts = list(parts or ())
    role = parts[0] if parts else ""
    names = RECIPES.get(role, ())
    return {"role": role, **dict(zip(names, parts[1:])), "extras": parts[1 + len(names):]}
