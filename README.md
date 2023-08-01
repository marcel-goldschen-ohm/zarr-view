# zarr-view
PySide or PyQt tree model-view for a Zarr hierarchy

# Install
1. Install either `PySide6>=6.5.2`, `PyQt6>=6.5.2`, or `PyQt5`. :warning: The Qt6 version requirements are due to a [bug](https://bugreports.qt.io/browse/QTBUG-115136) in `Qt6==6.5.1` that causes the tree view to crash on macOS arm64 chipset. If you are using a different OS, then you may be able to ignore these version requirements. For example:
```
pip install PySide6>=6.5.2
```
2. Install `zarrview`:
```
pip install zarrview
```

# Quick start example
```python
# Replace PySide6 with PyQt6 or PyQt5 depending on what Qt package you installed.
from PySide6.QtWidgets import QApplication
import sys
import zarr
from zarrview.ZarrViewer import ZarrViewer

# example zarr hierarchy (in-memory vs on-disk should not matter)
root = zarr.group()
foo = root.create_group('foo')
bar = foo.create_dataset('bar', shape=100, chunks=10)
baz = root.create_group('baz')
quux = baz.create_dataset('quux', shape=200, chunks=20)

# create app
app = QApplication(sys.argv)

# init zarr viewer widget with root of hierarchy
viewer = ZarrViewer(root)
viewer.show()

# run app
sys.exit(app.exec())
```
