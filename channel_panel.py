"""ChannelPanel: right-dock widget for configuring channel placement."""
from PySide6.QtWidgets import (
    QWidget, QPushButton, QLabel, QSpinBox,
    QHBoxLayout, QVBoxLayout, QButtonGroup,
)
from PySide6.QtCore import Qt, Signal


class ChannelPanel(QWidget):
    """Right-side panel for configuring I and L channel placement."""

    params_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._suppress = False
        self.setMinimumWidth(200)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)
        layout.setSpacing(6)
        layout.setContentsMargins(10, 10, 10, 10)

        # --- Type selector ---
        layout.addWidget(QLabel("<b>Channel Type</b>"))
        type_widget = QWidget()
        type_layout = QHBoxLayout(type_widget)
        type_layout.setContentsMargins(0, 0, 0, 0)
        type_layout.setSpacing(4)
        self._btn_i = QPushButton("▬  I")
        self._btn_i.setCheckable(True)
        self._btn_i.setChecked(True)
        self._btn_l = QPushButton("⌐  L")
        self._btn_l.setCheckable(True)
        self._type_group = QButtonGroup(self)
        self._type_group.addButton(self._btn_i)
        self._type_group.addButton(self._btn_l)
        self._type_group.setExclusive(True)
        type_layout.addWidget(self._btn_i)
        type_layout.addWidget(self._btn_l)
        layout.addWidget(type_widget)

        layout.addSpacing(6)

        # --- I channel params ---
        self._i_widget = QWidget()
        i_layout = QVBoxLayout(self._i_widget)
        i_layout.setContentsMargins(0, 0, 0, 0)
        i_layout.setSpacing(4)

        i_layout.addWidget(QLabel("Length (tiles):"))
        self._spin_len = QSpinBox()
        self._spin_len.setRange(1, 40)
        self._spin_len.setValue(3)
        i_layout.addWidget(self._spin_len)

        i_layout.addWidget(QLabel("Width (tiles):"))
        self._spin_w = QSpinBox()
        self._spin_w.setRange(1, 10)
        self._spin_w.setValue(1)
        i_layout.addWidget(self._spin_w)

        i_layout.addWidget(QLabel("Orientation:"))
        orient_widget = QWidget()
        orient_layout = QHBoxLayout(orient_widget)
        orient_layout.setContentsMargins(0, 0, 0, 0)
        orient_layout.setSpacing(4)
        self._btn_h = QPushButton("— H")
        self._btn_h.setCheckable(True)
        self._btn_h.setChecked(True)
        self._btn_v = QPushButton("| V")
        self._btn_v.setCheckable(True)
        self._orient_group = QButtonGroup(self)
        self._orient_group.addButton(self._btn_h)
        self._orient_group.addButton(self._btn_v)
        self._orient_group.setExclusive(True)
        orient_layout.addWidget(self._btn_h)
        orient_layout.addWidget(self._btn_v)
        i_layout.addWidget(orient_widget)

        layout.addWidget(self._i_widget)

        # --- L channel params ---
        self._l_widget = QWidget()
        l_layout = QVBoxLayout(self._l_widget)
        l_layout.setContentsMargins(0, 0, 0, 0)
        l_layout.setSpacing(4)

        l_layout.addWidget(QLabel("X extension (tiles):"))
        self._spin_lx = QSpinBox()
        self._spin_lx.setRange(0, 40)
        self._spin_lx.setValue(3)
        l_layout.addWidget(self._spin_lx)

        l_layout.addWidget(QLabel("Y extension (tiles):"))
        self._spin_ly = QSpinBox()
        self._spin_ly.setRange(0, 40)
        self._spin_ly.setValue(3)
        l_layout.addWidget(self._spin_ly)

        l_layout.addWidget(QLabel("Width (tiles):"))
        self._spin_lw = QSpinBox()
        self._spin_lw.setRange(1, 10)
        self._spin_lw.setValue(1)
        l_layout.addWidget(self._spin_lw)

        l_layout.addWidget(QLabel("Corner (rotation):"))
        rot_widget = QWidget()
        rot_layout = QHBoxLayout(rot_widget)
        rot_layout.setContentsMargins(0, 0, 0, 0)
        rot_layout.setSpacing(2)
        self._rot_btns = []
        self._rot_group = QButtonGroup(self)
        for i, (lbl, tip) in enumerate([
            ("⌐", "Corner top-left"),
            ("Γ", "Corner top-right"),
            ("L", "Corner bottom-left"),
            ("J", "Corner bottom-right"),
        ]):
            btn = QPushButton(lbl)
            btn.setCheckable(True)
            btn.setFixedSize(32, 28)
            btn.setToolTip(tip)
            self._rot_group.addButton(btn, i)
            rot_layout.addWidget(btn)
            self._rot_btns.append(btn)
        self._rot_btns[0].setChecked(True)
        l_layout.addWidget(rot_widget)

        self._l_widget.setVisible(False)
        layout.addWidget(self._l_widget)

        layout.addStretch()

        # --- Connect signals ---
        self._type_group.buttonClicked.connect(self._on_type_changed)
        self._spin_len.valueChanged.connect(self._emit)
        self._spin_w.valueChanged.connect(self._emit)
        self._orient_group.buttonClicked.connect(self._emit)
        self._spin_lx.valueChanged.connect(self._emit)
        self._spin_ly.valueChanged.connect(self._emit)
        self._spin_lw.valueChanged.connect(self._emit)
        self._rot_group.buttonClicked.connect(self._emit)

    def _on_type_changed(self, *_):
        is_l = self._btn_l.isChecked()
        self._i_widget.setVisible(not is_l)
        self._l_widget.setVisible(is_l)
        self._emit()

    def _emit(self, *_):
        if not self._suppress:
            self.params_changed.emit(self._params())

    def _params(self) -> dict:
        if self._btn_l.isChecked():
            return {
                'type': 'L',
                'len_x': self._spin_lx.value(),
                'len_y': self._spin_ly.value(),
                'width': self._spin_lw.value(),
                'rotation': self._rot_group.checkedId(),
            }
        return {
            'type': 'I',
            'length': self._spin_len.value(),
            'width': self._spin_w.value(),
            'orientation': 'H' if self._btn_h.isChecked() else 'V',
        }

    @property
    def params(self) -> dict:
        return self._params()

    def set_params(self, d: dict):
        """Update all controls to reflect d without emitting params_changed."""
        self._suppress = True
        try:
            t = d.get('type', 'I')
            if t == 'I':
                self._btn_i.setChecked(True)
                self._btn_l.setChecked(False)
                self._i_widget.setVisible(True)
                self._l_widget.setVisible(False)
                self._spin_len.setValue(d.get('length', 3))
                self._spin_w.setValue(d.get('width', 1))
                orient = d.get('orientation', 'H')
                self._btn_h.setChecked(orient == 'H')
                self._btn_v.setChecked(orient == 'V')
            else:
                self._btn_l.setChecked(True)
                self._btn_i.setChecked(False)
                self._i_widget.setVisible(False)
                self._l_widget.setVisible(True)
                self._spin_lx.setValue(d.get('len_x', 3))
                self._spin_ly.setValue(d.get('len_y', 3))
                self._spin_lw.setValue(d.get('width', 1))
                rot = d.get('rotation', 0)
                for i, btn in enumerate(self._rot_btns):
                    btn.setChecked(i == rot)
        finally:
            self._suppress = False
