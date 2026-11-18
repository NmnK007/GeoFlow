import numpy as np
import pytest

from geoflow.boundaries import faces, ghost


@pytest.mark.parametrize("direction", [0, 1])
@pytest.mark.parametrize("upper", [False, True])
def test_ghost_and_wall_flux(direction, upper):
    q = np.arange(1.0, 46.0).reshape(3, 3, 5)
    axis = 2 - direction
    edge = np.take(q, [-1 if upper else 0], axis=axis)
    edge[direction + 1] *= -1
    np.testing.assert_equal(ghost(q, direction, upper, "wall"), edge)
    periodic = np.take(q, [0 if upper else -1], axis=axis)
    np.testing.assert_equal(ghost(q, direction, upper, "periodic"), periodic)
    wall = faces(q, 9.81, direction, "wall")[0]
    np.testing.assert_equal(np.take(wall, [0, -1], axis=axis - 1), 0.0)
