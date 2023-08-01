"""zarr_path_utils.py
"""


import re
import zarr


def index_exp(exp: str) -> tuple[int | list[int] | slice]:
    """ Convert index expression string to tuple of slices or index lists for each dimension.

    exp: Index expression string (i.e., what you would put inside [] for indexing as in numpy).
        Currently only supports slices, single indexes, and flat 1-D lists of indices.
        More advanced indexing is not yet supported.

    e.g.,
        exp = ':2, [5, 7, 8], 9, 1:3, :'
        -> (
              slice(None, 2, None),
              [5, 7, 8],
              9,
              slice(1, 3, None),
              slice(None, None, None)
            )
    """
    
    # split each comma-separated index expression for each dimension into separate parts
    parts = re.split(r',(?=[^\]]*(?:\[|$))', exp)
    
    # convert each part to a slice or list of indices
    slices = []
    for part in parts:
        part = part.strip()
        if part.startswith('[') and part.endswith(']'):
            # list of comma-separated explicit indices
            slices.append(
                [int(i) for i in part[1:-1].split(',')]
            )
        elif ':' in part:
            # slice
            slices.append(
                slice(*(int(i) if i else None for i in part.split(':')))
            )
        else:
            # single index
            slices.append(
                int(part)
            )
    return tuple(slices)

def test_index_exp():
    all_ok = True

    for exp, slices in [
        ['5', (5,)],
        [':5', (slice(None, 5),)],
        ['::2', (slice(None, None, 2),)],
        ['5::2', (slice(5, None, 2),)],
        [':', (slice(None),)],
        [' : ', (slice(None),)],
        [':2, [5, 7, 8], 1:3, :', (slice(None, 2), [5, 7, 8], slice(1, 3), slice(None))],
        ['[5, 7, 8]', ([5, 7, 8],)],
        ['[5, 7, 8], 6', ([5, 7, 8], 6)],
        [':, [5, 7, 8]', (slice(None), [5, 7, 8])],
        ['5, 7, 8', (5, 7, 8)]
    ]:
        ind = index_exp(exp)
        ok = ind == slices
        print('OK' if ok else 'FAIL', exp, '->', ind)
        if not ok:
            all_ok = False
    
    return all_ok


def name_index_exp(exp: str) -> tuple[str, tuple[int | list[int] | slice]]:
    """ parse name[index_exp] string for name and slices/indices
    
    e.g.,
        exp = 'group[1:3, 14, [5, 7, 8]]'
        -> ('group', (slice(1, 3, None), 14, [5, 7, 8]))
    """
    if exp.endswith(']'):
        pos = exp.find('[')
        if pos != -1:
            name = exp[:pos].strip()
            ind = exp[pos+1:-1]
            return name, index_exp(ind)
    return exp, ()

def test_name_index_exp():
    all_ok = True

    exp = 'group[:, 1:3, 2, [5, 7, 8]]'
    name, slices = name_index_exp(exp)
    ok = name == 'group' and slices == (slice(None), slice(1, 3), 2, [5, 7, 8])
    print('OK' if ok else 'FAIL', exp, '->', name, slices)
    if not ok:
        all_ok = False
    
    return all_ok


def slice_path(path: str) -> tuple[tuple[str, tuple[int | list[int] | slice]]]:
    """ return path parts and slices/indices from path string

    e.g. path = 'project/run[0]/sweep[:2,3]/channel[[1,4,6]]/trace[:]'
        -> (
            ('project', ()), 
            ('run', (slice(0, None, None),)), 
            ('sweep', (slice(None, 2, None), slice(3, None, None))), 
            ('channel', ([1,4,6],)), 
            ('trace', (slice(None, None, None),))
            )
    """
    return tuple(name_index_exp(part.strip()) for part in path.strip('/').split('/'))

def test_slice_path():
    all_ok = True

    path = 'project/run[0]/sweep[:2,3]/channel[[1,4,6]]/trace[:]'
    pathslices = slice_path(path)
    ok = pathslices == (
        ('project', ()), 
        ('run', (0,)), 
        ('sweep', (slice(None, 2), 3)), 
        ('channel', ([1,4,6],)), 
        ('trace', (slice(None),))
    )
    print('OK' if ok else 'FAIL', path, '->', pathslices)
    if not ok:
        all_ok = False

    path = 'project'
    pathslices = slice_path(path)
    ok = pathslices == (
        ('project', ()),
    )
    print('OK' if ok else 'FAIL', path, '->', pathslices)
    if not ok:
        all_ok = False

    return all_ok


