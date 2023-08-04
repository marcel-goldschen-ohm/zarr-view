"""
PySide or PyQt tree model/view for a Zarr hierarchy.

Each row of the tree corresponds to a Zarr (https://zarr.dev) group, array, or attr.
The first column is the tree representation of the Zarr hierarchy.
The second column is a representation of the data (i.e., array shape and dtype or attr value).

ZarrViewer is a widget that aims to provide similar functionality for Zarr
as does HDF5View for HDF5 files (https://www.hdfgroup.org/downloads/hdfview/).

There are also some additional features for supporting ordered arrays of Zarr groups.
e.g., You can view only a slice of the full hierarchy by specifying a path with
numpy-like indexing over ordered groups:
    "/path[:2]/to[5]/data" --> ["/path.0/to.5/data", "/path.1/to.5/data"]

TODO:
- check how non-zarr files are handled?
- allow multiple selection or selection ranges?
- edit arrays?
- simple text file support?
- optional data preview?
"""


__author__ = "Marcel P. Goldschen-Ohm"
__author_email__ = "goldschen-ohm@utexas.edu, marcel.goldschen@gmail.com"


try:
    from PySide6.QtCore import *
    from PySide6.QtGui import *
    from PySide6.QtWidgets import *
except ImportError:
    try:
        from PyQt6.QtCore import *
        from PyQt6.QtGui import *
        from PyQt6.QtWidgets import *
    except ImportError:
        from PyQt5.QtCore import *
        from PyQt5.QtGui import *
        from PyQt5.QtWidgets import *
    Signal = pyqtSignal
    Slot = pyqtSlot

import zarr
from zarrview import zarr_path_utils as zpu
import qtawesome as qta


