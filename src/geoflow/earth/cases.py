"""Historical windows are study configurations; availability depends on the imported file."""

from .acquire import CASE

CASES = {
    "Arabian Sea": CASE,
    "Bay of Bengal": {
        "box": [80, 94, 8, 20],
        "start": "2020-07-01",
        "end": "2020-07-04",
    },
    "Somali Current": {
        "box": [48, 55, 3, 12],
        "start": "2020-07-01",
        "end": "2020-07-04",
    },
    "Winter monsoon contrast": dict(CASE, start="2020-01-01", end="2020-01-04"),
    "Mesoscale eddies": dict(CASE, box=[60, 69, 10, 18]),
    "Surface transport": CASE,
}
