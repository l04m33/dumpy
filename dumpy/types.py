import struct
import collections
import weakref
from .config import ENDIAN


class PrimitiveStructMixin:
    def pack(self):
        return self.__struct__.pack(self)

    def pack_into(self, buf, offset=0):
        self.__struct__.pack_into(buf, offset, self)

    @classmethod
    def unpack(cls, buf):
        (value,) = cls.__struct__.unpack(buf)
        return cls(value)

    @classmethod
    def unpack_from(cls, buf, offset=0, parent=None):
        (value,) = cls.__struct__.unpack_from(buf, offset)
        return cls(value)

    @property
    def size(self):
        return self.__struct__.size


class SequenceStructMixin:
    def pack(self):
        return self.__struct__.pack(*self)

    def pack_into(self, buf, offset=0):
        self.__struct__.pack_into(buf, offset, *self)

    @classmethod
    def unpack(cls, buf):
        return cls(cls.__struct__.unpack(buf))

    @classmethod
    def unpack_from(cls, buf, offset=0):
        return cls(cls.__struct__.unpack_from(buf, offset))

    @property
    def size(self):
        return self.__struct__.size


class NoDefault:
    def __init__(self):
        raise RuntimeError('NoDefault cannot be instantiated')


def field(name, tp, count=1, default=NoDefault):
    return (name, tp, count, default)


def counted_by(name):
    def counted_by_func(obj):
        return obj[name]
    return counted_by_func


def count_of(name):
    def count_of_func(obj):
        return len(obj[name])
    return count_of_func


class VariableType:
    def __init__(self, get_type):
        self._get_type = get_type

    def get_type(self, obj):
        return self._get_type(obj)


class CompositeStructMixin:
    def _safe_get(self, fname, default=None):
        try:
            return super().__getitem__(fname)
        except KeyError:
            return default

    def _get_field(self, fname, count, default):
        if callable(count):
            # variable length
            return self._safe_get(fname, [])
        else:
            if count > 1:
                val_list = self._safe_get(fname, [])
                real_count = len(val_list)
                # We checked this in __setitem__, but a newly created object may
                # still have insufficient values to pack.
                if real_count < count:
                    if default is NoDefault:
                        raise ValueError(
                            'Expected {} values for field {}, '
                            'but got {}'.format(count, repr(fname), real_count))
                    elif callable(default):
                        default_list = \
                            [default(self) for _i in range(count - real_count)]
                    else:
                        default_list = [default] * (count - real_count)
                    val_list += default_list
                return val_list
            elif count == 1:
                if default is NoDefault:
                    field_val = super().__getitem__(fname)
                else:
                    if callable(default):
                        default = default(self)
                    field_val = self._safe_get(fname, default)
                return field_val
            else:
                return None

    def _normalize_composite(self, value, ftype):
        if issubclass(ftype, CompositeStructMixin):
            if not isinstance(value, ftype):
                value = ftype(value)
            value.parent = self
        return value

    def __getitem__(self, fname):
        _ftype, count, default = self.__field_info__[fname]
        ret = self._get_field(fname, count, default)
        if ret is None:
            raise ValueError('Field {} cannot be read'.format(fname))
        return ret

    def __setitem__(self, fname, value):
        ftype, count, default = self.__field_info__[fname]

        if isinstance(ftype, VariableType):
            ftype = ftype.get_type(self)

        if callable(count):
            if not isinstance(value, list):
                raise TypeError('Field {} needs a list'.format(repr(fname)))
            value = [self._normalize_composite(v, ftype) for v in value]
            super().__setitem__(fname, value)
        else:
            if count > 1:
                if not isinstance(value, list):
                    raise TypeError('Field {} needs a list'.format(repr(fname)))
                if len(value) > count:
                    raise ValueError(
                        'Field {} needs {} values, but got {}'.format(
                            repr(fname), count, len(value)))
                elif len(value) < count and default is NoDefault:
                    raise ValueError(
                        'Field {} needs {} values, but got {}'.format(
                            repr(fname), count, len(value)))

                value = [self._normalize_composite(v, ftype) for v in value]
                super().__setitem__(fname, value)
            elif count == 1:
                if isinstance(value, list):
                    raise TypeError(
                        'Field {} cannot accept a list'.format(repr(fname)))

                value = self._normalize_composite(value, ftype)
                super().__setitem__(fname, value)
            else:
                raise ValueError('No space for field {}'.format(repr(fname)))

    def pack(self):
        bin_list = []
        for fname in self.__fields__:
            ftype, count, default = self.__field_info__[fname]
            val = self._get_field(fname, count, default)

            if val is None:
                continue

            if not isinstance(val, list):
                val = [val]
            for v in val:
                try:
                    packed = v.pack()
                except AttributeError:
                    if isinstance(ftype, VariableType):
                        ftype = ftype.get_type(self)
                    packed = ftype(v).pack()
                bin_list.append(packed)

        return b''.join(bin_list)

    def pack_into(self, buf, offset=0):
        total_size = self.size
        if len(buf[offset:]) < total_size:
            raise ValueError(
                'pack_into needs {} bytes of space, but only got {}'.format(
                    total_size, len(buf[offset:])))

        for fname in self.__fields__:
            ftype, count, default = self.__field_info__[fname]
            val = self._get_field(fname, count, default)

            if val is None:
                continue

            if not isinstance(val, list):
                val = [val]
            for v in val:
                try:
                    v.pack_into(buf, offset)
                except AttributeError:
                    if isinstance(ftype, VariableType):
                        ftype = ftype.get_type(self)
                    v = ftype(v)
                    v.pack_into(buf, offset)
                offset += v.size

    @classmethod
    def unpack(cls, buf):
        obj = cls.unpack_from(buf, 0)
        return obj

    @classmethod
    def unpack_from(cls, buf, offset=0, parent=None):
        obj = cls()

        if parent is not None:
            obj.parent = weakref.ref(parent)
        else:
            obj.parent = None

        for fname in cls.__fields__:
            ftype, count, _default = cls.__field_info__[fname]

            if callable(count):
                real_count = count(obj)
            else:
                real_count = count

            if isinstance(ftype, VariableType):
                ftype = ftype.get_type(obj)

            val_list = []
            for i in range(real_count):
                v = ftype.unpack_from(buf, offset, obj)
                offset += v.size
                val_list.append(v)

            if callable(count):
                super().__setitem__(obj, fname, val_list)
            else:
                if len(val_list) > 1:
                    super().__setitem__(obj, fname, val_list)
                elif len(val_list) == 1:
                    super().__setitem__(obj, fname, val_list[0])

        return obj

    def _safe_size(self, v, ftype):
        try:
            return v.size
        except AttributeError:
            return ftype(v).size

    @property
    def size(self):
        size = 0
        for fname in self.__fields__:
            ftype, count, default = self.__field_info__[fname]
            val = self._get_field(fname, count, default)

            if val is None:
                continue

            if isinstance(ftype, VariableType):
                ftype = ftype.get_type(self)

            if isinstance(val, list):
                for v in val:
                    size += self._safe_size(v, ftype)
            else:
                size += self._safe_size(val, ftype)
        return size