def path_slice_regex(path: str | tuple[tuple[str, tuple[int | list[int] | slice]]]
                     ) -> tuple[str, list[slice]]:
    """ Constructs a regex for matching paths in the input path slice.

        Returns the regex plus all slices associated with capture groups in the regex.
        This is because there is no unambiguous regex for slices without a specified stop.
        For such slices, the index in the path is captured.
        Thus, for any paths that match the regex one must also check that all
        captured indexes are in their associated slices.
    """
    if isinstance(path, str):
        # convert path string to slice path
        path = slice_path(path)
    regex = ''
    capture_group_slices = []
    for name, indices in path:
        if name == '...' and indices == ():
            # match any number of any charachters
            # TODO: this could probably be more restrictive as paths only have certain allowed charachters
            regex += '.+'
        elif name == '*' and indices == ():
            # match anything for just this one level of the hierarchy
            # TODO: this could probably be more restrictive as paths only have certain allowed charachters
            regex += '[^/]+/'
        elif indices == ():
            # must match the specified path name
            regex += name + '/'
        else:
            # name[index expression]
            regex += name
            for ind in indices:
                if isinstance(ind, int):
                    # only the specified index
                    regex += '\\.' + str(ind)
                elif isinstance(ind, list):
                    # only one of the specified indices
                    regex += '\\.(?:' + '|'.join([str(i) for i in ind]) + ')'
                elif isinstance(ind, slice):
                    if ind == slice(None, None, None):
                        # any index
                        regex += '\\.[0-9]+'
                    elif ind.stop is None:
                        # we have to capture this index and also return its associated slice
                        # so we can check it later to see if it is in the slice
                        regex += '\\.([0-9]+)'
                        capture_group_slices.append(ind)
                    else:
                        # only one of the specified indices
                        indexes = range(*ind.indices(ind.stop))
                        regex += '\\.(?:' + '|'.join([str(i) for i in indexes]) + ')'
            regex += '/'
    return regex.strip('/'), capture_group_slices

def path_in_slice(path: str, path_slice: str | tuple[str, list[slice]]) -> bool:
    if isinstance(path_slice, str):
        regex, group_slices = path_slice_regex(path_slice)
    else:
        regex, group_slices = path_slice  # output from path_slice_regex
    result = re.fullmatch(regex, path)
    if result is None:
        return False
    for group, group_slice in zip(result.groups(), group_slices):
        index = int(group)
        if index not in range(*group_slice.indices(index + 1)):
            return False
    return True