class ZarrTreeItem:
    """ Each tree item corresponds to a zarr group, array, or attr.
    """

    def __init__(self, 
                 data: zarr.hierarchy.Group | zarr.core.Array | str | int, 
                 parent: 'ZarrTreeItem' = None
                 ):
        # data is one of the following:
        # - zarr.hierarchy.Group
        # - zarr.core.Array
        # - str key (attrs, dict) | int index (list)
        self.item_data = data
        self.parent_item = parent
        self.child_items = []
    
    def isgroup(self) -> bool:
        return isinstance(self.item_data, zarr.hierarchy.Group)
    
    def isarray(self) -> bool:
        return isinstance(self.item_data, zarr.core.Array)
    
    def isattr(self) -> bool:
        # str dict key or int list index
        return isinstance(self.item_data, str) | isinstance(self.item_data, int)
    
    def data(self, column: int):
        if column == 0:
            return self.key()
        elif column == 1:
            if self.isgroup():
                # no data for this row other than the group name in column 0
                return None
            if self.isarray():
                # array shape and dtype summary as in zarr tree printout
                zarray = self.item_data
                return f"{zarray.shape} {zarray.dtype}"
            if self.isattr():
                # attr value (only leaf attrs)
                if self.child_count() > 0:
                    # this is not a leaf attr (e.g., a dict or list)
                    return None
                return self.attr()
        return None

    def set_data(self, column: int, value) -> bool:
        if column == 0:
            return self.set_key(value)
        elif column == 1:
            if self.isgroup():
                # No data for this row other than the group name in column 0
                return False
            if self.isarray():
                # TODO: edit zarr array in popup table?
                return False
            if self.isattr():
                # attr value (only leaf attrs)
                if self.child_count() > 0:
                    # e.g., this is a dict or list
                    return False
                return self.set_attr(value)
        return False

    def key(self) -> str | int:
        if self.isgroup() or self.isarray():
            # group or array name from their path
            return self.item_data.name.strip('/').split('/')[-1]
        if self.isattr():
            # attr key/index
            return self.item_data
        return None
    
    def set_key(self, key: str | int) -> bool:
        if key == self.key():
            return False
        if self.isgroup() or self.isarray():
            key = str(key).strip().strip('/')
            if '/' in key:
                return False
            key = self.get_unique_key(key)
            # rename group or array hierarchy path
            old_path = self.item_data.path
            pos = old_path.rfind('/')
            new_path = old_path[:pos+1] + key
            if new_path == old_path:
                return False
            store = self.item_data.store
            try:
                store.rename(old_path, new_path)
            except:
                return False
            # reset this item to the new zarr object
            root_item = self.root()
            self.item_data = root_item.item_data[new_path]
            # reset all group and array items in the entire subtree
            for item in self.subtree_itemlist():
                old_item_path = item.item_data.path
                new_item_path = old_item_path.replace(old_path, new_path, 1)
                item.item_data = root_item.item_data[new_item_path]
            return True
        if self.isattr():
            obj, attr_keychain = self._get_attr_chain()
            if len(attr_keychain) == 1:
                # direct attr of group or array
                key = self.get_unique_key(str(key))
                obj.attrs[key] = obj.attrs.pop(attr_keychain[0])
                self.item_data = key
                return True
            else:
                # child attr of dict or list attr
                attr = obj.attrs[attr_keychain[0]]
                child_attr = attr
                for i in range(1, len(attr_keychain) - 1):
                    child_attr = child_attr[attr_keychain[i]]
                if isinstance(child_attr, dict):
                    key = self.get_unique_key(str(key))
                    child_attr[key] = child_attr.pop(attr_keychain[-1])
                    obj.attrs[attr_keychain[0]] = attr
                    self.item_data = key
                    return True
        return False
    
    def get_unique_key(self, key: str, include_self: bool = True) -> str:
        if self.parent_item is None:
            return key
        sibling_keys = []
        if self.isgroup() or self.isarray():
            sibling_keys = [item.key() for item in self.parent_item.child_items 
                            if (include_self or (item is not self)) and (item.isgroup() or item.isarray())]
        elif self.isattr():
            sibling_keys = [item.key() for item in self.parent_item.child_items 
                            if (include_self or (item is not self)) and item.isattr()]
        if key not in sibling_keys:
            return key
        key += '_1'
        i = 2
        while key in sibling_keys:
            pos = key.rfind('_')
            key = key[:pos+1] + str(i)
            i += 1
        return key
    
    def get_unique_child_key(self, key: str) -> str:
        child_keys = [item.key() for item in self.child_items if item.isgroup() or item.isarray()]
        if key not in child_keys:
            return key
        key += '_1'
        i = 2
        while key in child_keys:
            pos = key.rfind('_')
            key = key[:pos+1] + str(i)
            i += 1
        return key
    
    def get_unique_child_attr_key(self, key: str) -> str:
        child_keys = [item.key() for item in self.child_items if item.isattr()]
        if key not in child_keys:
            return key
        key += '_1'
        i = 2
        while key in child_keys:
            pos = key.rfind('_')
            key = key[:pos+1] + str(i)
            i += 1
        return key
    
    def attr(self):
        if not self.isattr():
            return None
        obj, attr_keychain = self._get_attr_chain()
        value = obj.attrs[attr_keychain[0]]
        for i in range(1, len(attr_keychain)):
            value = value[attr_keychain[i]]
        return value
    
    def set_attr(self, value) -> bool:
        if not self.isattr():
            return False
        obj, attr_keychain = self._get_attr_chain()
        if len(attr_keychain) == 1:
            obj.attrs[attr_keychain[0]] = value
            return True
        else:
            attr = obj.attrs[attr_keychain[0]]
            child_attr = attr
            for i in range(1, len(attr_keychain) - 1):
                child_attr = child_attr[attr_keychain[i]]
            child_attr[attr_keychain[-1]] = value
            obj.attrs[attr_keychain[0]] = attr
            return True
        return False
    
    def attr_parent_container(self) -> zarr.hierarchy.Group | zarr.core.Array | dict | list:
        obj, attr_keychain = self._get_attr_chain()
        value = obj.attrs[attr_keychain[0]]
        for i in range(1, len(attr_keychain) - 1):
            value = value[attr_keychain[i]]
        return value
    
    def _get_attr_chain(self) -> tuple[zarr.hierarchy.Group | zarr.core.Array, list[str | int]]:
        if not self.isattr():
            return None
        item = self
        attr_keychain = []
        while item.isattr() and item.parent_item:
            attr_keychain.insert(0, item.item_data)
            item = item.parent_item
        obj = item.item_data
        return obj, attr_keychain
    
    def add_existing_child_groups(self, isrecursive: bool = True):
        if not self.isgroup():
            return
        for name, group in self.item_data.groups():
            child_item = ZarrTreeItem(group, self)
            self.child_items.append(child_item)
            if isrecursive:
                child_item.add_existing_child_groups()
    
    def add_existing_child_arrays(self):
        if not self.isgroup():
            return
        for name, array in self.item_data.arrays():
            child_item = ZarrTreeItem(array, self)
            self.child_items.append(child_item)
    
    def add_existing_child_attrs(self, isrecursive: bool = True):
        if self.isgroup() or self.isarray():
            for key in self.item_data.attrs:
                child_item = ZarrTreeItem(str(key), self)
                self.child_items.append(child_item)
                if isrecursive:
                    child_item.add_existing_child_attrs()
        elif self.isattr():
            attr = self.attr()
            if isinstance(attr, dict):
                for key in attr:
                    child_item = ZarrTreeItem(str(key), self)
                    self.child_items.append(child_item)
                    if isrecursive:
                        child_item.add_existing_child_attrs()
            elif isinstance(attr, list):
                for i in range(len(attr)):
                    child_item = ZarrTreeItem(i, self)
                    self.child_items.append(child_item)
                    if isrecursive:
                        child_item.add_existing_child_attrs()
    
    def parent(self) -> 'ZarrTreeItem':
        return self.parent_item

    def child(self, number: int) -> 'ZarrTreeItem':
        if number < 0 or number >= len(self.child_items):
            return None
        return self.child_items[number]

    def last_child(self) -> 'ZarrTreeItem':
        return self.child_items[-1] if self.child_items else None

    def child_count(self) -> int:
        return len(self.child_items)

    def child_number(self) -> int:
        if self.parent_item:
            return self.parent_item.child_items.index(self)
        return 0

    def row(self) -> int:
        return self.child_number()
    
    def row_count(self) -> int:
        return self.child_count()

    def column_count(self) -> int:
        return 2

    def insert_child_group(self, position: int, key: str = None) -> bool:
        if position < 0 or position > len(self.child_items):
            return False
        
        if not self.isgroup():
            return False

        if key is None:
            key = 'new_group'
        else:
            key = str(key)
        key = self.get_unique_child_key(key)
        
        group = self.item_data.create_group(key)
        child_item = ZarrTreeItem(group, self)
        self.child_items.insert(position, child_item)
        return True
    
    def insert_child_attr(self, position: int, key: str | int = None, value = None) -> bool:
        if position < 0 or position > len(self.child_items):
            return False
        
        if self.isgroup() or self.isarray():
            if key is None:
                key = 'new_attr'
            else:
                key = str(key)
            key = self.get_unique_child_attr_key(key)
            self.item_data.attrs[key] = value
            child_item = ZarrTreeItem(key, self)
            self.child_items.insert(position, child_item)
            return True
        elif self.isattr():
            obj, attr_keychain = self._get_attr_chain()
            attr = obj.attrs[attr_keychain[0]]
            child_attr = attr
            for i in range(1, len(attr_keychain)):
                child_attr = child_attr[attr_keychain[i]]
            if isinstance(child_attr, dict):
                if key is None:
                    key = 'new_attr'
                else:
                    key = str(key)
                key = self.get_unique_child_attr_key(key)
                child_attr[key] = value
                obj.attrs[attr_keychain[0]] = attr
                child_item = ZarrTreeItem(key, self)
                self.child_items.insert(position, child_item)
                return True
            elif isinstance(child_attr, list):
                child_attr.insert(position, value)
                obj.attrs[attr_keychain[0]] = attr
                child_item = ZarrTreeItem(position, self)
                self.child_items.insert(position, child_item)
                # update indices of other child items
                for i in range(position + 1, len(self.child_items)):
                    self.child_items[i].item_data += 1
                return True
        return False
    
    def move_to(self, dst_parent: 'ZarrTreeItem', dst_position: int = None) -> bool:
        if not self.parent_item:
            return False
        # only allow moving groups and arrays to another group
        if not self.isgroup() and not self.isarray():
            return False
        if not dst_parent.isgroup():
            return False
        if not self.parent_item:
            # no move allowed
            return False
        if dst_parent is self.parent_item:
            # no move needed
            return False
        if dst_position is None or dst_position < 0:
            # default to appending as last child
            dst_position = dst_parent.child_count()
        
        src_key = self.key()
        dst_keys = [item.key() for item in dst_parent.child_items]
        if src_key in dst_keys:
            # TODO: ask to replace or keep both...
            return False
        
        # update zarr hierarchy
        root = self.root().item_data
        src_path = self.item_data.path
        dst_path = dst_parent.item_data.path + '/' + src_key
        try:
            root.store.rename(src_path, dst_path)
        except:
            return False
        
        # move item in hierarchy
        self.parent_item.child_items.remove(self)
        self.parent_item = dst_parent
        dst_parent.child_items.insert(dst_position, self)

        # reset all group and array items in the entire moved subtree
        for item in self.subtree_itemlist():
            if item.isgroup() or item.isarray():
                old_item_path = item.item_data.path
                new_item_path = old_item_path.replace(src_path, dst_path, 1)
                item.item_data = root[new_item_path]
        
        # print(root.tree())
        # self.root().dump()
        return True
    
    def insert_children(self, position: int, count: int, columns: int) -> bool:
        if position < 0 or position > len(self.child_items):
            return False

        for row in range(count):
            # default to inserting an undefined item
            item = ZarrTreeItem(None, self)
            self.child_items.insert(position, item)

        return True

    def remove_children(self, position: int, count: int) -> bool:
        if position < 0 or position + count > len(self.child_items):
            return False

        for row in range(count):
            # remove item's branch from tree
            item: ZarrTreeItem = self.child_items.pop(position)

            # delete associated object in zarr hierarchy
            if item.isgroup() or item.isarray():
                item.item_data.store.rmdir(item.item_data.path)
            elif item.isattr():
                key = item.item_data
                obj, attr_keychain = item._get_attr_chain()
                if len(attr_keychain) == 1:
                    # direct attr of group or array
                    del obj.attrs[key]
                else:
                    # child attr of dict or list attr
                    attr = obj.attrs[attr_keychain[0]]
                    child_attr = attr
                    for i in range(1, len(attr_keychain) - 1):
                        child_attr = child_attr[attr_keychain[i]]
                    del child_attr[key]
                    obj.attrs[attr_keychain[0]] = attr
                    if isinstance(child_attr, list):
                        # update indices of remaining child items
                        for i in range(position, len(self.child_items)):
                            self.child_items[i].item_data -= 1
        return True

    def insert_columns(self, position: int, columns: int) -> bool:
        # there are always two columns, non-negotiable
        return False

    def remove_columns(self, position: int, columns: int) -> bool:
        # there are always two columns, non-negotiable
        return False

    def __repr__(self) -> str:
        result = f"<ZarrTreeItem at 0x{id(self):x}"
        result += f", data={self.item_data}"
        result += f", {len(self.child_items)} children>"
        return result
    
    def root(self) -> 'ZarrTreeItem':
        item = self
        while item.parent() is not None:
            item = item.parent()
        return item
    
    def depth(self) -> int:
        depth = 0
        item = self
        while item.parent_item:
            depth += 1
            item = item.parent_item
        return depth
    
    def dump(self, indent='  '):
        total_indent = indent * self.depth()
        if self.isgroup():
            print(f"{total_indent}{self.key()}/")
        elif self.isarray():
            array: zarr.core.Array = self.item_data
            shape = ','.join([str(d) for d in array.shape])
            print(f"{total_indent}{self.key()} ({shape}) {array.dtype}")
        elif self.isattr():
            print(f"{total_indent}{self.key()}")
        for child_item in self.child_items:
            child_item.dump()
    
    def subtree_itemlist(self) -> list['ZarrTreeItem']:
        items = [self]
        for child_item in self.child_items:
            items.extend(child_item.subtree_itemlist())
        return items

    def subtree_zarrlist(self, 
                         include_arrays: bool = True, 
                         include_groups: bool = True
                         ) -> list[zarr.hierarchy.Group | zarr.core.Array]:
        zarr_objects = []
        for item in self.subtree_itemlist():
            if (include_groups and item.isgroup()) or (include_arrays and item.isarray()):
                zarr_objects.append(item.item_data)
        return zarr_objects


