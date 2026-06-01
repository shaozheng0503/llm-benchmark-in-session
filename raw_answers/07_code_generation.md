```python
import threading
from collections import OrderedDict
from typing import Any, Optional


class ThreadSafeLRUCache:
    """线程安全的 LRU 缓存，O(1) get/put。"""

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        self._capacity = capacity
        self._cache: "OrderedDict[Any, Any]" = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: Any) -> Optional[Any]:
        with self._lock:
            if key not in self._cache:
                return None
            self._cache.move_to_end(key)  # 标记为最近使用
            return self._cache[key]

    def put(self, key: Any, value: Any) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            if len(self._cache) > self._capacity:
                self._cache.popitem(last=False)  # 淘汰最久未使用


# ---------------------- 单元测试 ----------------------
import unittest


class TestThreadSafeLRUCache(unittest.TestCase):
    def test_basic_get_put(self) -> None:
        cache = ThreadSafeLRUCache(capacity=2)
        cache.put("a", 1)
        cache.put("b", 2)
        self.assertEqual(cache.get("a"), 1)
        self.assertEqual(cache.get("b"), 2)
        self.assertIsNone(cache.get("c"))

    def test_eviction_lru(self) -> None:
        cache = ThreadSafeLRUCache(capacity=2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.get("a")           # 访问 a，使 b 成为最久未使用
        cache.put("c", 3)        # 触发淘汰，应淘汰 b
        self.assertEqual(cache.get("a"), 1)
        self.assertIsNone(cache.get("b"))
        self.assertEqual(cache.get("c"), 3)

    def test_concurrency_safety(self) -> None:
        """多线程并发 put/get，最终大小不应超过 capacity。"""
        cache = ThreadSafeLRUCache(capacity=50)
        errors: list = []

        def worker(start: int) -> None:
            try:
                for i in range(start, start + 1000):
                    cache.put(i, i)
                    cache.get(i % 50)
            except Exception as e:  # pragma: no cover
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(t * 1000,)) for t in range(8)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        self.assertEqual(errors, [])
        self.assertLessEqual(len(cache._cache), 50)


if __name__ == "__main__":
    unittest.main()
```
