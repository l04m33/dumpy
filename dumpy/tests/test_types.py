import unittest
import dumpy.config as dconfig
import dumpy.types as dtypes


class TestStructMeta(unittest.TestCase):
    def test_format_endian(self):
        class A(int, metaclass=dtypes.StructMeta):
            __format__ = '<i'
        self.assertEqual(A.__struct__.format, b'<i')

        class A(int, metaclass=dtypes.StructMeta):
            __format__ = '>i'
        self.assertEqual(A.__struct__.format, b'>i')

        class A(int, metaclass=dtypes.StructMeta):
            __format__ = 'i'
        self.assertTrue(
            chr(A.__struct__.format[0]) in ['@', '=', '<', '>', '!'])
        self.assertEqual(A.__struct__.format[1], ord('i'))

    def test_base_class(self):
        class A(int, metaclass=dtypes.StructMeta):
            __format__ = 'i'
        self.assertTrue(issubclass(A, dtypes.StructMixin))


class TestInt8(unittest.TestCase):
    def test_int8(self):
        i = dtypes.Int8(0x7f)

        self.assertEqual(i.size(), 1)

        self.assertEqual(i.pack(), b'\x7f')
        self.assertEqual(dtypes.Int8.unpack(i.pack()), 0x7f)
        self.assertEqual(dtypes.Int8.unpack(i.pack()).pack(), i.pack())

        b = bytearray(4)
        i.pack_into(b, 1)
        self.assertEqual(b, b'\x00\x7f\x00\x00')
        i.pack_into(b)
        self.assertEqual(b, b'\x7f\x7f\x00\x00')

        i = dtypes.Int8.unpack_from(b'\x7e\x7f\x00\x00')
        self.assertEqual(i, dtypes.Int8(0x7e))
        i = dtypes.Int8.unpack_from(b'\x7e\x7f\x00\x00', 1)
        self.assertEqual(i, dtypes.Int8(0x7f))
