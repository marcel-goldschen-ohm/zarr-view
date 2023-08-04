# You only need to import the Qt version you installed.
# This is the sort of logic that zarrview uses to load Qt.
try:
    from PySide6.QtWidgets import *
except ImportError:
    try:
        from PyQt6.QtWidgets import *
    except ImportError:
        from PyQt5.QtWidgets import *

import sys
import zarr
from zarrview.ZarrViewer import ZarrViewer

# example zarr hierarchy (in-memory vs on-disk should not matter)
root = zarr.group()
foo = root.create_group('foo')
bar = foo.create_dataset('bar', shape=100, chunks=10)
baz = foo.create_group('baz')
quux = baz.create_dataset('quux', shape=200, chunks=20)

# attributes for quux
quux.attrs['a_int'] = 82
quux.attrs['a_float'] = 3.14
quux.attrs['a_bool'] = False
quux.attrs['a_str'] = 'zarr-view is awesome!'
quux.attrs['a_dict'] = {'a_child': 42}
quux.attrs['a_list'] = [8, 4.5, True, 'hello']

# create app
app = QApplication(sys.argv)

# init zarr viewer widget with root of hierarchy
viewer = ZarrViewer(root)
viewer.show()
viewer.setWindowTitle('ZarrViewer')

# run app
sys.exit(app.exec())