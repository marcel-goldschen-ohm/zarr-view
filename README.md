# zarr-view
PySide or PyQt tree model-view for a Zarr hierarchy

- [Install](#install)
- [Quick start example](#quick-start-example)
- [Path slice](#path-slice)
- [Path slice for N-D arrays of nested ordered groups](#path-slice-for-n-d-arrays-of-nested-ordered-groups)

# Install
1. Install either `"PySide6>=6.5.2"`, `"PyQt6>=6.5.2"`, or `PyQt5`. :warning: The Qt6 version requirements are due to a [Qt6.5.1 bug](https://bugreports.qt.io/browse/QTBUG-115136) that causes the tree view to crash on macOS arm64 chipset. If you are using a different OS, then this bug may not apply to you and you may be able to ignore these version requirements. For example:
```
pip install "PySide6>=6.5.2"
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

# Here the viewer is shown in its own window.
# However, it can also be inserted int a Qt app just like any QWidget.
viewer.show()
viewer.setWindowTitle('ZarrViewer')

# run app
sys.exit(app.exec())
```

The viewer displays a tree view of the Zaar hierarchy groups and arrays along with a representation of each arrays size and data type.

Selecting a group or array in the tree view of the Zarr hierarchy displays the info for the selected object below the tree:

<img src='images/quick-start-example-info.png' width=400>

The selected object's attributes can also be viewed and edited in their own tree view below the main hierarchy view:

<img src='images/quick-start-example-attrs.png' width=400>

You can insert new attributes or delete attributes via the viewer:

<img src='images/quick-start-example-insert-attr.png' width=400>

Toolbar buttons allow quickly collapsing or expanding the tree to any level:

<img src='images/quick-start-example-collapse-all.png' width=400>

<img src='images/quick-start-example-expand-all.png' width=400>

<img src='images/quick-start-example-expand-1.png' width=400>

You can insert new groups or delete groups or arrays via the viewer:

<img src='images/quick-start-example-insert-group.png' width=400>

You can rename all groups, arrays, and attrs:

<img src='images/quick-start-example-rename.png' width=400>

You can drag and drop groups or arrays to restructure the hierarchy:

<img src='images/quick-start-example-drag.png' width=400>

<img src='images/quick-start-example-drop.png' width=400>

You can specify a specific path or path slice to view only a subset of the hierarchy (see the sections on [path slice](#path-slice) and [path slice for N-D arrays of nested ordered groups](#path-slice-for-n-d-arrays-of-nested-ordered-groups)):

<img src='images/quick-start-example-path.png' width=400>

You can dynamically reset the displayed hierarchy:
```python
viewer.setTree(new_root)
```

# Path slice
It can be useful to view only a subset of a large hierarchy. This can be done in the `ZarrViewer` widget by specifying a path or path slice to view. 

All functions for Zarr hierarchy path slices are in `zarr_path_utils.py` which is independent of the Qt model-view classes in `ZarrViewer.py`. Thus, these path utilities may be useful outside of the Qt tree model-view interface. The paths in a slice are found by regex matching paths in the hierarchy.

Consider the following Zarr hierarchy where branches are groups and leaves are either groups or arrays:
```
/
├── foo
│   ├── bar
│   │   ├── baz
│   │   └── quux
│   ├── foo
│   │   ├── bar
│   │   └── baz
│   │       └── quux
│   └── baz
│       ├── quux
│       └── foo
│           └── bar
│               └── baz
│                   └── quux
└── bar
    ├── baz
    └── quux
```

The following are examples of specifying a subset of the above hierarchy using a path slice:

`"foo/bar"`:
```
/
└── foo
    └── bar
```

`"*/baz"`:
```
/
├── foo
│   └── baz
└── bar
    └── baz
```

`"foo/*/baz"`:
```
/
└── foo
    ├── bar
    │   └── baz
    └── foo
        └── baz
```

`"foo/.../baz"`:
```
/
└── foo
    ├── bar
    │   └── baz
    ├── foo
    │   └── baz
    └── baz
        └── foo
            └── bar
                └── baz
```

`".../bar"`:
```
/
├── foo
│   ├── bar
│   ├── foo
│   │   └── bar
│   └── baz
│       └── foo
│           └── bar
└── bar
```

`".../foo/bar/..."`:
```
/
└── foo
    ├── bar
    │   ├── baz
    │   └── quux
    ├── foo
    │   └── bar
    └── baz
        └── foo
            └── bar
                └── baz
                    └── quux
```

`".../baz/quux"`:
```
/
└── foo
    ├── foo
    │   └── baz
    │       └── quux
    └── baz
        └── foo
            └── bar
                └── baz
                    └── quux
```

Note that the path slice functions actually return only the Zarr objects at the matched paths:
```
".../baz/quux" -> ["foo/foo/baz/quux", "foo/baz/foo/bar/baz/quux"]
```
However, the subtree containing the matched paths as indicated above is easily reconstructed in the viewer.

# Path slice for N-D arrays of nested ordered groups
:construction:

Consider the following example dataset for EEG recordings from two subjects across 100 trials and 64 probes where each recorded waveform is a time series with 2000 samples:
```python
import zarr

root = zarr.group()
for subject_name in ['subject_A', 'subject_B']:
    subject = root.create_group(subject_name)
    for i in range(100):
        trial = subject.create_group(f'trial.{i}')
        for j in range(64):
            probe = trial.create_group(f'probe.{j}')
            location = probe.create_dataset('location_xyz', shape=3)
            location.attrs['units'] = 'mm'
            eeg = probe.create_dataset('eeg', shape=2000)
            eeg.attrs['units'] = 'uV'
            eeg.attrs['sample_freq_kHz'] = 1.0
```
In the above example we chose to split each EEG waveform 1-D time series array across a nested hierarchy of trials and probes, where the ordering of the trials and probes is contained in the group paths (e.g., `trial.3/`, `trial.3/probe.42/`).

Alternatively, we could have stored all of the EEGs for a given subject in a single 3-D array of shape (#trials, #probes, #samples) and another array of locations for each probe. However, the hierarchy of explicit groups for each trial and probe has some important advantages over the 3-D array:

|  | trial.i/probe.j/eeg tree | eeg[trial,probe,sample] 3-D array |
|- | -------------------------| --------------------------------- |
| Add a note that subject was distracted during a specific trial. | Trivial to add the note to the trial group. The association is also obvious to a naive program that doesn't understand the concept of a trial. | Requires associating the note with the specific trial via, for example, an index. This can be a pain to manage and may be non-trivial to convey the association to a naive program without specific conventions. |
| Remove artifactual recordings for a damaged probe. | Simply remove the probe's folder from each trial. |  |
| ? | ? | ? |
