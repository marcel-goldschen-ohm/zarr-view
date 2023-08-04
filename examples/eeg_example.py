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
import numpy as np

# example zarr hierarchy for a dataset consisting of EEG recordings across 100 trials and 64 probes
# where each recorded waveform is a time series with 2000 samples.
root = zarr.group()
for i in range(100):
    trial = root.create_group(f'trial.{i}')
    trial.attrs['reward_probability'] = np.random.random()
    for j in range(64):
        probe = trial.create_group(f'probe.{j}')
        probe.attrs['location_xyz_mm'] = list(np.random.random(3) * 100)
        eeg_waveform = probe.create_dataset('eeg_waveform', shape=2000, chunks=1000)

# create app
app = QApplication(sys.argv)

# init zarr viewer widget with root of hierarchy
viewer = ZarrViewer(root)
viewer.show()
viewer.setWindowTitle('ZarrViewer')

# run app
sys.exit(app.exec())