def build_tree(root: zarr.hierarchy.Group | zarr.core.Array, 
               path: str = None,
               include_attrs: bool = False, 
               include_arrays: bool = True, 
               include_groups: bool = True
               ) -> ZarrTreeItem:
    root_item = ZarrTreeItem(root)
    if path is None:
        if include_groups:
            root_item.add_existing_child_groups(isrecursive=True)
        if include_arrays:
            items = root_item.subtree_itemlist()
            for item in items:
                item.add_existing_child_arrays()
    else:
        leaves = zpu.find_leaves(root, path, include_arrays, include_groups)
        for leaf in leaves:
            leaf_path_parts = leaf.path.strip('/').split('/')
            item = root_item
            for i in range(len(leaf_path_parts)):
                obj_path = '/'.join(leaf_path_parts[:i+1])
                obj = root[obj_path]
                obj_in_tree = False
                for j in range(len(item.child_items)):
                    child_item = item.child_items[j]
                    if child_item.item_data == obj:
                        obj_in_tree = True
                        break
                if not obj_in_tree:
                    child_item = ZarrTreeItem(obj, item)
                    item.child_items.append(child_item)
                item = child_item
    if include_attrs:
        items = root_item.subtree_itemlist()
        for item in items:
            item.add_existing_child_attrs(isrecursive=True)
    return root_item


