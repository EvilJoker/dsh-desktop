"""panel/theme.py — 桌面助手设计 token + 全局 QSS。

v3.2 样式大改：
  - 单一来源：所有颜色/字号/圆角/间距都在这里
  - 控件通过 objectName 走全局 QSS，不要再 setStyleSheet 单点改
  - PyQt5 QSS 能力 < CSS：玻璃模糊/动画/box-shadow 都不支持，
    退化成纯半透 + 静态色 + 边框表达层次
"""

# ----------------------------------------------------------------------
# 设计 token
# ----------------------------------------------------------------------
T = {
    # ---- 背景 ----
    "bg_panel":      "rgba(20, 20, 28, 230)",       # panel 主体（更高 alpha）
    "bg_card":       "rgba(255, 255, 255, 6)",       # card 半透
    "bg_hover":      "rgba(255, 255, 255, 12)",      # hover 状态
    # v3.2.1：控件背景改成不透明 + 亮色（用户反馈太暗）
    "bg_input":      "#1f242f",                      # 输入框深色不透明
    "bg_input_focus": "#262b38",                     # 输入框 focus
    "bg_input_disabled": "#181c25",
    "bg_btn":        "#2c313e",                      # 玻璃按钮（不透明深灰）
    "bg_btn_hover":  "#363b4a",
    "bg_tab_active": "#2c313e",                      # 当前 tab
    "bg_tab_hover":  "rgba(255, 255, 255, 8)",

    # ---- 文字 ----
    "text_primary":   "#e8eaf0",
    "text_secondary": "rgba(255, 255, 255, 200)",
    "text_tertiary":  "rgba(255, 255, 255, 130)",
    "text_label":     "rgba(255, 255, 255, 90)",     # 卡片标题大写
    "text_code":      "#79c0ff",                      # code 内联

    # ---- 强调色 ----
    "accent":         "#6bb6ff",                      # tab 下划线、focus 边
    "accent_glow":    "rgba(99, 102, 241, 0.3)",     # 紫光晕（不直接用，参考）

    # ---- 状态 ----
    "ok":             "#4ade80",
    "ok_bg":          "rgba(74, 222, 128, 0.08)",
    "ok_border":      "rgba(74, 222, 128, 0.25)",
    "err":            "#f85149",
    "err_bg":         "rgba(248, 81, 73, 0.1)",
    "err_border":     "rgba(248, 81, 73, 0.2)",
    "warn":           "#d29922",

    # ---- 边框 ----
    "border":         "rgba(255, 255, 255, 10)",
    "border_strong":  "rgba(255, 255, 255, 20)",
    "border_btn":     "rgba(255, 255, 255, 24)",

    # ---- 圆角 ----
    "r_sm":   "6px",
    "r_md":   "8px",
    "r_lg":   "10px",
    "r_pill": "14px",
}


