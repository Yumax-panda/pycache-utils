from pycache_utils.core import cache
import random

random.seed(0)


def test_cache():

    def test_function(min_value: int = 0, max_value: int = 100):
        return random.randint(min_value, max_value)

    cached_func = cache(
        test_function,
        tag="test_cache",
        get_key=lambda min_value, max_value: f"{min_value}-{max_value}",
    )

    assert cached_func(0, 100) == cached_func(0, 100)
    assert cached_func(0, 100) != cached_func(0, 101)
