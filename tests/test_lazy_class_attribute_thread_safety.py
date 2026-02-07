import threading
import time
import unittest
from typing import Any

from marshmallow_dataclass.lazy_class_attribute import LazyClassAttribute


class TestLazyClassAttributeThreadSafety(unittest.TestCase):
    def test_concurrent_first_access_does_not_return_forward_value(self) -> None:
        started: threading.Event = threading.Event()
        computed_value: object = object()
        forward_value: str = "FORWARD_VALUE"
        thread_result: list[Any] = []

        def compute() -> object:
            started.set()
            # Release the GIL (on GIL builds) and widen the race window.
            time.sleep(0.2)
            return computed_value

        class Foo:
            value: Any = LazyClassAttribute(compute, "value", forward_value)

        def access_from_thread() -> None:
            thread_result.append(Foo.value)

        t: threading.Thread = threading.Thread(target=access_from_thread)
        t.start()
        started_set: bool = started.wait(timeout=5.0)
        self.assertTrue(started_set)

        main_thread_value: Any = Foo.value
        t.join(timeout=5.0)
        if t.is_alive():
            self.fail("worker thread did not finish within timeout")

        self.assertEqual(len(thread_result), 1)
        self.assertIs(thread_result[0], computed_value)
        self.assertIs(main_thread_value, computed_value)
