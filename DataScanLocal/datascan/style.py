STYLE = """
* { font-family: 'Microsoft YaHei UI', 'Microsoft YaHei', 'Segoe UI'; font-size: 12px; }
QMainWindow { background: #f3f6fb; }
QWidget { color: #24334b; }
QFrame#rail { background: #182943; border: none; }
QLabel#brand { color: #ffffff; font-size: 24px; font-weight: 800; }
QLabel#brandSub { color: #91a6c4; font-size: 11px; }
QLabel#railCaption { color: #7c94b6; font-size: 10px; letter-spacing: 2px; }
QLabel#railFoot { color: #8ca2c0; font-size: 11px; }
QPushButton#nav { background: transparent; color: #aebed5; text-align: left; padding: 13px 16px; border: 0; border-radius: 7px; font-size: 13px; }
QPushButton#nav:checked { background: #2c4467; color: #ffffff; font-weight: 600; }
QPushButton#nav:hover { background: #233b5d; }
QFrame#header { background: #ffffff; border-bottom: 1px solid #e1e7f0; }
QLabel#title { font-size: 21px; font-weight: 700; color: #1b2b46; }
QLabel#subtitle { color: #8190a5; font-size: 11px; }
QLabel#pill { color: #33836e; background: #eaf6f1; padding: 6px 11px; border-radius: 11px; font-size: 11px; }
QFrame#files { background: #ffffff; border-right: 1px solid #e1e7f0; }
QLabel#sectionTitle { font-weight: 700; font-size: 13px; }
QLabel#muted { color: #8090a5; font-size: 11px; }
QLabel#eyebrow { color: #7c8da7; font-size: 10px; letter-spacing: 1px; }
QLabel#largeTitle { font-size: 24px; font-weight: 700; color: #203553; }
QFrame#card { background: #ffffff; border: 1px solid #e1e7f0; border-radius: 9px; }
QLabel#cardNumber { font-family: 'Segoe UI'; font-size: 30px; font-weight: 600; }
QLabel#cardLabel { color: #7d8ba1; font-size: 11px; }
QFrame#panel { background: #ffffff; border: 1px solid #e0e6ef; border-radius: 9px; }
QLabel#hint { color: #8b6a35; background: #fff9ed; border: 1px solid #f0e5cc; border-radius: 6px; padding: 9px 12px; font-size: 11px; }
QPushButton { background: #ffffff; border: 1px solid #d9e1ed; padding: 8px 14px; border-radius: 6px; color: #465a79; }
QPushButton:hover { background: #eef3fd; border-color: #b2c5f3; }
QPushButton:pressed { background: #e5edff; }
QPushButton:disabled { color: #a6b1c1; background: #f1f4f8; border-color: #e1e7ef; }
QPushButton#primary { background: #365fdc; border-color: #365fdc; color: white; font-weight: 600; }
QPushButton#primary:hover { background: #284dc6; }
QPushButton#primary:disabled { background: #b1bfe6; border-color: #b1bfe6; }
QPushButton#subtle { background: transparent; border: none; color: #627a9e; padding: 5px; }
QPushButton:focus { border: 2px solid #6a8ae8; }
QTreeWidget { border: none; background: white; outline: none; font-size: 11px; }
QTreeWidget::item { padding: 7px 2px; }
QTreeWidget::item:selected { background: #edf2ff; color: #315bd1; }
QTableView, QTableWidget { background: white; alternate-background-color: #f8faff; border: 0; gridline-color: #eaf0f7; selection-background-color: #eaf0ff; selection-color: #2b4a9d; outline: none; }
QTableView::item { padding: 6px; border-bottom: 1px solid #edf1f6; }
QHeaderView::section { background: #f7f9fd; color: #7c8ca3; padding: 9px 8px; border: none; border-bottom: 1px solid #e4eaf3; font-size: 11px; }
QLineEdit, QPlainTextEdit, QSpinBox, QComboBox { background: white; border: 1px solid #dce4f0; border-radius: 5px; padding: 7px; selection-background-color: #dbe6ff; }
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus { border-color: #5e82e5; }
QComboBox { min-width: 100px; }
QComboBox::drop-down { border: none; width: 22px; }
QCheckBox { spacing: 8px; color: #596e8d; }
QCheckBox::indicator { width: 14px; height: 14px; }
QProgressBar { border: none; background: #e6edfa; border-radius: 3px; max-height: 6px; }
QProgressBar::chunk { background: #3d6be6; border-radius: 3px; }
QStatusBar { background: white; border-top: 1px solid #e1e7f0; color: #788ba7; font-size: 11px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { width: 8px; background: transparent; }
QScrollBar::handle:vertical { background: #d0dbea; border-radius: 4px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { height: 8px; background: transparent; }
QScrollBar::handle:horizontal { background: #d0dbea; border-radius: 4px; min-width: 24px; }
QSplitter::handle { background: #f0f4fa; width: 7px; }
QToolTip { color: #24334b; background: #ffffff; border: 1px solid #cbd7e8; padding: 6px; }
QDialog { background: #f7f9fd; }
"""