def test_path_in_slice():
    all_ok = True

    path_slice = 'run[0]/sweep[:]/channel[1:]/trace[:]'
    path = 'run.0/sweep.1/channel.1'
    isin = path_in_slice(path, path_slice)
    ok = isin == False
    print('OK' if ok else 'FAIL', path, 'in' if isin else 'not in', path_slice)
    if not ok:
        all_ok = False

    path_slice = '.../channel[1:]/...'
    path = 'run.0/sweep.1/channel.1/trace.2'
    isin = path_in_slice(path, path_slice_regex(path_slice))
    ok = isin == True
    print('OK' if ok else 'FAIL', path, 'in' if isin else 'not in', path_slice)
    if not ok:
        all_ok = False

    path_slice = '.../channel[1:]/...'
    path = 'run.0/sweep.1/channel.1/trace.2'
    isin = path_in_slice(path, path_slice)
    ok = isin == True
    print('OK' if ok else 'FAIL', path, 'in' if isin else 'not in', path_slice)
    if not ok:
        all_ok = False

    path_slice = '.../channel[1:]/...'
    path = 'run.0/sweep.1/channel.0/trace.2'
    isin = path_in_slice(path, path_slice)
    ok = isin == False
    print('OK' if ok else 'FAIL', path, 'in' if isin else 'not in', path_slice)
    if not ok:
        all_ok = False

    path_slice = 'run[0]/sweep.1/channel[1:]/trace[:]'
    path = 'run.0/sweep.1/channel.1/trace.2'
    isin = path_in_slice(path, path_slice)
    ok = isin == True
    print('OK' if ok else 'FAIL', path, 'in' if isin else 'not in', path_slice)
    if not ok:
        all_ok = False

    path_slice = 'run[0]/sweep[:]/channel[1:]/trace[:]'
    path = 'run.0/sweep.1/channel.1/trace.2'
    isin = path_in_slice(path, path_slice)
    ok = isin == True
    print('OK' if ok else 'FAIL', path, 'in' if isin else 'not in', path_slice)
    if not ok:
        all_ok = False

    path_slice = 'run[0]/sweep[:]/channel[1:]/trace[:]'
    path = 'run.0/sweep.1/channel.0/trace.2'
    isin = path_in_slice(path, path_slice)
    ok = isin == False
    print('OK' if ok else 'FAIL', path, 'in' if isin else 'not in', path_slice)
    if not ok:
        all_ok = False

    path_slice = 'run[0]/sweep[:,3,4:]/channel[1:]/trace[:]'
    path = 'run.0/sweep.1.3.6/channel.2/trace.8'
    isin = path_in_slice(path, path_slice)
    ok = isin == True
    print('OK' if ok else 'FAIL', path, 'in' if isin else 'not in', path_slice)
    if not ok:
        all_ok = False

    path_slice = 'run[0]/sweep[:,3,4:]/channel[1:]/trace[:]'
    path = 'run.0/sweep.1.3/channel.2/trace.8'
    isin = path_in_slice(path, path_slice)
    ok = isin == False
    print('OK' if ok else 'FAIL', path, 'in' if isin else 'not in', path_slice)
    if not ok:
        all_ok = False

    path_slice = 'run[0]/sweep[:,3,4:]/channel[1:]/trace[:]'
    path = 'run.0/sweep.1.3.6/channel.2/'
    isin = path_in_slice(path, path_slice)
    ok = isin == False
    print('OK' if ok else 'FAIL', path, 'in' if isin else 'not in', path_slice)
    if not ok:
        all_ok = False

    path_slice = 'run[0]/sweep[0]/channel[0]/trace[:]'
    path = 'run.0/sweep.0/channel.0/trace.0/ydata'
    isin = path_in_slice(path, path_slice)
    ok = isin == False
    print('OK' if ok else 'FAIL', path, 'in' if isin else 'not in', path_slice)
    if not ok:
        all_ok = False

    return all_ok


def find_first(root: zarr.hierarchy.Group, name: str, include_arrays: bool = True, include_groups: bool = True) -> zarr.hierarchy.Group | zarr.core.Array | None:
    def _find_first(obj):
        if isinstance(obj, zarr.core.Array) and not include_arrays:
            return
        if isinstance(obj, zarr.hierarchy.Group) and not include_groups:
            return
        objname = obj.path.strip('/').split('/')[-1]
        if name == objname or name == objname.split('.')[0]:
            return obj
    
    return root.visitvalues(_find_first)

def test_find_first():
    root = zarr.group()
    root.create_dataset('run.0/sweep.0/channel.0/trace.0/ydata', shape=1000)
    root.create_dataset('run.0/sweep.0/channel.0/trace.1/ydata', shape=1000)
    root.create_dataset('run.0/sweep.0/channel.0/trace.2/ydata', shape=1000)
    root.create_dataset('run.0/sweep.0/channel.1/trace.0/ydata', shape=1000)
    root.create_dataset('run.0/sweep.0/channel.1/trace.1/ydata', shape=1000)
    root.create_dataset('run.0/sweep.0/channel.1/trace.2/ydata', shape=1000)
    root.create_dataset('run.0/sweep.1/channel.0/trace.0/ydata', shape=1000)
    root.create_dataset('run.0/sweep.1/channel.0/trace.1/ydata', shape=1000)
    root.create_dataset('run.0/sweep.1/channel.1/trace.0/ydata', shape=1000)
    root.create_dataset('run.0/sweep.1/channel.1/trace.1/ydata', shape=1000)
    print(root.tree())

    all_ok = True

    obj = find_first(root, 'ydata')
    trueobj = root['run.0/sweep.0/channel.0/trace.0/ydata']
    ok = obj == trueobj
    print('OK' if all_ok else 'FAIL', 'ydata', '->', obj)
    if not ok:
        all_ok = False

    obj = find_first(root, 'channel.1')
    trueobj = root['run.0/sweep.0/channel.1']
    ok = obj == trueobj
    print('OK' if ok else 'FAIL', 'channel.1', '->', obj)
    if not ok:
        all_ok = False

    obj = find_first(root, 'ydata', include_arrays=False)
    ok = obj is None
    print('OK' if ok else 'FAIL', 'ydata include_arrays=False', '->', obj)
    if not ok:
        all_ok = False

    obj = find_first(root, 'channel.1', include_groups=False)
    ok = obj is None
    print('OK' if ok else 'FAIL', 'channel.1 include_groups=False', '->', obj)
    if not ok:
        all_ok = False
    
    return all_ok


