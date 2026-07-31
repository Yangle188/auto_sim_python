# framework/event_bus.py
from typing import Callable, Dict, List


class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, topic: str, callback: Callable) -> None:
        """新增订阅（同一回调不重复注册）"""
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        if callback not in self._subscribers[topic]:
            self._subscribers[topic].append(callback)

    def unsubscribe(self, topic: str, callback: Callable) -> None:
        """取消订阅"""
        if topic in self._subscribers and callback in self._subscribers[topic]:
            self._subscribers[topic].remove(callback)

    def publish(self, topic: str, data: dict) -> None:
        """
        发布事件。拷贝回调列表，避免订阅变更导致遍历异常；
        单个回调异常不影响同主题其余订阅者。
        """
        if topic not in self._subscribers:
            return
        callbacks = self._subscribers[topic].copy()
        for callback in callbacks:
            try:
                callback(data)
            except Exception as exc:
                print(f"[EventBus] topic={topic!r} 回调异常: {exc}")

    def clear_topic(self, topic: str) -> None:
        if topic in self._subscribers:
            self._subscribers.pop(topic)

    def clear_all(self) -> None:
        self._subscribers.clear()
