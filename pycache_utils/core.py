from __future__ import annotations

from abc import abstractmethod
from typing import (
    Any,
    Coroutine,
    TypeVar,
    Generic,
    TYPE_CHECKING,
    ParamSpec,
    Callable,
)
from datetime import datetime, timedelta
from inspect import iscoroutinefunction

T = TypeVar("T")
P = ParamSpec("P")
Coro = Coroutine[Any, Any, T]


class CachedFunction(Callable[P, T], Generic[P, T]):
    @abstractmethod
    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T: ...

    @abstractmethod
    def purge(self) -> None: ...


class CacheItem(Generic[T]):
    __slots__ = ("key", "value", "expire_at")

    if TYPE_CHECKING:
        key: str
        value: T
        expire_at: datetime | None

    def __init__(
        self, key: str, value: T, expire_at: datetime | None = None
    ) -> None:
        self.key = key
        self.value = value
        self.expire_at = expire_at

    @property
    def expired(self) -> bool:
        return self.expire_at is not None and self.expire_at < datetime.now()

    @property
    def expire_in(self) -> int | None:
        if self.expire_at is not None:
            return (self.expire_at - datetime.now()).total_seconds()
        return None

    def __repr__(self) -> str:
        return f"CacheItem(key={self.key}, value={self.value}, expire_at={self.expire_at})"


class LocalCacheStore(Generic[T]):
    __slots__ = ("tag", "_store")

    if TYPE_CHECKING:
        tag: str
        _store: dict[str, CacheItem[T]]

    def __init__(self, tag: str) -> None:
        self._store = {}
        self.tag = tag

    def purge(self) -> None:
        self._store = {}

    def __getitem__(self, key: str) -> T:
        item = self._store[key]
        if item.expired:
            del self._store[key]
            raise KeyError(
                f"Item with tag: {self.tag}, key: {key} has expired"
            )
        return item.value

    def __setitem__(self, key: str, value: T) -> None:
        self._store[key] = value


class CacheStore(Generic[T]):
    _stores: dict[str, LocalCacheStore[T]] = {}

    @classmethod
    def get_store(cls, tag: str) -> LocalCacheStore[T]:
        if tag not in cls._stores:
            cls._stores[tag] = LocalCacheStore(tag)
        return cls._stores[tag]

    @classmethod
    def purge_all(cls) -> None:
        cls._stores = {}

    @classmethod
    def purge(cls, tag: str) -> None:
        if tag in cls._stores:
            del cls._stores[tag]

    @classmethod
    def set(
        cls, tag: str, key: str, value: T, expire_at: datetime | None = None
    ) -> None:
        store = cls.get_store(tag)
        store._store[key] = CacheItem(key, value, expire_at)


def _cache(
    func: Callable[P, T],
    get_key: Callable[P, str],
    tag: str,
    expire_in: int | None = None,
) -> Callable[P, T]:
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        key = get_key(*args, **kwargs)
        store = CacheStore.get_store(tag)
        try:
            return store[key]
        except KeyError:
            value = func(*args, **kwargs)
            expire_at = (
                datetime.now() + timedelta(seconds=expire_in)
                if expire_in
                else None
            )
            store[key] = CacheItem(key, value, expire_at)
            return value

    return wrapper


def _cache_async(
    func: Callable[P, T],
    get_key: Callable[P, str],
    tag: str,
    expire_in: int | None = None,
) -> Callable[P, T]:
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        key = get_key(*args, **kwargs)
        store = CacheStore.get_store(tag)
        try:
            return store[key]
        except KeyError:
            value = await func(*args, **kwargs)
            expire_at = (
                datetime.now() + timedelta(seconds=expire_in)
                if expire_in
                else None
            )
            store[key] = CacheItem(key, value, expire_at)
            return value

    return wrapper


def cache(
    func: Callable[P, T],
    tag: str,
    get_key: Callable[P, str],
    expire_in: int | None = None,
) -> CachedFunction[P, T]:
    if iscoroutinefunction(func):
        fn = _cache_async(func, get_key, tag, expire_in)
    else:
        fn = _cache(func, get_key, tag, expire_in)
    fn.purge = lambda: CacheStore.purge(tag)
    return fn