def find_all(root: zarr.hierarchy.Group, name: str, include_arrays: bool = True, include_groups: bool = True) -> list[zarr.hierarchy.Group | zarr.core.Array]:
    objects = []

    def _find_all(obj):
        if isinstance(obj, zarr.core.Array) and not include_arrays:
            return
        if isinstance(obj, zarr.hierarchy.Group) and not include_groups:
            return
        objname = obj.path.strip('/').split('/')[-1]
        if name == objname or name == objname.split('.')[0]:
            objects.append(obj)
    
    root.visitvalues(_find_all)
    return objects

def test_find_all():
    root = zarr.group()
    root.create_dataset('run.0/sweep.0/channel.0/trace.0/ydata', shape=1000)
    root.create_dataset('run.0/sweep.0/channel.0/trace.0/trace.0/ydata', shape=1000)
    root.create_dataset('run.0/sweep.0/channel.0/trace.1/ydata', shape=1000)
    root.create_dataset('run.0/sweep.0/channel.0/trace.2/ydata', shape=1000)
    root.create_dataset('run.0/sweep.0/channel.1/trace.0/ydata', shape=1000)
    root.create_dataset('run.0/sweep.0/channel.1/trace.1/ydata', shape=1000)
    root.create_dataset('run.0/sweep.0/channel.1/trace.2/ydata', shape=1000)
    root.create_dataset('run.0/sweep.1/channel.0/trace.0/ydata', shape=1000)
    root.create_dataset('run.0/sweep.1/channel.0/trace.1/ydata', shape=1000)
    root.create_dataset('run.0/sweep.1/channel.1/trace.0/ydata', shape=1000)
    root.create_dataset('run.0/sweep.1/channel.1/trace.1/ydata', shape=1000)
    print(root.tree())

    all_ok = True

    objs = find_all(root['run.0/sweep.0/channel.0'], 'trace')
    trueobjs = (
        root['run.0/sweep.0/channel.0/trace.0'],
        root['run.0/sweep.0/channel.0/trace.0/trace.0'],
        root['run.0/sweep.0/channel.0/trace.1'],
        root['run.0/sweep.0/channel.0/trace.2']
    )
    ok = tuple(objs) == trueobjs
    print('OK' if ok else 'FAIL', 'run.0/sweep.0/channel.0', 'trace', '->', objs)
    if not ok:
        all_ok = False

    objs = find_all(root['run.0/sweep.0/channel.0'], 'ydata')
    trueobjs = (
        root['run.0/sweep.0/channel.0/trace.0/trace.0/ydata'],
        root['run.0/sweep.0/channel.0/trace.0/ydata'],
        root['run.0/sweep.0/channel.0/trace.1/ydata'],
        root['run.0/sweep.0/channel.0/trace.2/ydata']
    )
    ok = tuple(objs) == trueobjs
    print('OK' if ok else 'FAIL', 'run.0/sweep.0/channel.0', 'ydata', '->', objs)
    if not ok:
        all_ok = False

    objs = find_all(root['run.0/sweep.0/channel.0'], 'trace', include_groups=False)
    ok = tuple(objs) == ()
    print('OK' if ok else 'FAIL', 'run.0/sweep.0/channel.0', 'trace include_groups=False', '->', objs)
    if not ok:
        all_ok = False

    objs = find_all(root['run.0/sweep.0/channel.0'], 'ydata', include_arrays=False)
    ok = tuple(objs) == ()
    print('OK' if ok else 'FAIL', 'run.0/sweep.0/channel.0', 'ydata include_arrays=False', '->', objs)
    if not ok:
        all_ok = False
    
    return all_ok


