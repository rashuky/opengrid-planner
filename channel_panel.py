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
        self._btn_t = QPushButton("⊤  T")
        self._btn_t.setCheckable(True)
        self._type_group = QButtonGroup(self)
        self._type_group.addButton(self._btn_i)
        self._type_group.addButton(self._btn_l)
        self._type_group.addButton(self._btn_t)
        self._type_group.setExclusive(True)
        type_layout.addWidget(self._btn_i)
        type_layout.addWidget(self._btn_l)
        type_layout.addWidget(self._btn_t)
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

        l_layout.addWidget(QLabel("Corner:"))
        rot_widget = QWidget()
        rot_layout = QHBoxLayout(rot_widget)
        rot_layout.setContentsMargins(0, 0, 0, 0)
        rot_layout.setSpacing(4)
        self._l_rotation = 0
        self._rot_left_btn = QPushButton("◀")
        self._rot_left_btn.setFixedSize(32, 28)
        self._rot_left_btn.setToolTip("Rotate counter-clockwise")
        self._rot_corner_lbl = QLabel()
        self._rot_corner_lbl.setAlignment(Qt.AlignCenter)
        self._rot_corner_lbl.setMinimumWidth(60)
        self._rot_right_btn = QPushButton("▶")
        self._rot_right_btn.setFixedSize(32, 28)
        self._rot_right_btn.setToolTip("Rotate clockwise")
        rot_layout.addWidget(self._rot_left_btn)
        rot_layout.addWidget(self._rot_corner_lbl)
        rot_layout.addWidget(self._rot_right_btn)
        rot_layout.addStretch()
        self._update_rot_label()
        l_layout.addWidget(rot_widget)

        self._l_widget.setVisible(False)
        layout.addWidget(self._l_widget)

        # --- T channel params ---
        self._t_widget = QWidget()
        t_layout = QVBoxLayout(self._t_widget)
        t_layout.setContentsMargins(0, 0, 0, 0)
        t_layout.setSpacing(4)

        t_layout.addWidget(QLabel("Stem extension (tiles):"))
        self._spin_t_sl = QSpinBox()
        self._spin_t_sl.setRange(0, 40)
        self._spin_t_sl.setValue(3)
        t_layout.addWidget(self._spin_t_sl)

        t_layout.addWidget(QLabel("Stem width (tiles):"))
        self._spin_t_sw = QSpinBox()
        self._spin_t_sw.setRange(1, 10)
        self._spin_t_sw.setValue(1)
        t_layout.addWidget(self._spin_t_sw)

        t_layout.addWidget(QLabel("Left extension (tiles):"))
        self._spin_t_ll = QSpinBox()
        self._spin_t_ll.setRange(0, 40)
        self._spin_t_ll.setValue(3)
        t_layout.addWidget(self._spin_t_ll)

        t_layout.addWidget(QLabel("Left width (tiles):"))
        self._spin_t_lw = QSpinBox()
        self._spin_t_lw.setRange(1, 10)
        self._spin_t_lw.setValue(1)
        t_layout.addWidget(self._spin_t_lw)

        t_layout.addWidget(QLabel("Right extension (tiles):"))
        self._spin_t_rl = QSpinBox()
        self._spin_t_rl.setRange(0, 40)
        self._spin_t_rl.setValue(3)
        t_layout.addWidget(self._spin_t_rl)

        t_layout.addWidget(QLabel("Right width (tiles):"))
        self._spin_t_rw = QSpinBox()
        self._spin_t_rw.setRange(1, 10)
        self._spin_t_rw.setValue(1)
        t_layout.addWidget(self._spin_t_rw)

        t_layout.addWidget(QLabel("Stem direction:"))
        trot_widget = QWidget()
        trot_layout = QHBoxLayout(trot_widget)
        trot_layout.setContentsMargins(0, 0, 0, 0)
        trot_layout.setSpacing(4)
        self._t_rotation = 0
        self._t_rot_left_btn = QPushButton("◀")
        self._t_rot_left_btn.setFixedSize(32, 28)
        self._t_rot_left_btn.setToolTip("Rotate stem counter-clockwise")
        self._t_rot_lbl = QLabel()
        self._t_rot_lbl.setAlignment(Qt.AlignCenter)
        self._t_rot_lbl.setMinimumWidth(60)
        self._t_rot_right_btn = QPushButton("▶")
        self._t_rot_right_btn.setFixedSize(32, 28)
        self._t_rot_right_btn.setToolTip("Rotate stem clockwise")
        trot_layout.addWidget(self._t_rot_left_btn)
        trot_layout.addWidget(self._t_rot_lbl)
        trot_layout.addWidget(self._t_rot_right_btn)
        trot_layout.addStretch()
        self._update_t_rot_label()
        t_layout.addWidget(trot_widget)

        self._t_widget.setVisible(False)
        layout.addWidget(self._t_widget)

        layout.addStretch()

        # --- Connect signals ---
        self._type_group.buttonClicked.connect(self._on_type_changed)
        self._spin_len.valueChanged.connect(self._emit)
        self._spin_w.valueChanged.connect(self._emit)
        self._orient_group.buttonClicked.connect(self._emit)
        self._spin_lx.valueChanged.connect(self._emit)
        self._spin_ly.valueChanged.connect(self._emit)
        self._spin_lw.valueChanged.connect(self._emit)
        self._rot_left_btn.clicked.connect(self._rotate_left)
        self._rot_right_btn.clicked.connect(self._rotate_right)
        self._spin_t_sl.valueChanged.connect(self._emit)
        self._spin_t_sw.valueChanged.connect(self._emit)
        self._spin_t_ll.valueChanged.connect(self._emit)
        self._spin_t_lw.valueChanged.connect(self._emit)
        self._spin_t_rl.valueChanged.connect(self._emit)
        self._spin_t_rw.valueChanged.connect(self._emit)
        self._t_rot_left_btn.clicked.connect(self._t_rotate_left)
        self._t_rot_right_btn.clicked.connect(self._t_rotate_right)

    _CORNER_LABELS = ['top-left', 'top-right', 'bot-left', 'bot-right']
    _STEM_LABELS   = ['↓ down', '→ right', '↑ up', '← left']

    def _update_rot_label(self):
        self._rot_corner_lbl.setText(self._CORNER_LABELS[self._l_rotation])

    def _rotate_left(self):
        self._l_rotation = (self._l_rotation - 1) % 4
        self._update_rot_label()
        self._emit()

    def _rotate_right(self):
        self._l_rotation = (self._l_rotation + 1) % 4
        self._update_rot_label()
        self._emit()

    def _update_t_rot_label(self):
        self._t_rot_lbl.setText(self._STEM_LABELS[self._t_rotation])

    def _t_rotate_left(self):
        self._t_rotation = (self._t_rotation - 1) % 4
        self._update_t_rot_label()
        self._emit()

    def _t_rotate_right(self):
        self._t_rotation = (self._t_rotation + 1) % 4
        self._update_t_rot_label()
        self._emit()

    def _on_type_changed(self, *_):
        is_l = self._btn_l.isChecked()
        is_t = self._btn_t.isChecked()
        self._i_widget.setVisible(not is_l and not is_t)
        self._l_widget.setVisible(is_l)
        self._t_widget.setVisible(is_t)
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
                'rotation': self._l_rotation,
            }
        if self._btn_t.isChecked():
            return {
                'type': 'T',
                'stem_len':  self._spin_t_sl.value(),
                'stem_w':    self._spin_t_sw.value(),
                'left_len':  self._spin_t_ll.value(),
                'left_w':    self._spin_t_lw.value(),
                'right_len': self._spin_t_rl.value(),
                'right_w':   self._spin_t_rw.value(),
                'rotation':  self._t_rotation,
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
                self._btn_t.setChecked(False)
                self._i_widget.setVisible(True)
                self._l_widget.setVisible(False)
                self._t_widget.setVisible(False)
                self._spin_len.setValue(d.get('length', 3))
                self._spin_w.setValue(d.get('width', 1))
                orient = d.get('orientation', 'H')
                self._btn_h.setChecked(orient == 'H')
                self._btn_v.setChecked(orient == 'V')
            elif t == 'L':
                self._btn_l.setChecked(True)
                self._btn_i.setChecked(False)
                self._btn_t.setChecked(False)
                self._i_widget.setVisible(False)
                self._l_widget.setVisible(True)
                self._t_widget.setVisible(False)
                self._spin_lx.setValue(d.get('len_x', 3))
                self._spin_ly.setValue(d.get('len_y', 3))
                self._spin_lw.setValue(d.get('width', 1))
                self._l_rotation = d.get('rotation', 0) % 4
                self._update_rot_label()
            else:  # T
                self._btn_t.setChecked(True)
                self._btn_i.setChecked(False)
                self._btn_l.setChecked(False)
                self._i_widget.setVisible(False)
                self._l_widget.setVisible(False)
                self._t_widget.setVisible(True)
                self._spin_t_sl.setValue(d.get('stem_len', 3))
                self._spin_t_sw.setValue(d.get('stem_w', 1))
                self._spin_t_ll.setValue(d.get('left_len', 3))
                self._spin_t_lw.setValue(d.get('left_w', 1))
                self._spin_t_rl.setValue(d.get('right_len', 3))
                self._spin_t_rw.setValue(d.get('right_w', 1))
                self._t_rotation = d.get('rotation', 0) % 4
                self._update_t_rot_label()
        finally:
            self._suppress = False
