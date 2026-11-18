import math

import numpy as np
import pytest

from geoflow.physics import coriolis, rotate, rusanov


def test_equal_state_flux():
    q = np.array([2.0, 6.0, -4.0])
    for axis, exact in enumerate(([6, 38, -12], [-4, -12, 28])):
        np.testing.assert_array_equal(rusanov(q, q, 10.0, axis), exact)


@pytest.mark.parametrize("sign", [-1, 1])
def test_rotation(sign):
    q = np.array([3.0, 4.0, 2.0])
    angle = math.copysign(math.pi / 2, coriolis(sign * 45))
    result = rotate(q, angle)
    np.testing.assert_allclose(result, [3.0, sign * 2.0, -sign * 4.0], atol=1e-14)
    assert np.linalg.norm(result[1:]) == pytest.approx(np.linalg.norm(q[1:]))