def find_leaves(root: zarr.hierarchy.Group, path_slice: str, 
                include_arrays: bool = True, include_groups: bool = True
                ) -> list[zarr.hierarchy.Group | zarr.core.Array]:
    regex, group_slices = path_slice_regex(path_slice)
    objects = []

    def _find_leaves(obj):
        if isinstance(obj, zarr.core.Array) and not include_arrays:
            return
        if isinstance(obj, zarr.hierarchy.Group) and not include_groups:
            return
        if path_in_slice(obj.path.strip('/'), (regex, group_slices)):
            if path_slice.endswith('...'):
                # only accept true leaves
                if not isinstance(obj, zarr.hierarchy.Group) or len(obj.keys()) == 0:
                    objects.append(obj)
            else:
                objects.append(obj)
    
    root.visitvalues(_find_leaves)
    return objects

def test_find_leaves():
    root = zarr.group()
    root.create_dataset('run.0/sweep.0/channel.0/trace.0/ydata', shape=1000)
    root.create_dataset('run.0/sweep.0/channel.0/trace.1/ydata', shape=1000)
    root.create_dataset('run.0/sweep.0/channel.0/trace.2/ydata', shape=1000)
    root.create_dataset('run.0/sweep.0/channel.1/trace.0/ydata', shape=1000)
    root.create_dataset('run.0/sweep.0/channel.1/trace.1/ydata', shape=1000)
    root.create_dataset('run.0/sweep.0/channel.1/trace.2/ydata', shape=1000)
    root.create_dataset('run.0/sweep.1/channel.0/trace.0/ydata', shape=1000)
    root.create_dataset('run.0/sweep.1/channel.0/trace.1/ydata', shape=1000)
    root.create_dataset('run.0/sweep.1/channel.1/trace.0/ydata', shape=1000)
    root.create_dataset('run.0/sweep.1/channel.1/trace.1/ydata', shape=1000)
    print(root.tree())

    all_ok = True

    path = '.../channel[0]/trace[:]'
    leaves = find_leaves(root, path)
    ok = tuple(leaves) == (
        root['run.0/sweep.0/channel.0/trace.0'],
        root['run.0/sweep.0/channel.0/trace.1'],
        root['run.0/sweep.0/channel.0/trace.2'],
        root['run.0/sweep.1/channel.0/trace.0'],
        root['run.0/sweep.1/channel.0/trace.1']
    )
    print('OK' if ok else 'FAIL', path, '->', leaves)
    if not ok:
        all_ok = False

    path = 'run[0]/sweep[1]/...'
    leaves = find_leaves(root, path)
    ok = tuple(leaves) == (
        root['run.0/sweep.1/channel.0/trace.0/ydata'],
        root['run.0/sweep.1/channel.0/trace.1/ydata'],
        root['run.0/sweep.1/channel.1/trace.0/ydata'],
        root['run.0/sweep.1/channel.1/trace.1/ydata']
    )
    print('OK' if ok else 'FAIL', path, '->', leaves)
    if not ok:
        all_ok = False

    path = 'run[0]/.../trace.1'
    leaves = find_leaves(root, path)
    ok = tuple(leaves) == (
        root['run.0/sweep.0/channel.0/trace.1'],
        root['run.0/sweep.0/channel.1/trace.1'],
        root['run.0/sweep.1/channel.0/trace.1'],
        root['run.0/sweep.1/channel.1/trace.1']
    )
    print('OK' if ok else 'FAIL', path, '->', leaves)
    if not ok:
        all_ok = False

    path = '.../channel[0]/...'
    leaves = find_leaves(root, path)
    ok = tuple(leaves) == (
        root['run.0/sweep.0/channel.0/trace.0/ydata'],
        root['run.0/sweep.0/channel.0/trace.1/ydata'],
        root['run.0/sweep.0/channel.0/trace.2/ydata'],
        root['run.0/sweep.1/channel.0/trace.0/ydata'],
        root['run.0/sweep.1/channel.0/trace.1/ydata']
    )
    print('OK' if ok else 'FAIL', path, '->', leaves)
    if not ok:
        all_ok = False

    path = 'run[0]/sweep[0]/channel[0]/trace[:]'
    leaves = find_leaves(root, path)
    ok = tuple(leaves) == (
        root['run.0/sweep.0/channel.0/trace.0'],
        root['run.0/sweep.0/channel.0/trace.1'],
        root['run.0/sweep.0/channel.0/trace.2']
    )
    print('OK' if ok else 'FAIL', path, '->', leaves)
    if not ok:
        all_ok = False

    path = 'run[0]/sweep[:]/channel[1:2]/trace[1]'
    leaves = find_leaves(root, path)
    ok = tuple(leaves) == (
        root['run.0/sweep.0/channel.1/trace.1'],
        root['run.0/sweep.1/channel.1/trace.1']
    )
    print('OK' if ok else 'FAIL', path, '->', leaves)
    if not ok:
        all_ok = False

    path = 'run[0]/sweep[1]/channel[:]/trace[:]'
    leaves = find_leaves(root, path)
    ok = tuple(leaves) == (
        root['run.0/sweep.1/channel.0/trace.0'],
        root['run.0/sweep.1/channel.0/trace.1'],
        root['run.0/sweep.1/channel.1/trace.0'],
        root['run.0/sweep.1/channel.1/trace.1']
    )
    print('OK' if ok else 'FAIL', path, '->', leaves)
    if not ok:
        all_ok = False

    path = 'run.0/sweep[:]/channel[1]/trace[:]'
    leaves = find_leaves(root, path)
    ok = tuple(leaves) == (
        root['run.0/sweep.0/channel.1/trace.0'],
        root['run.0/sweep.0/channel.1/trace.1'],
        root['run.0/sweep.0/channel.1/trace.2'],
        root['run.0/sweep.1/channel.1/trace.0'],
        root['run.0/sweep.1/channel.1/trace.1']
    )
    print('OK' if ok else 'FAIL', path, '->', leaves)
    if not ok:
        all_ok = False

    path = 'run.0/sweep.1/channel[1]/trace[:]'
    leaves = find_leaves(root, path)
    ok = tuple(leaves) == (
        root['run.0/sweep.1/channel.1/trace.0'],
        root['run.0/sweep.1/channel.1/trace.1']
    )
    print('OK' if ok else 'FAIL', path, '->', leaves)
    if not ok:
        all_ok = False

    path = 'run.0/*/channel[1]/trace[:]'
    leaves = find_leaves(root, path)
    ok = tuple(leaves) == (
        root['run.0/sweep.0/channel.1/trace.0'],
        root['run.0/sweep.0/channel.1/trace.1'],
        root['run.0/sweep.0/channel.1/trace.2'],
        root['run.0/sweep.1/channel.1/trace.0'],
        root['run.0/sweep.1/channel.1/trace.1']
    )
    print('OK' if ok else 'FAIL', path, '->', leaves)
    if not ok:
        all_ok = False

    path = 'run.0/*/channel[1]/trace[:]/ydata'
    leaves = find_leaves(root, path)
    ok = tuple(leaves) == (
        root['run.0/sweep.0/channel.1/trace.0/ydata'],
        root['run.0/sweep.0/channel.1/trace.1/ydata'],
        root['run.0/sweep.0/channel.1/trace.2/ydata'],
        root['run.0/sweep.1/channel.1/trace.0/ydata'],
        root['run.0/sweep.1/channel.1/trace.1/ydata']
    )
    print('OK' if ok else 'FAIL', path, '->', leaves)
    if not ok:
        all_ok = False

    path = 'run.0/*'
    leaves = find_leaves(root, path)
    ok = tuple(leaves) == (
        root['run.0/sweep.0'],
        root['run.0/sweep.1']
    )
    print('OK' if ok else 'FAIL', path, '->', leaves)
    if not ok:
        all_ok = False

    path = 'run[:]/*'
    leaves = find_leaves(root, path)
    ok = tuple(leaves) == (
        root['run.0/sweep.0'],
        root['run.0/sweep.1']
    )
    print('OK' if ok else 'FAIL', path, '->', leaves)
    if not ok:
        all_ok = False

    return all_ok


def tests():
    test_funcs = [
        test_index_exp,
        test_name_index_exp,
        test_slice_path,
        test_path_in_slice,
        test_find_first,
        test_find_all,
        test_find_leaves
    ]
    oks = [test_func() for test_func in test_funcs]
    print('----------')
    for ok, test_func in zip(oks, test_funcs):
        print(f"{'OK' if ok else 'FAIL'}: {test_func}")
    print('----------')


if __name__ == '__main__':
    tests()
