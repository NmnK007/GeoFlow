"""Spherical coordinates in degrees, distances in metres."""

import numpy as np

R = 6371000.0


def wrap(lon):
    return (np.asarray(lon) + 180) % 360 - 180


def distance(lon1, lat1, lon2, lat2):
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    a = (
        np.sin((phi2 - phi1) / 2) ** 2
        + np.cos(phi1)
        * np.cos(phi2)
        * np.sin(np.radians(wrap(np.asarray(lon2) - lon1)) / 2) ** 2
    )
    return 2 * R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def rates(u, v, latitude):
    if abs(latitude) >= 89.999:
        raise ValueError("polar coordinate singularity")
    return np.degrees(np.array([u / np.cos(np.radians(latitude)), v]) / R)


def bounds(west, east, south, north):
    if (
        not np.all(np.isfinite([west, east, south, north]))
        or not -90 < south < north < 90
    ):
        raise ValueError("invalid regional bounding box")
    width = (east - west) % 360
    if not 0 < width <= 180:
        raise ValueError("regional longitude span must be in (0,180] degrees")
    return width