class ZarrTreeModel(QAbstractItemModel):

    infoChanged = Signal(QModelIndex)
    maxDepthChanged = Signal(int)
    
    def __init__(self,  
                 root: zarr.hierarchy.Group | zarr.core.Array, 
                 path: str = None,
                 include_attrs: bool = False, 
                 include_arrays: bool = True, 
                 include_groups: bool = True,
                 parent: QObject = None
                 ):
        QAbstractItemModel.__init__(self, parent)

        self.root_item = build_tree(root, path, include_attrs, include_arrays, include_groups)

    def reset_model(self, 
                    root: zarr.hierarchy.Group | zarr.core.Array = None, 
                    path: str = None,
                    include_attrs: bool = False, 
                    include_arrays: bool = True, 
                    include_groups: bool = True
                    ):
        if root is None:
            root = self.root_item.item_data
        
        self.beginResetModel()
        self.root_item = build_tree(root, path, include_attrs, include_arrays, include_groups)
        self.endResetModel()
    
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid() and parent.column() > 0:
            return 0

        parent_item: ZarrTreeItem = self.get_item(parent)
        if not parent_item:
            return 0
        return parent_item.child_count()

    def columnCount(self, parent: QModelIndex = None) -> int:
        return 2

    def get_item(self, index: QModelIndex = QModelIndex()) -> ZarrTreeItem:
        if index.isValid():
            item: ZarrTreeItem = index.internalPointer()
            if item:
                return item

        return self.root_item

    def parent(self, index: QModelIndex = QModelIndex()) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()

        child_item: ZarrTreeItem = self.get_item(index)
        if child_item:
            parent_item: ZarrTreeItem = child_item.parent()
        else:
            parent_item = None

        if parent_item == self.root_item or not parent_item:
            return QModelIndex()

        return self.createIndex(parent_item.child_number(), 0, parent_item)

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if parent.isValid() and parent.column() != 0:
            return QModelIndex()

        parent_item: ZarrTreeItem = self.get_item(parent)
        if not parent_item:
            return QModelIndex()

        child_item: ZarrTreeItem = parent_item.child(row)
        if child_item:
            return self.createIndex(row, column, child_item)
        return QModelIndex()

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if index == QModelIndex():
            # allow drag-n-grop onto root (viewport)
            return Qt.ItemFlag.ItemIsDropEnabled
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        item: ZarrTreeItem = self.get_item(index)

        if index.column() == 0:
            if item.isgroup() or item.isarray():
                return (Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
                        | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled)
            if item.isattr():
                if isinstance(item.attr_parent_container(), list):
                    # list indices are not editable
                    return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        elif index.column() == 1:
            if item.isgroup():
                # group has no value in column 1
                return Qt.ItemFlag.NoItemFlags
            if item.isattr():
                if item.child_count() > 0:
                    # not a leaf attr -> dict or list
                    return Qt.ItemFlag.NoItemFlags
                attr = item.attr()
                if isinstance(attr, dict) or isinstance(attr, list):
                    # dict or list do not have a directly editable value
                    return Qt.ItemFlag.NoItemFlags

        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable

    def data(self, index: QModelIndex, role: int = None):
        if not index.isValid():
            return None

        item: ZarrTreeItem = self.get_item(index)

        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            return item.data(index.column())
        
        if role == Qt.ItemDataRole.DecorationRole:
            if index.column() == 0:
                if item.isgroup():
                    return qta.icon('ph.folder-open-fill')
                elif item.isarray():
                    return qta.icon('ph.cube-thin')
                elif item.isattr():
                    value = item.attr()
                    if isinstance(value, dict):
                        return qta.icon('ph.folder-thin')
                    elif isinstance(value, list):
                        return qta.icon('ph.list-numbers-thin')

        return None

    def setData(self, index: QModelIndex, value, role: int) -> bool:
        if role != Qt.EditRole:
            return False

        item: ZarrTreeItem = self.get_item(index)
        result: bool = item.set_data(index.column(), value)

        if not result:
            return False
        
        # # if we changed the index of an attr in a list,
        # # we need to update all items in the list
        # if (index.column() == 0) and (item.parent() is not None) and item.isattr() \
        # and isinstance(item.attr_parent_container(), list):
        #     parent_index = self.parent(index)
        #     num_children = item.parent().child_count()
        #     top_left_index = self.index(0, 0, parent_index)
        #     bottom_right_index = self.index(num_children - 1, 1, parent_index)
        #     self.dataChanged.emit(top_left_index, bottom_right_index, 
        #                         [Qt.DisplayRole, Qt.EditRole])
        #     return True

        self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])

        if (index.column() == 0) and (item.isgroup() or item.isarray()):
            # zaar object path has changed
            self.infoChanged.emit(index)

        return True

    def headerData(self, 
                   section: int, 
                   orientation: Qt.Orientation,
                   role: int = Qt.DisplayRole
                   ):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.root_item.data(section)

        return None

    def setHeaderData(self, section: int, orientation: Qt.Orientation, value,
                      role: int = None) -> bool:
        if role != Qt.EditRole or orientation != Qt.Horizontal:
            return False

        result: bool = self.root_item.set_data(section, value)

        if result:
            self.headerDataChanged.emit(orientation, section, section)

        return result

    def insert_group(self, position: int, key: str = None, parent: QModelIndex = QModelIndex()) -> bool:
        parent_item: ZarrTreeItem = self.get_item(parent)
        if not parent_item or not parent_item.isgroup():
            return False

        self.beginInsertRows(parent, position, position)
        success: bool = parent_item.insert_child_group(position, key)
        self.endInsertRows()

        return success
    
    def insert_attribute(self, position: int, key: str | int = None, value = None,
                        parent: QModelIndex = QModelIndex()) -> bool:
        parent_item: ZarrTreeItem = self.get_item(parent)
        if not parent_item:
            return False
        
        if key is None and parent_item.isattr() and isinstance(parent_item.item_data, list):
            key = position

        self.beginInsertRows(parent, position, position)
        success: bool = parent_item.insert_child_attr(position, key, value)
        self.endInsertRows()

        return success
    
    def insertRows(self, position: int, rows: int,
                   parent: QModelIndex = QModelIndex()) -> bool:
        parent_item: ZarrTreeItem = self.get_item(parent)
        if not parent_item:
            return False

        self.beginInsertRows(parent, position, position + rows - 1)
        column_count = self.root_item.column_count()
        success: bool = parent_item.insert_children(position, rows, column_count)
        self.endInsertRows()

        return success

    def removeRows(self, position: int, rows: int,
                   parent: QModelIndex = QModelIndex()) -> bool:
        parent_item: ZarrTreeItem = self.get_item(parent)
        if not parent_item:
            return False

        self.beginRemoveRows(parent, position, position + rows - 1)
        success: bool = parent_item.remove_children(position, rows)
        self.endRemoveRows()

        return success

    def insertColumns(self, position: int, columns: int,
                      parent: QModelIndex = QModelIndex()) -> bool:
        self.beginInsertColumns(parent, position, position + columns - 1)
        success: bool = self.root_item.insert_columns(position, columns)
        self.endInsertColumns()

        return success

    def removeColumns(self, position: int, columns: int,
                      parent: QModelIndex = QModelIndex()) -> bool:
        self.beginRemoveColumns(parent, position, position + columns - 1)
        success: bool = self.root_item.remove_columns(position, columns)
        self.endRemoveColumns()

        if self.root_item.column_count() == 0:
            self.removeRows(0, self.rowCount())

        return success

    def moveRow(self, sourceParent: QModelIndex, sourceRow: int,
                destinationParent: QModelIndex, destinationChild: int):
        if sourceParent == destinationParent:
            return False
        if sourceRow < 0 or sourceRow >= self.rowCount(sourceParent):
            return False
        # destinationChild = -1 --> append as last child
        if destinationChild < -1 or destinationChild > self.rowCount(destinationParent):
            return False

        source_parent_item = self.get_item(sourceParent)
        source_item = source_parent_item.child(sourceRow)
        dest_parent_item = self.get_item(destinationParent)
        
        self.beginMoveRows(sourceParent, sourceRow, sourceRow, destinationParent, destinationChild)
        success: bool = source_item.move_to(dest_parent_item, destinationChild)
        self.endMoveRows()
        return success
    
    def supportedDropActions(self) -> Qt.DropActions:
        return Qt.DropAction.MoveAction #| Qt.DropAction.CopyAction
    
    """ unused stuff for drag-n-drop
    # def mimeTypes(self) -> list[str]:
    #     return ['ZarrTreeItem']
    
    # def mimeData(self, indexes: list[QModelIndex]) -> QMimeData:
    #     self._internalMoveData = indexes

    #     print('--------------------')
    #     print('mimeData:')
    #     for index in indexes:
    #         item = self.get_item(index)
    #         print(item.item_data)
    #     print('--------------------')

    #     # encode ZarrTreeItem into a QByteArray
    #     # encoded_data = QByteArray()
    #     # stream = QDataStream(encoded_data, QIODevice.WriteOnly)
    #     # stream.writeInt(len(indexes))
    #     # for index in indexes:
    #     #     item: ZarrTreeItem = self.get_item(index)
    #     #     stream.writeQVariant(QVariant(item))

    #     # data = QMimeData()
    #     # data.setData('InternalMove', encoded_data)
    #     # return data
    
    #     return QMimeData()
    
    # def canDropMimeData(self, data: QMimeData, action: Qt.DropAction, 
    #                     row: int, column: int, parent: QModelIndex) -> bool:
    #     if getattr(self, '_internalMoveData', None) is None:
    #         print('no')
    #         return False
    #     # if not data.hasFormat('InternalMove'):
    #     #     return False

    #     if column != 0:
    #         # only drop on first column with tree hierarchy
    #         print('no')
    #         return False

    #     print('yes')
    #     return True
    
    # def dropMimeData(self, data: QMimeData, action: Qt.DropAction,
    #                  row: int, column: int, parent: QModelIndex) -> bool:
    #     print('dropMimeData')
    #     if not self.canDropMimeData(data, action, row, column, parent):
    #         return False
        
    #     if action == Qt.DropAction.IgnoreAction:
    #         return False
        
    #     src_indexes = getattr(self, '_internalMoveData', None)
    #     if src_indexes is None:
    #         return False
    #     # print(src_indexes[0].row(), src_indexes[0].column())
        
    #     dst_parent_item = self.get_item(parent)
    #     # print(dst_parent_item.item_data.tree())
    #     for i, src_index in enumerate(src_indexes):
    #         src_parent_index = self.parent(src_index)
    #         # src_parent_item = self.get_item(src_parent_index)
    #         # src_item = self.get_item(src_index)
    #         # print(src_item.item_data.tree())
    #         self.moveRow(src_parent_index, src_index.row(), parent, row + i)
        
    #     # encoded_data: QByteArray = data.data('InternalMove')
    #     # stream = QDataStream(encoded_data, QIODevice.ReadOnly)
    #     # num_items = stream.readInt()
    #     # print(num_items)
    #     # for i in range(num_items):
    #     #     item = ZarrTreeItem(stream.readQVariant())
    #     #     print(item)
    #     #     item.move_to(parent_item, row + i)
    #     self._internalMoveMimeData = None
    #     print('... dropMimeData')
    #     return True
    """
    
    def _repr_recursion(self, item: ZarrTreeItem, indent: int = 0) -> str:
        result = " " * indent + repr(item) + "\n"
        for child in item.child_items:
            result += self._repr_recursion(child, indent + 2)
        return result

    def __repr__(self) -> str:
        return self._repr_recursion(self.root_item)
    
    def max_depth(self) -> int:
        max_depth = 0
        items = self.root_item.subtree_itemlist()
        for item in items:
            depth = item.depth()
            if depth > max_depth:
                max_depth = depth
        return max_depth

    def dump(self):
        self.root_item.dump()


