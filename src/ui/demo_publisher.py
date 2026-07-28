"""Cycles through demo/states/ fixtures (Stage 4) on a QTimer, publishing
each one through the real publish_state() writer (src/runtime/
state_publisher.py) -- Stage 7's --demo mode deliberately reuses the
exact same output path a real LiveStateSource/StateWatcher watches,
rather than a second, demo-only rendering path. This class's only job is
deciding *when* to write the next fixture; it never touches a window or
a widget directly.
"""

from PySide6.QtCore import QObject, QTimer

from src.runtime.state_publisher import publish_state


class DemoStatePublisher(QObject):
    def __init__(
        self,
        states: list,
        output_path,
        interval_seconds: float = 5.0,
        publish_fn=publish_state,
        timer_factory=QTimer,
        parent=None,
    ):
        super().__init__(parent)
        if not states:
            raise ValueError("DemoStatePublisher requires at least one demo state")
        self._states = states
        self._output_path = output_path
        self._publish_fn = publish_fn
        self._index = 0
        self._timer = timer_factory(self)
        self._timer.setInterval(max(1, int(interval_seconds * 1000)))
        self._timer.timeout.connect(self._publish_next)

    @property
    def is_cycling(self) -> bool:
        return self._timer.isActive()

    def start(self) -> None:
        self._publish_next()  # publish the first fixture immediately, don't wait a full interval
        if len(self._states) > 1:
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _publish_next(self) -> None:
        self._publish_fn(self._states[self._index], output_path=self._output_path)
        self._index = (self._index + 1) % len(self._states)
