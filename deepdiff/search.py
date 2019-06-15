#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import sys
import datetime
import logging
from decimal import Decimal

py_major_version = sys.version[0]
py_minor_version = sys.version[2]

py3 = py_major_version == '3'

if (py_major_version, py_minor_version) == (2.6):  # pragma: no cover
    sys.exit('Python 2.6 is not supported.')

if py3:  # pragma: no cover
    from collections.abc import Iterable
    from collections.abc import MutableMapping
    from builtins import int
    strings = (str, bytes)  # which are both basestring
    numbers = (int, float, complex, datetime.datetime, datetime.date, Decimal)
    items = 'items'
else:  # pragma: no cover
    from collections import Iterable
    from collections import MutableMapping
    strings = (str, unicode)
    numbers = (int, float, long, complex, datetime.datetime, datetime.date, Decimal)
    items = 'iteritems'

logger = logging.getLogger(__name__)


INDEX_VS_ATTRIBUTE = ('[%s]', '.%s')


class DeepSearch(dict):

    r"""
    **DeepSearch**

    Deep Search inside objects to find the item matching your criteria.

    **Parameters**

    obj : The object to search within

    item : The item to search for

    verbose_level : int >= 0, default = 1.
        Verbose level one shows the paths of found items.
        Verbose level 2 shows the path and value of the found items.

    exclude_paths: list, default = None.
        List of paths to exclude from the report.

    exclude_types: list, default = None.
        List of object types to exclude from the report.

    **Returns**

        A DeepSearch object that has the matched paths and matched values.

    **Supported data types**

    int, string, unicode, dictionary, list, tuple, set, frozenset, OrderedDict, NamedTuple and custom objects!

    **Examples**

    Importing
        >>> from deepdiff import DeepSearch
        >>> from pprint import pprint
        >>> from __future__ import print_function # In case running on Python 2

    Search in list for string
        >>> obj = ["long somewhere", "string", 0, "somewhere great!"]
        >>> item = "somewhere"
        >>> ds = DeepSearch(obj, item, verbose_level=2)
        >>> print(ds)
        {'matched_values': {'root[3]': 'somewhere great!', 'root[0]': 'long somewhere'}}

    Search in nested data for string
        >>> obj = ["something somewhere", {"long": "somewhere", "string": 2, 0: 0, "somewhere": "around"}]
        >>> item = "somewhere"
        >>> ds = DeepSearch(obj, item, verbose_level=2)
        >>> pprint(ds, indent=2)
        { 'matched_paths': {"root[1]['somewhere']": 'around'},
          'matched_values': { 'root[0]': 'something somewhere',
                              "root[1]['long']": 'somewhere'}}

    """

    warning_num = 0

    def __init__(self, obj, item, exclude_paths=set(), exclude_types=set(), verbose_level=1, **kwargs):
        if kwargs:
            raise ValueError(("The following parameter(s) are not valid: %s\n"
                              "The valid parameters are obj, item, exclude_paths, exclude_types and verbose_level.") % ', '.join(kwargs.keys()))

        self.obj = obj
        self.item = item
        self.exclude_paths = set(exclude_paths)
        self.exclude_types = set(exclude_types)
        self.exclude_types_tuple = tuple(exclude_types)  # we need tuple for checking isinstance
        self.verbose_level = verbose_level
        self.update(matched_paths=self.__set_or_dict(),
                    matched_values=self.__set_or_dict(),
                    unprocessed=[])

        self.__search(obj, item, parents_ids=frozenset({id(obj)}))

        empty_keys = [k for k, v in getattr(self, items)() if not v]

        for k in empty_keys:
            del self[k]

    def __set_or_dict(self):
        return {} if self.verbose_level >= 2 else set()

    def __report(self, report_key, key, value):
        if self.verbose_level >= 2:
            self[report_key][key] = value
        else:
            self[report_key].add(key)

    @staticmethod
    def __add_to_frozen_set(parents_ids, item_id):
        parents_ids = set(parents_ids)
        parents_ids.add(item_id)
        return frozenset(parents_ids)

    def __search_obj(self, obj, item, parent, parents_ids=frozenset({}), is_namedtuple=False):
        """Search objects"""
        try:
            if is_namedtuple:
                obj = obj._asdict()
            else:
                obj = obj.__dict__
        except AttributeError:
            try:
                obj = {i: getattr(obj, i) for i in obj.__slots__}
            except AttributeError:
                self['unprocessed'].append("%s" % parent)
                return

        self.__search_dict(obj, item, parent, parents_ids, print_as_attribute=True)

    def __skip_this(self, item, parent):
        skip = False
        if parent in self.exclude_paths:
            skip = True
        else:
            if isinstance(item, self.exclude_types_tuple):
                skip = True

        return skip

    def __search_dict(self, obj, item, parent, parents_ids=frozenset({}), print_as_attribute=False):
        """Search dictionaries"""
        if print_as_attribute:
            parent_text = "%s.%s"
        else:
            parent_text = "%s[%s]"

        obj_keys = set(obj.keys())

        for item_key in obj_keys:
            if not print_as_attribute and isinstance(item_key, strings):
                item_key_str = "'%s'" % item_key
            else:
                item_key_str = item_key

            obj_child = obj[item_key]

            item_id = id(obj_child)

            if parents_ids and item_id in parents_ids:
                continue

            parents_ids_added = self.__add_to_frozen_set(parents_ids, item_id)

            new_parent = parent_text % (parent, item_key_str)

            if str(item) in new_parent:
                self.__report(report_key='matched_paths', key=new_parent, value=obj_child)

            self.__search(obj_child, item, parent=new_parent, parents_ids=parents_ids_added)

    def __search_iterable(self, obj, item, parent="root", parents_ids=frozenset({})):
        """Search iterables except dictionaries, sets and strings."""

        for i, x in enumerate(obj):
            new_parent = "%s[%s]" % (parent, i)
            if self.__skip_this(x, parent=new_parent):
                continue
            if x == item:
                self.__report(report_key='matched_values', key=new_parent, value=x)
            else:
                item_id = id(x)
                if parents_ids and item_id in parents_ids:
                    continue
                parents_ids_added = self.__add_to_frozen_set(parents_ids, item_id)
                self.__search(x, item, "%s[%s]" % (parent, i), parents_ids_added)

    def __search_str(self, obj, item, parent):
        """Compare strings"""
        if item in obj:
            self.__report(report_key='matched_values', key=parent, value=obj)

    def __search_numbers(self, obj, item, parent):
        if item == obj:
            self.__report(report_key='matched_values', key=parent, value=obj)

    def __search_tuple(self, obj, item, parent, parents_ids):
        # Checking to see if it has _fields. Which probably means it is a named
        # tuple.
        try:
            obj._asdict
        # It must be a normal tuple
        except AttributeError:
            self.__search_iterable(obj, item, parent, parents_ids)
        # We assume it is a namedtuple then
        else:
            self.__search_obj(obj, item, parent, parents_ids, is_namedtuple=True)

    def __search(self, obj, item, parent="root", parents_ids=frozenset({})):
        """The main search method"""

        if self.__skip_this(item, parent):
            return

        elif isinstance(obj, strings) and isinstance(item, strings):
            self.__search_str(obj, item, parent)

        elif isinstance(obj, strings) and isinstance(item, numbers):
            return

        elif isinstance(obj, numbers):
            self.__search_numbers(obj, item, parent)

        elif isinstance(obj, MutableMapping):
            self.__search_dict(obj, item, parent, parents_ids)

        elif isinstance(obj, tuple):
            self.__search_tuple(obj, item, parent, parents_ids)

        elif isinstance(obj, (set, frozenset)):
            if self.warning_num < 10:
                logger.warning("Set item detected in the path."
                               "'set' objects do NOT support indexing. But DeepSearch will still report a path.")
                self.warning_num += 1
            self.__search_iterable(obj, item, parent, parents_ids)

        elif isinstance(obj, Iterable):
            self.__search_iterable(obj, item, parent, parents_ids)

        else:
            self.__search_obj(obj, item, parent, parents_ids)



if __name__ == "__main__":  # pragma: no cover
    if not py3:
        sys.exit("Please run with Python 3 to check for doc strings.")
    import doctest
    doctest.testmod()
