# zarr-view
PySide or PyQt tree model-view for a Zarr hierarchy

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

You can specify a specific path or path slice through the hierarchy to display (see the sections on [path slicing](#path-slicing) and [N-D arrays of ordered groups](#n-d-arrays-of-ordered-groups)):

<img src='images/quick-start-example-path.png' width=400>

You can dynamically reset the displayed hierarchy:
```python
viewer.setTree(baz)
```

# Path slicing
:construction:

Functions for Zarr hierarchy path slices are in `zarr_path_utils.py`.

Consider the following Zarr hierarchy where branches are groups and leaves are either groups or arrays:
```
/
└── foo
│   ├── bar
│   │   ├── baz
│   │   └── quux
│   └── foo
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
```
"foo/bar" ==>
/
└── foo
    └── bar
```

```
"*/baz" ==>
/
└── foo
│   └── baz
└── bar
    └── baz
```

```
"foo/*/baz" ==>
/
└── foo
    ├── bar
    │   └── baz
    └── foo
        └── baz
```

```
"foo/.../baz" ==>
/
└── foo
    ├── bar
    │   └── baz
    └── foo
    │   └── baz
    └── baz
        └── foo
            └── bar
                └── baz
```

```
".../bar" ==>
/
└── foo
│   └── bar
│   └── foo
│   │   └── bar
│   └── baz
│       └── foo
│           └── bar
└── bar
```

```
".../foo/bar/..." ==>
/
└── foo
    ├── bar
    │   ├── baz
    │   └── quux
    └── foo
    │   └── bar
    └── baz
        └── foo
            └── bar
                └── baz
                    └── quux
```

```
".../baz/quux" ==>
/
└── foo
    └── foo
    │   └── baz
    │       └── quux
    └── baz
        └── foo
            └── bar
                └── baz
                    └── quux
```

# N-D arrays of ordered groups
:construction:
