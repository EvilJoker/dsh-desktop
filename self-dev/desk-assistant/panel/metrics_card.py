"""panel/metrics_card.py — 指标卡片：横排小方块。"""
from PyQt5 import QtCore, QtWidgets


class MetricsCard(QtWidgets.QFrame):
    """接收 indicators 数组，渲染成横排小方块。

    用法：
        card = MetricsCard()
        card.update_indicators([{"id":"cpu","label":"CPU","value":77,"unit":"%","type":"progress"}, ...])
    """

    BOX_W = 58
    BOX_H = 44

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MetricsCard")
        # 样式走 theme.GLOBAL_QSS（#MetricsCard 选择器），不再 setStyleSheet

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 10)
        outer.setSpacing(6)

        title = QtWidgets.QLabel("指标 / METRICS")
        title.setObjectName("CardTitle")
        outer.addWidget(title)

        self._row = QtWidgets.QHBoxLayout()
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(8)
        self._row.setAlignment(QtCore.Qt.AlignLeft)
        outer.addLayout(self._row)
        # 不加 stretch 的话，QLabel title 默认 Preferred sizePolicy 会被 QVBoxLayout
        # 拉成全高，文字（默认 AlignVCenter）就会显示在 card 纵向中间。
        # 加 stretch(1) 把 title 顶在 card 顶部。
        outer.addStretch(1)

    def update_indicators(self, indicators):
        self._clear()
        if not indicators:
            empty = QtWidgets.QLabel("(无指标)")
            empty.setObjectName("Empty")
            self._row.addWidget(empty)
            return
        for ind in indicators:
            self._row.addWidget(self._make_box(ind))
        self._row.addStretch(1)

    def _clear(self):
        while self._row.count():
            item = self._row.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _make_box(self, ind):
        try:
            val = float(ind.get("value", 0))
        except (TypeError, ValueError):
            val = 0
        unit = str(ind.get("unit") or "")
        label = str(ind.get("label") or ind.get("id") or "")
        # v3.2：值颜色按阈值变化（保留旧逻辑：绿/黄/红）
        color = "#6bce82" if val < 70 else ("#f0c060" if val < 90 else "#e25c5c")
        value_str = f"{int(val)}{unit}" if val == int(val) else f"{val:.1f}{unit}"

        box = QtWidgets.QFrame()
        box.setObjectName("MetricBox")
        box.setFixedSize(self.BOX_W, self.BOX_H)
        # 样式走 theme.GLOBAL_QSS（#MetricBox 选择器）

        v = QtWidgets.QVBoxLayout(box)
        v.setContentsMargins(3, 3, 3, 3)
        v.setSpacing(0)

        val_lbl = QtWidgets.QLabel(value_str)
        val_lbl.setObjectName("MetricValue")
        # 用 inline style 覆盖 MetricValue 默认色（阈值变色）
        val_lbl.setStyleSheet(f"color: {color};")
        val_lbl.setAlignment(QtCore.Qt.AlignCenter)
        v.addWidget(val_lbl, 1)

        name_lbl = QtWidgets.QLabel(label)
        name_lbl.setObjectName("MetricName")
        name_lbl.setAlignment(QtCore.Qt.AlignCenter)
        v.addWidget(name_lbl)

        return box
