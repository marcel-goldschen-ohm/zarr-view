try:
    from PySide6.QtWidgets import *
except ImportError:
    try:
        from PyQt6.QtWidgets import *
    except ImportError:
        from PyQt5.QtWidgets import *

from zarrview.ZarrViewer import ZarrViewer
import sys

# create app
app = QApplication(sys.argv)

# create the UI
ui = ZarrViewer()
ui.show()

# run the app
status = app.exec()
sys.exit(status)