class ZarrTreeView(QTreeView):
    def __init__(self, parent: QWidget = None):
        QTreeView.__init__(self, parent)
        
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setAnimated(False)
        self.setAllColumnsShowFocus(True)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.onCustomContextMenuRequested)

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        # self.setDefaultDropAction(Qt.MoveAction)
        self.setDragDropMode(QAbstractItemView.InternalMove)
    
    @Slot(QPoint)
    def onCustomContextMenuRequested(self, pos: QPoint):
        index: QModelIndex = self.indexAt(pos)
        if not index.isValid():
            return
        menu = self.context_menu(index)
        if menu:
            menu.exec(self.viewport().mapToGlobal(pos))
    
    def context_menu(self, index: QModelIndex = QModelIndex()) -> QMenu:
        if not index.isValid():
            return None
        
        model: ZarrTreeModel = self.model()
        item: ZarrTreeItem = model.get_item(index)

        if item.isgroup() or item.isarray():
            menu = QMenu()
            menu.addAction('Insert Group', lambda: self.insert_group(index))
            # menu.addAction('Insert Array')
            if item.parent() is item.root() and item.parent().child_count() == 1:
                # Don't allow deleting the final child of root
                # as this will result in an empty tree.
                return menu
            menu.addSeparator()
            menu.addAction('Delete', lambda: self.remove_row(index))
            return menu
        elif item.isattr():
            menu = QMenu()
            insertAttrMenu = menu.addMenu('Insert Attribute')
            insertAttrMenu.addAction('str', lambda: self.insert_attribute(index, None, ''))
            insertAttrMenu.addAction('int', lambda: self.insert_attribute(index, None, 0))
            insertAttrMenu.addAction('float', lambda: self.insert_attribute(index, None, 0.0))
            insertAttrMenu.addAction('dict', lambda: self.insert_attribute(index, None, {}))
            insertAttrMenu.addAction('list', lambda: self.insert_attribute(index, None, []))
            attr = item.attr()
            if isinstance(attr, dict) or isinstance(attr, list):
                menu.addSeparator()
                appendChildAttrMenu = menu.addMenu('Append Child Attribute')
                appendChildAttrMenu.addAction('str', lambda: self.append_child_attribute(index, None, ''))
                appendChildAttrMenu.addAction('int', lambda: self.append_child_attribute(index, None, 0))
                appendChildAttrMenu.addAction('float', lambda: self.append_child_attribute(index, None, 0.0))
                appendChildAttrMenu.addAction('dict', lambda: self.append_child_attribute(index, None, {}))
                appendChildAttrMenu.addAction('list', lambda: self.append_child_attribute(index, None, []))
            menu.addSeparator()
            menu.addAction('Delete Attribute', lambda: self.remove_row(index))
            return menu
    
    def insert_group(self, index: QModelIndex, path: str = None):
        model: ZarrTreeModel = self.model()
        model.insert_group(index.row(), path, index.parent())
    
    def insert_attribute(self, index: QModelIndex, key: str | int = None, value = None):
        model: ZarrTreeModel = self.model()
        model.insert_attribute(index.row(), key, value, index.parent())
    
    def append_child_attribute(self, index: QModelIndex, key: str | int = None, value = None):
        model: ZarrTreeModel = self.model()
        item: ZarrTreeItem = model.get_item(index)
        model.insert_attribute(item.child_count(), key, value, index)
    
    def remove_row(self, index: QModelIndex):
        model: ZarrTreeModel = self.model()
        model.removeRows(index.row(), 1, index.parent())
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        index: QModelIndex = event.source().currentIndex()
        # model: ZarrTreeModel = self.model()
        # item: ZarrTreeItem = model.get_item(index)
        # print(item)
        # print(event.dropAction() == Qt.DropAction.MoveAction)
        # print(event.dropAction() == Qt.DropAction.CopyAction)
        if index and index != QModelIndex():
            self._indexBeingDragged = index
            event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent):
        src_index: QModelIndex = getattr(self, '_indexBeingDragged', None)
        if not src_index or src_index == QModelIndex():
            return
        dst_index: QModelIndex = self.indexAt(event.pos()) # TODO: event.position() in Qt6?
        if not dst_index:
            return
        
        model: ZarrTreeModel = self.model()
        src_parent_index = model.parent(src_index)
        src_row = src_index.row()
        dst_parent_index = model.parent(dst_index)
        dst_row = dst_index.row()

        drop_pos = self.dropIndicatorPosition()
        dst_item = model.get_item(dst_index)
        if drop_pos == QAbstractItemView.OnItem:
            # print('OnItem')
            if dst_item.isgroup():
                # append src_index as last child of dst_index
                dst_parent_index = dst_index
                dst_row = model.rowCount(dst_parent_index)
            # otherwise insert src_index as prior sibling of dst_index
            pass
        elif drop_pos == QAbstractItemView.AboveItem:
            # print('AboveItem')
            # insert src_index as prior sibling of dst_index
            pass
        elif drop_pos == QAbstractItemView.BelowItem:
            # print('BelowItem')
            # insert src_index as sibling just after dst_index
            dst_row += 1
        elif drop_pos == QAbstractItemView.OnViewport:
            # print('OnViewport')
            # append src_index as last child of root
            dst_parent_index = QModelIndex()
            dst_row = model.rowCount(dst_parent_index)

        old_max_depth = model.max_depth()
        model.moveRow(src_parent_index, src_row, dst_parent_index, dst_row)
        moved_index = model.index(dst_row, 0, dst_parent_index)
        model.infoChanged.emit(moved_index)
        new_max_depth = model.max_depth()
        if new_max_depth != old_max_depth:
            model.maxDepthChanged.emit(new_max_depth)
        self._indexBeingDragged = None


