import threading
from typing import Any, Callable


__all__ = ("lazy_class_attribute",)

_init_depth: threading.local = threading.local()


def _get_init_depth() -> int:
    """Return the per-thread lazy initialization depth."""
    depth: Any = getattr(_init_depth, "depth", 0)
    if isinstance(depth, int):
        return depth
    return 0


def _increment_init_depth() -> None:
    """Increment the per-thread lazy initialization depth."""
    depth: int = _get_init_depth()
    _init_depth.depth = depth + 1


def _decrement_init_depth() -> None:
    """Decrement the per-thread lazy initialization depth."""
    depth: int = _get_init_depth()
    new_depth: int = depth - 1
    if new_depth <= 0:
        _init_depth.depth = 0
        return
    _init_depth.depth = new_depth


class LazyClassAttribute:
    """Descriptor decorator implementing a class-level, read-only property.

    This caches its value by replacing the descriptor with the computed value on
    the owning class.

    In order to support recursive definitions, re-entrant access from the same
    thread while initialization is in-progress returns the ``forward_value``.
    Concurrent access from other threads will block until initialization is
    complete.
    """

    __slots__ = (
        "func",
        "name",
        "forward_value",
        "_initialized_event",
        "_initializing",
        "_initializing_thread_id",
        "_lock",
    )

    def __init__(
        self,
        func: Callable[..., Any],
        name: str | None = None,
        forward_value: Any = None,
    ) -> None:
        """
        :param func: Callable that computes the attribute value.
        :param name: Name of the attribute on the owner class.
        :param forward_value: Value returned on re-entrant access during initialization.
        """
        self.func = func
        self.name = name
        self.forward_value = forward_value
        self._initialized_event: threading.Event | None = None
        self._initializing = False
        self._initializing_thread_id: int | None = None
        self._lock = threading.Lock()

    def __get__(self, instance: object | None, cls: type | None = None) -> Any:
        if cls is None:
            if instance is None:
                raise TypeError(
                    "LazyClassAttribute.__get__ called without instance or class."
                )
            cls = type(instance)

        if self.name is None:
            raise AttributeError(
                "LazyClassAttribute used without being bound to a name."
            )

        name: str = self.name
        thread_id: int = threading.get_ident()

        while True:
            should_initialize: bool = False

            with self._lock:
                current: Any = cls.__dict__.get(name)
                if current is not self and current is not None:
                    # "getattr" is used to handle bounded methods.
                    return getattr(cls, name)

                if self._initializing:
                    if self._initializing_thread_id == thread_id:
                        return self.forward_value

                    # When we're already in the middle of initializing *another*
                    # LazyClassAttribute in this thread (e.g. schema generation),
                    # returning a placeholder avoids potential cross-thread deadlocks
                    # in mutually-recursive graphs.
                    if self.forward_value is not None and _get_init_depth() > 0:
                        return self.forward_value

                    event: threading.Event | None = self._initialized_event
                    if event is None:
                        event = threading.Event()
                        self._initialized_event = event
                else:
                    self._initializing = True
                    self._initializing_thread_id = thread_id
                    event = threading.Event()
                    self._initialized_event = event
                    should_initialize = True

            if should_initialize:
                _increment_init_depth()
                try:
                    value: Any = self.func()
                    setattr(cls, name, value)
                    return getattr(cls, name)
                finally:
                    _decrement_init_depth()
                    with self._lock:
                        self._initializing = False
                        self._initializing_thread_id = None
                        event_to_set: threading.Event | None = self._initialized_event
                        self._initialized_event = None
                        if event_to_set is not None:
                            event_to_set.set()

            event.wait()

    def __set_name__(self, owner: type, name: str) -> None:
        if self.name is None:
            self.name = name


lazy_class_attribute = LazyClassAttribute
