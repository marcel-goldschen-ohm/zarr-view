try:
    from PySide6.QtWidgets import *
except ImportError:
    try:
        from PyQt6.QtWidgets import *
    except ImportError:
        from PyQt5.QtWidgets import *

import numpy as np
import zarr
from zarrview.ZarrViewer import ZarrViewer
import sys

# create app
app = QApplication(sys.argv)

# create example zarr hierarchy in memory
root = zarr.group()
root.create_dataset('run.0/sweep.0/channel.0/trace.0/xdata', shape=1)
root.create_dataset('run.0/sweep.0/channel.0/trace.0/ydata', shape=1000)
root.create_dataset('run.0/sweep.0/channel.1/trace.0/xdata', shape=1)
root.create_dataset('run.0/sweep.0/channel.1/trace.0/ydata', shape=1000)
root.create_dataset('run.0/sweep.1/channel.0/trace.0/xdata', shape=1)
root.create_dataset('run.0/sweep.1/channel.0/trace.0/ydata', shape=1000)
root.create_dataset('run.0/sweep.1/channel.1/trace.0/xdata', shape=1)
root.create_dataset('run.0/sweep.1/channel.1/trace.0/ydata', shape=1000)
root.create_dataset('run.1/sweep.0/channel.0/trace.0/xdata', shape=1)
root.create_dataset('run.1/sweep.0/channel.0/trace.0/ydata', shape=1000)
root.create_dataset('run.1/sweep.0/channel.1/trace.0/xdata', shape=1)
root.create_dataset('run.1/sweep.0/channel.1/trace.0/ydata', shape=1000)
root.create_dataset('run.1/sweep.1/channel.0/trace.0/xdata', shape=1)
root.create_dataset('run.1/sweep.1/channel.0/trace.0/ydata', shape=1000)
root.create_dataset('run.1/sweep.1/channel.1/trace.0/xdata', shape=1)
root.create_dataset('run.1/sweep.1/channel.1/trace.0/ydata', shape=1000)
trace = root['run.0/sweep.0/channel.0/trace.0']
trace.attrs['test'] = 82
trace.attrs['xzero'] = {'a': 5.2, 'b': 'hello', 'c': [10, 82, 3.3]}
ydata = root['run.0/sweep.0/channel.0/trace.0/ydata']
ydata.attrs['ok'] = True
root.create_dataset('run.0/sweep.1/test', shape=(3,3))
# print(root.tree())

# copy in-memory zarr hierarchy to disk
file_root = zarr.open_group('zarr-view-test-example.zarr', 'w')
zarr.copy_store(root.store, file_root.store, if_exists='replace')
file_root = zarr.open_group('zarr-view-test-example.zarr')

# load zarr hierarchy from disk into viewer
viewer = ZarrViewer(file_root)
viewer.show()

# run app
status = app.exec()
sys.exit(status)