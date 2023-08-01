# zarr-view
PySide or PyQt tree model-view for a Zarr hierarchy

# Install
```
pip install zarrview
```

# Quick start example
```python
from PySide6.QtWidgets import QApplication
import numpy as np
import zarr
from zarrview.ZarrViewer import ZarrViewer
import sys

# example zarr hierarchy (in-memory vs on-disk should not matter)
root = zarr.group()
foo = root.create_group('foo')
bar = foo.create_dataset('bar', shape=100, chunks=10)
baz = root.create_group('baz')
quux = baz.create_dataset('quux', shape=200, chunks=20)

# create app
app = QApplication(sys.argv)

# create zarr viewer widget
viewer = ZarrViewer(root)
viewer.show()

# run app
sys.exit(app.exec())
```
