import struct
import collections
from .config import ENDIAN


class StructMixin:
    def pack(self):
        return self.__struct__.pack(self)

    def pack_into(self, buf, offset=0):
        self.__struct__.pack_into(buf, offset, self)

    @classmethod
    def unpack(cls, buf):
        (value,) = cls.__struct__.unpack(buf)
        return cls(value)

    @classmethod
    def unpack_from(cls, buf, offset=0):
        (value,) = cls.__struct__.unpack_from(buf, offset)
        return cls(value)

    @classmethod
    def size(cls):
        return cls.__struct__.size


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

    @classmethod
    def size(cls):
        return cls.__struct__.size


class StructMeta(type):
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

    def _new_simple(cls, clsname, bases, clsdict):
        try:
            fmt = clsdict['__format__']
        except KeyError:
            # No meta data, do not process this class
            return super().__new__(cls, clsname, bases, clsdict)

        fmt = cls._normalize_format(fmt, clsdict)
        clsdict['__struct__'] = struct.Struct(fmt)

        return super().__new__(cls, clsname, bases, clsdict)

    def _new_primitive(cls, clsname, bases, clsdict):
        if StructMixin not in bases:
            bases = (StructMixin,) + bases
        return cls._new_simple(cls, clsname, bases, clsdict)

    def _new_sequence(cls, clsname, bases, clsdict):
        if SequenceStructMixin not in bases:
            bases = (SequenceStructMixin,) + bases
        return cls._new_simple(cls, clsname, bases, clsdict)

    def _new_composite(cls, clsname, bases, clsdict):
        try:
            fields = clsdict['__field_specs__']
        except KeyError:
            # No meta data, do not process this class
            return super().__new__(cls, clsname, bases, clsdict)

        __fields__ = []
        __field_info__ = {}
        for fname, ftype, count, default in fields:
            if count < 1:
                raise ValueError(
                    'Value count for field {} is invalid'.format(repr(fname)))
            __fields__.append(fname)
            __field_info__[fname] = (ftype, count, default)

        clsdict['__fields__'] = __fields__
        clsdict['__field_info__'] = __field_info__

        if CompoundStructMixin not in bases:
            bases = (CompoundStructMixin,) + bases

        new_cls = super().__new__(cls, clsname, bases, clsdict)
        return new_cls


class Int8(int, metaclass=StructMeta):
    __format__ = 'b'


class UInt8(int, metaclass=StructMeta):
    __format__ = 'B'


class Int16(int, metaclass=StructMeta):
    __format__ = 'h'


class UInt16(int, metaclass=StructMeta):
    __format__ = 'H'


class Int32(int, metaclass=StructMeta):
    __format__ = 'i'


class UInt32(int, metaclass=StructMeta):
    __format__ = 'I'


class Float(float, metaclass=StructMeta):
    __format__ = 'f'


class Double(float, metaclass=StructMeta):
    __format__ = 'd'


class NoDefault:
    def __init__(self):
        raise RuntimeError('NoDefault cannot be instantiated')


def field(name, tp, count=1, default=NoDefault):
    return (name, tp, count, default)


class CompoundStructMixin:
    def _get_field(self, fname, count, default):
        if count > 1:
            val_list = self.get(fname, [])
            real_count = len(val_list)
            # We checked this in __setitem__, but a newly created object may
            # still have insufficient values to pack.
            if real_count < count:
                if default is NoDefault:
                    raise ValueError(
                        'Expected {} values for field {}, '
                        'but got {}'.format(count, repr(fname), real_count))
                val_list += ([default] * (count - real_count))
            return val_list
        else:
            if default is NoDefault:
                field_val = super().__getitem__(fname)
            else:
                try:
                    field_val = super().__getitem__(fname)
                except KeyError:
                    field_val = default
            return field_val

    def __getitem__(self, fname):
        ftype, count, default = self.__field_info__[fname]
        return self._get_field(fname, count, default)

    def __setitem__(self, fname, value):
        ftype, count, default = self.__field_info__[fname]

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

            super().__setitem__(fname, value)

        else:
            if isinstance(value, list):
                raise TypeError(
                    'Field {} cannot accept a list'.format(repr(fname)))

            super().__setitem__(fname, value)

    def pack(self):
        bin_list = []
        for fname in self.__fields__:
            ftype, count, default = self.__field_info__[fname]
            val = self._get_field(fname, count, default)
            if not isinstance(val, list):
                val = [val]
            for v in val:
                try:
                    packed = v.pack()
                except AttributeError:
                    packed = ftype(v).pack()
                bin_list.append(packed)

        return b''.join(bin_list)

    def pack_into(self, buf, offset=0):
        total_size = self.size()
        if len(buf[offset:]) < total_size:
            raise ValueError(
                'pack_into needs {} bytes of space, but only got {}'.format(
                    total_size, len(buf[offset:])))

        for fname in self.__fields__:
            ftype, count, default = self.__field_info__[fname]
            val = self._get_field(fname, count, default)
            if not isinstance(val, list):
                val = [val]
            for v in val:
                try:
                    v.pack_into(buf, offset)
                except AttributeError:
                    v = ftype(v)
                    v.pack_into(buf, offset)
                offset += v.size()

    @classmethod
    def unpack(cls, buf):
        obj = cls.unpack_from(buf, 0)
        if obj.size() < len(buf):
            raise ValueError(
                '{} trailing bytes in buffer'.format(len(buf) - obj.size()))
        return obj

    @classmethod
    def unpack_from(cls, buf, offset=0):
        obj = cls()
        for fname in cls.__fields__:
            ftype, count, _default = cls.__field_info__[fname]
            val_list = []
            for i in range(count):
                v = ftype.unpack_from(buf, offset)
                offset += v.size()
                val_list.append(v)

            if len(val_list) > 1:
                obj[fname] = val_list
            else:
                obj[fname] = val_list[0]

        return obj

    @classmethod
    def size(cls):
        size = 0
        for _fname, info in cls.__field_info__.items():
            ftype, count, _default = info
            size += (ftype.size() * count)
        return size
