try:
    from PySide6.QtWidgets import *
except ImportError:
    try:
        from PyQt6.QtWidgets import *
    except ImportError:
        from PyQt5.QtWidgets import *

import zarr
from zarrview.ZarrViewer import ZarrViewer
import sys

# create app
app = QApplication(sys.argv)

# create a zarr group
root = zarr.group()

# create the UI
ui = ZarrViewer(root)
ui.show()

# run the app
status = app.exec()
sys.exit(status)