class DumpyMeta(type):
    def __new__(cls, clsname, bases, clsdict):
        if any([issubclass(c, collections.Mapping) for c in bases]):
            return cls._new_composite(cls, clsname, bases, clsdict)
        elif any([issubclass(c, collections.Sequence) for c in bases]):
            return cls._new_sequence(cls, clsname, bases, clsdict)
        else:
            return cls._new_primitive(cls, clsname, bases, clsdict)

    def _normalize_format(fmt, clsdict):
        first_char = fmt[0]
        if isinstance(first_char, int):
            first_char = chr(first_char)

        if first_char not in ['@', '=', '<', '>', '!']:
            try:
                endian = clsdict['__endian__']
            except KeyError:
                endian = ENDIAN
            return (endian + fmt)
        else:
            return fmt

    def _new_simple(cls, clsname, bases, clsdict, extra_base):
        try:
            fmt = clsdict['__format__']
        except KeyError:
            # No meta data, do not process this class
            return super().__new__(cls, clsname, bases, clsdict)

        if extra_base not in bases:
            bases = (extra_base,) + bases

        fmt = cls._normalize_format(fmt, clsdict)
        clsdict['__struct__'] = struct.Struct(fmt)

        return super().__new__(cls, clsname, bases, clsdict)

    def _new_primitive(cls, clsname, bases, clsdict):
        return cls._new_simple(
            cls, clsname, bases, clsdict, PrimitiveStructMixin)

    def _new_sequence(cls, clsname, bases, clsdict):
        return cls._new_simple(
            cls, clsname, bases, clsdict, SequenceStructMixin)

    def _new_composite(cls, clsname, bases, clsdict):
        try:
            fields = clsdict['__field_specs__']
        except KeyError:
            # No meta data, do not process this class
            return super().__new__(cls, clsname, bases, clsdict)

        __fields__ = []
        __field_info__ = {}
        for fname, ftype, count, default in fields:
            __fields__.append(fname)
            __field_info__[fname] = (ftype, count, default)

        clsdict['__fields__'] = __fields__
        clsdict['__field_info__'] = __field_info__

        if CompositeStructMixin not in bases:
            bases = (CompositeStructMixin,) + bases

        new_cls = super().__new__(cls, clsname, bases, clsdict)
        return new_cls


class Int8(int, metaclass=DumpyMeta):
    __format__ = 'b'


class UInt8(int, metaclass=DumpyMeta):
    __format__ = 'B'


class Int16(int, metaclass=DumpyMeta):
    __format__ = 'h'


class UInt16(int, metaclass=DumpyMeta):
    __format__ = 'H'


class Int32(int, metaclass=DumpyMeta):
    __format__ = 'i'


class UInt32(int, metaclass=DumpyMeta):
    __format__ = 'I'


class Float(float, metaclass=DumpyMeta):
    __format__ = 'f'


class Double(float, metaclass=DumpyMeta):
    __format__ = 'd'