class ZarrViewer(QSplitter):
    def __init__(self, root: zarr.hierarchy.Group | zarr.core.Array, path: str = None):
        QSplitter.__init__(self)

        self.hierarchy_model = ZarrTreeModel(root, 
                                             path=path, 
                                             include_attrs=False, 
                                             include_arrays=True, 
                                             include_groups=True)
        self.hierarchy_view = ZarrTreeView()
        self.hierarchy_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.hierarchy_view.setModel(self.hierarchy_model)
        self.hierarchy_view.expandAll()

        self.attr_model = ZarrTreeModel(root, 
                                        path=path, 
                                        include_attrs=True, 
                                        include_arrays=False, 
                                        include_groups=False)
        self.attr_view = ZarrTreeView()
        self.attr_view.setModel(self.attr_model)
        self.attr_view.expandAll()

        self.pathLineEdit = QLineEdit()
        if path is not None:
            self.pathLineEdit.setText(path)
        self.pathLineEdit.setToolTip('Path')
        self.pathLineEdit.editingFinished.connect(self.onPathChanged)

        self.expandToDepthSpinBox = QSpinBox()
        max_depth = self.hierarchy_model.max_depth()
        self.expandToDepthSpinBox.setMinimum(0)
        self.expandToDepthSpinBox.setMaximum(max_depth - 1)
        self.expandToDepthSpinBox.setToolTip('Expand to Depth')
        self.expandToDepthSpinBox.valueChanged.connect(self.expandToDepth)

        self.collapseAllButton = QToolButton()
        self.collapseAllButton.setFixedSize(16, 16)
        self.collapseAllButton.setIcon(qta.icon('mdi6.arrow-collapse-left'))
        self.collapseAllButton.setToolTip('Collapse All')
        self.collapseAllButton.clicked.connect(self.collapseAll)

        self.expandAllButton = QToolButton()
        self.expandAllButton.setFixedSize(16, 16)
        self.expandAllButton.setIcon(qta.icon('mdi6.arrow-expand-right'))
        self.expandAllButton.setToolTip('Expand All')
        self.expandAllButton.clicked.connect(self.expandAll)

        pathSliceLayout = QHBoxLayout()
        pathSliceLayout.setContentsMargins(5, 0, 0, 0)
        pathSliceLayout.setSpacing(5)
        pathSliceLayout.addWidget(QLabel('/'))
        pathSliceLayout.addWidget(self.pathLineEdit)

        hierarchyDepthLayout = QHBoxLayout()
        hierarchyDepthLayout.setContentsMargins(5, 0, 0, 0)
        hierarchyDepthLayout.setSpacing(5)
        hierarchyDepthLayout.addWidget(self.collapseAllButton)
        hierarchyDepthLayout.addWidget(self.expandAllButton)
        hierarchyDepthLayout.addWidget(self.expandToDepthSpinBox)
        hierarchyDepthLayout.addStretch()

        hierarchy_wrapper = QWidget()
        vbox = QVBoxLayout(hierarchy_wrapper)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        vbox.addLayout(pathSliceLayout)
        vbox.addLayout(hierarchyDepthLayout)
        vbox.addWidget(self.hierarchy_view)

        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.updateInfo(root)

        tabs = QTabWidget()
        tabs.addTab(self.attr_view, 'Attributes')
        tabs.addTab(self.info_text, 'Info')
        tabs.setCurrentIndex(1)

        self.setOrientation(Qt.Orientation.Vertical)
        self.addWidget(hierarchy_wrapper)
        self.addWidget(tabs)

        self.setStretchFactor(0, 2)
        self.setStretchFactor(1, 1)

        self.hierarchy_view.selectionModel().selectionChanged.connect(self.onSelectionChanged)
        self.hierarchy_model.infoChanged.connect(self.onInfoChanged)
        self.hierarchy_model.maxDepthChanged.connect(self.onMaxDepthChanged)

        self.collapseAll()
    
    def setTree(self, root: zarr.hierarchy.Group | zarr.core.Array, path: str = None):
        self.hierarchy_model.reset_model(root, 
                                         path=path, 
                                         include_attrs=False, 
                                         include_arrays=True, 
                                         include_groups=True)

        self.hierarchy_view.selectionModel().clearSelection()
        self.hierarchy_view.selectionModel().selectionChanged.connect(self.onSelectionChanged)

        max_depth = self.hierarchy_model.max_depth()
        self.expandToDepthSpinBox.setMaximum(max_depth - 1)
        self.collapseAll()

        self.attr_model.reset_model(root, 
                                    path=None, 
                                    include_attrs=True, 
                                    include_arrays=False, 
                                    include_groups=False)
        self.attr_view.expandAll()

        self.updateInfo(root)
    
    def updateInfo(self, obj: zarr.hierarchy.Group | zarr.core.Array):
        # print(obj.info_items())
        self.info_text.setPlainText(str(obj.info))
    
    @Slot()
    def onSelectionChanged(self):
        indexes: list[QModelIndex] = self.hierarchy_view.selectionModel().selectedIndexes()
        if not indexes:
            obj = None
        else:
            # first index will be the item for column 0 in the selected row
            item: ZarrTreeItem = self.hierarchy_model.get_item(indexes[0])
            # item will be for either a zarr group or array
            obj = item.item_data
        self.attr_model.reset_model(obj, 
                                    path=None, 
                                    include_attrs=True, 
                                    include_arrays=False, 
                                    include_groups=False)
        self.attr_view.expandAll()
        for col in range(2):
            self.attr_view.resizeColumnToContents(col)
        self.updateInfo(obj)
    
    @Slot()
    def onPathChanged(self):
        root = self.hierarchy_model.root_item.item_data
        path = self.pathLineEdit.text().strip()
        if path == '':
            path = None
        self.setTree(root, path)
    
    @Slot()
    def collapseAll(self):
        self.hierarchy_view.collapseAll()
        if self.expandToDepthSpinBox.value() != 0:
            self.expandToDepthSpinBox.valueChanged.disconnect(self.expandToDepth)
            self.expandToDepthSpinBox.setValue(0)
            self.expandToDepthSpinBox.valueChanged.connect(self.expandToDepth)
    
    @Slot()
    def expandAll(self):
        self.hierarchy_view.expandAll()
        for col in range(2):
            self.hierarchy_view.resizeColumnToContents(col)
        max_depth = self.expandToDepthSpinBox.maximum()
        if self.expandToDepthSpinBox.value() != max_depth:
            self.expandToDepthSpinBox.valueChanged.disconnect(self.expandToDepth)
            self.expandToDepthSpinBox.setValue(max_depth)
            self.expandToDepthSpinBox.valueChanged.connect(self.expandToDepth)
    
    @Slot(int)
    def expandToDepth(self, depth: int = None):
        if depth is None:
            depth = self.expandToDepthSpinBox.value()
        if depth == 0:
            self.collapseAll()
        elif depth < 0 or depth >= self.expandToDepthSpinBox.maximum():
            self.expandAll()
        else:
            self.hierarchy_view.expandToDepth(depth - 1)
            for col in range(2):
                self.hierarchy_view.resizeColumnToContents(col)
            if self.expandToDepthSpinBox.value() != depth:
                self.expandToDepthSpinBox.valueChanged.disconnect(self.expandToDepth)
                self.expandToDepthSpinBox.setValue(depth)
                self.expandToDepthSpinBox.valueChanged.connect(self.expandToDepth)
    
    @Slot(QModelIndex)
    def onInfoChanged(self, index: QModelIndex):
        self.onSelectionChanged()
    
    @Slot(int)
    def onMaxDepthChanged(self, max_depth: int):
        self.expandToDepthSpinBox.setMaximum(max_depth - 1)