# ----------------------------------------------------------------------
# 全局 QSS（PyQt5 语法；box-shadow/animation/backdrop-filter 不支持，
# 退化为半透 + 边线 + hover 状态）
# ----------------------------------------------------------------------
GLOBAL_QSS = """
/* === 全局 === */
QWidget {
    color: %(text_primary)s;
    font-family: "Noto Sans CJK SC", "PingFang SC", "Microsoft YaHei", sans-serif;
    font-size: 12px;
}
QWidget:disabled {
    color: %(text_tertiary)s;
}

/* === 标题行（顶部） === */
QLabel#HeaderTitle {
    color: %(text_primary)s;
    font-size: 13px;
    font-weight: 600;
    background: transparent;
}
QLabel#ShortcutHint {
    color: rgba(255, 255, 255, 220);
    font-size: 10px;
    background: rgba(255, 255, 255, 8);
    border: 1px solid rgba(255, 255, 255, 15);
    border-radius: 4px;
    padding: 2px 7px;
    font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace;
}
QLabel#StatusLabel {
    font-size: 11px;
    padding: 3px 8px;
    border-radius: 6px;
    background: transparent;
    border: 1px solid transparent;
}
QLabel#StatusLabel[connected="true"] {
    color: %(ok)s;
    background: %(ok_bg)s;
    border: 1px solid %(ok_border)s;
}
QLabel#StatusLabel[connected="false"] {
    color: %(err)s;
    background: %(err_bg)s;
    border: 1px solid %(err_border)s;
}

/* === 关闭按钮（圆角幽灵） === */
QPushButton#CloseBtn {
    background: transparent;
    color: rgba(255, 255, 255, 130);
    border: none;
    border-radius: 13px;
    font-size: 14px;
    font-weight: 400;
}
QPushButton#CloseBtn:hover {
    background: rgba(248, 81, 73, 0.15);
    color: %(err)s;
}
QPushButton#CollapseBtn {
    background: transparent;
    color: rgba(255, 255, 255, 130);
    border: none;
    border-radius: 6px;
    font-size: 16px;
    font-weight: 400;
}
QPushButton#CollapseBtn:hover {
    background: rgba(255, 255, 255, 10);
    color: %(text_primary)s;
}

/* === Tab 栏（底部，玻璃药丸） === */
QPushButton#TabBtn {
    background: transparent;
    color: rgba(255, 255, 255, 180);
    border: 1px solid transparent;
    border-radius: 7px;
    padding: 0 12px;
    font-size: 11px;
    min-height: 28px;
}
QPushButton#TabBtn:hover {
    color: rgba(255, 255, 255, 240);
    background: %(bg_tab_hover)s;
}
QPushButton#TabBtn:checked {
    color: %(text_primary)s;
    background: %(bg_tab_active)s;
    border: 1px solid %(border_strong)s;
    font-weight: 600;
}

/* === 卡片 === */
QFrame#MetricsCard, QFrame#EventsCard, QFrame#ChatCard {
    background: %(bg_card)s;
    border: 1px solid %(border)s;
    border-radius: %(r_lg)s;
}
QLabel#CardTitle {
    color: %(text_label)s;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1px;
    background: transparent;
    border: none;
}

/* === 指标方块 === */
QFrame#MetricBox {
    background: rgba(255, 255, 255, 4);
    border: 1px solid %(border)s;
    border-radius: %(r_sm)s;
}
QLabel#MetricValue {
    font-size: 13px;
    font-weight: 600;
    background: transparent;
    border: none;
}
QLabel#MetricName {
    color: rgba(255, 255, 255, 200);
    font-size: 8px;
    background: transparent;
    border: none;
}
QLabel#Empty {
    color: rgba(255, 255, 255, 130);
    font-size: 11px;
    background: transparent;
}

/* === 事件 === */
QLabel#EventTime {
    color: rgba(255, 255, 255, 200);
    font-size: 10px;
    font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace;
    background: transparent;
}
QLabel#EventName {
    color: #d0d0d8;
    font-size: 11px;
    background: transparent;
}
QLabel#EventName[done="true"] {
    color: rgba(255, 255, 255, 100);
    text-decoration: line-through;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid rgba(255, 255, 255, 120);
    border-radius: 3px;
    background: rgba(255, 255, 255, 6);
}
QCheckBox::indicator:hover {
    border-color: %(accent)s;
}
QCheckBox::indicator:checked {
    background: %(ok)s;
    border-color: %(ok)s;
}

/* === Chat 输入框 === */
QLineEdit#ChatInput {
    background: %(bg_input)s;
    border: 1px solid %(border_strong)s;
    border-radius: %(r_md)s;
    color: %(text_primary)s;
    padding: 0 12px;
    selection-background-color: %(accent)s;
    font-size: 12px;
    min-height: 32px;
}
QLineEdit#ChatInput:focus {
    border: 1px solid %(accent)s;
    background: %(bg_input_focus)s;
}
QLineEdit#ChatInput:disabled {
    color: %(text_tertiary)s;
    background: %(bg_input_disabled)s;
}

/* === 玻璃按钮（"新会话" / "打开 web"） === */
QPushButton#GlassBtn {
    background: %(bg_btn)s;
    border: 1px solid %(border_strong)s;
    border-radius: %(r_md)s;
    color: %(text_primary)s;
    font-size: 14px;
    min-width: 32px;
    min-height: 32px;
    padding: 0 8px;
}
QPushButton#GlassBtn:hover {
    background: %(bg_btn_hover)s;
    border-color: %(border_btn)s;
}

/* === Chat 历史（透明 viewport） === */
QScrollArea#ChatScroll, QScrollArea#EventScroll {
    background: transparent;
    border: none;
}
QScrollArea#ChatScroll > QWidget > QWidget,
QScrollArea#EventScroll > QWidget > QWidget {
    background: transparent;
}

/* === Chat 气泡 === */
QLabel#BubbleUser {
    /* v3.2.1：user 气泡改成蓝紫色高对比，明显区分 panel 深底 */
    color: #ffffff;
    background: #3d4a6b;
    border: 1px solid #5a6a92;
    border-radius: 10px;
    border-bottom-right-radius: 4px;
    padding: 8px 12px;
    font-size: 12px;
}
QLabel#BubbleAssistant {
    /* v3.2.1：assistant 气泡调亮，对比更明显 */
    color: rgba(255, 255, 255, 240);
    background: rgba(255, 255, 255, 10);
    border: 1px solid rgba(255, 255, 255, 18);
    border-radius: 10px;
    border-bottom-left-radius: 4px;
    padding: 8px 12px;
    font-size: 12px;
}
QLabel#BubbleError {
    color: #ffd0cc;
    background: rgba(248, 81, 73, 0.18);
    border: 1px solid rgba(248, 81, 73, 0.4);
    border-radius: 10px;
    border-bottom-left-radius: 4px;
    padding: 8px 12px;
    font-size: 11px;
}

/* === 滚动条（v3.2.1 调亮、调宽，更易见） === */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 45);
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(255, 255, 255, 70);
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
    border: none;
    height: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: 6px;
}
QScrollBar::handle:horizontal {
    background: rgba(255, 255, 255, 20);
    border-radius: 3px;
    min-width: 30px;
}

/* === Strip 状态点（v3.2 走 QSS） === */
QLabel#StripStatusDot {
    border-radius: 3px;
    background: %(err)s;
}
QLabel#StripStatusDot[connected="true"] {
    background: %(ok)s;
}
QLabel#StripStatusDot[connected="false"] {
    background: %(err)s;
}
""" % T
