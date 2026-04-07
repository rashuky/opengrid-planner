"""ChannelListPanel: object-tree dock showing all placed channels."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem
from PySide6.QtCore import Qt, Signal

from elements.channels.base import Channel


def _channel_label(ch: Channel) -> str:
    d = ch.to_dict()
    t = d['type']
    if t == 'I':
        return f"I  {d['orientation']}  len={d['length']}  w={d['width']}"
    corners = ['top-left', 'top-right', 'bot-left', 'bot-right']
    corner = corners[d.get('rotation', 0)]
    return f"L {corner}  x={d['len_x']} y={d['len_y']} w={d['width']}"


class ChannelListPanel(QWidget):
    """Lists every placed channel; emits channel_selected(id) on click."""

    channel_selected = Signal(object)  # id(channel), or -1 when nothing selected

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(180)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        layout.addWidget(QLabel("<b>Placed Channels</b>"))
        hint = QLabel(
            "<small>Click to select · Click again to move<br>"
            "Ctrl+R: rotate · Del: delete · Esc: cancel</small>"
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SingleSelection)
        layout.addWidget(self._list)
        self._list.currentItemChanged.connect(self._on_selection_changed)

    # ------------------------------------------------------------------
    # Public API (called by main_window via signals)
    # ------------------------------------------------------------------

    def add_channel(self, channel: Channel):
        item = QListWidgetItem(_channel_label(channel))
        item.setData(Qt.ItemDataRole.UserRole, id(channel))
        self._list.addItem(item)

    def remove_channel(self, channel_id: int):
        for i in range(self._list.count()):
            if self._list.item(i).data(Qt.ItemDataRole.UserRole) == channel_id:
                self._list.takeItem(i)
                return

    def select_channel(self, channel_id: int):
        self._list.blockSignals(True)
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == channel_id:
                self._list.setCurrentItem(item)
                self._list.blockSignals(False)
                return
        self._list.clearSelection()
        self._list.setCurrentItem(None)
        self._list.blockSignals(False)

    def deselect(self):
        self._list.blockSignals(True)
        self._list.clearSelection()
        self._list.setCurrentItem(None)
        self._list.blockSignals(False)

    def update_channel(self, old_id: int, new_channel: Channel):
        """Replace the list entry for old_id with the new channel's label and id."""
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == old_id:
                item.setText(_channel_label(new_channel))
                item.setData(Qt.ItemDataRole.UserRole, id(new_channel))
                return
        self.add_channel(new_channel)  # fallback

    def clear(self):
        self._list.clear()

    # ------------------------------------------------------------------

    def _on_selection_changed(self, current, _):
        if current is not None:
            self.channel_selected.emit(current.data(Qt.ItemDataRole.UserRole))
        else:
            self.channel_selected.emit(-1)
