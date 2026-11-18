import numpy as np

from giongtoi.engines.vieneu_engine import blend_embeddings


def test_blend_single_is_identity():
    v = np.array([3.0, 4.0], dtype=np.float32)
    assert np.allclose(blend_embeddings([v]), v)


def test_blend_averages_direction_and_keeps_typical_norm():
    a, b = np.array([10.0, 0.0]), np.array([0.0, 20.0])
    m = blend_embeddings([a, b])
    assert np.isclose(np.linalg.norm(m), 15.0)  # chuẩn trung bình
    assert np.isclose(m[0], m[1])  # hướng trung bình của hai vector đơn vị
    assert m.dtype == np.float32
