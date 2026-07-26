# framework/event_bus.py
from typing import Callable, Dict, List


class EventBus:
    def __init__(self):
        """
        初始化
        """
        self._subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, topic: str, callback: Callable) -> None:
        """
        新增订阅
        :param topic:
        :param callback:
        :return:
        """
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        if callback not in self._subscribers[topic]:
            self._subscribers[topic].append(callback)

    def unsubscribe(self, topic: str, callback: Callable) -> None:
        """
        取消订阅
        :param topic:
        :param callback:
        :return:
        """
        if topic in self._subscribers and callback in self._subscribers[topic]:
            self._subscribers[topic].remove(callback)

    def publish(self, topic: str, data: dict) -> None:
        """
        发布事件
        :param topic:
        :param data:
        :return:
        """
        if topic not in self._subscribers:
            return
        # 这里copy是为了避免回掉内增减订阅导致遍历异常
        callbacks = self._subscribers[topic].copy()
        for callback in callbacks:
            callback(data)

    def clear_topic(self, topic: str) -> None:
        if topic in self._subscribers:
            self._subscribers.pop(topic)

    def clear_all(self) -> None:
        self._subscribers.clear()