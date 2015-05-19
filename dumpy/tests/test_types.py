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


class TestArray(unittest.TestCase):
    def test_array(self):
        class ByteArray(tuple, metaclass=dtypes.StructMeta):
            __format__ = '4B'

        b = ByteArray((1, 2, 3, 4))
        self.assertEqual(b.size(), 4)
        self.assertEqual(b.pack(), b'\x01\x02\x03\x04')
        self.assertEqual(ByteArray.unpack(b.pack()), b)
        self.assertEqual(ByteArray.unpack(b.pack()).pack(), b.pack())


class TestCompoundStructMeta(unittest.TestCase):
    def test_field_specs(self):
        class A(metaclass=dtypes.CompoundStructMeta):
            __field_specs__ = (
                dtypes.field('field1', dtypes.Int8),
                dtypes.field('field2', dtypes.Int8, default=9),
                dtypes.field('field3', dtypes.Int8, 4),
                dtypes.field('field4', dtypes.Int8, 4, 1),
            )

        self.assertTrue(issubclass(A, dtypes.CompoundStructMixin))

        a = A()
        with self.assertRaises(KeyError):
            a.pack()

        with self.assertRaises(TypeError):
            a['field1'] = [0x7f]

        self.assertEqual(a['field2'], 9)

        a['field1'] = 0x7f
        with self.assertRaises(ValueError):
            a.pack()

        with self.assertRaises(TypeError):
            a['field3'] = 1

        with self.assertRaises(ValueError):
            a['field3'] = [1, 2]

        a['field3'] = [1, 2, 3, 4]

        self.assertEqual(a['field4'], [1, 1, 1, 1])

        data = a.pack()
        self.assertEqual(data, b'\x7f\x09\x01\x02\x03\x04\x01\x01\x01\x01')

        a['field2'] = 10
        a['field4'] = [2, 2, 2, 2]
        data = a.pack()
        self.assertEqual(data, b'\x7f\x0a\x01\x02\x03\x04\x02\x02\x02\x02')

    def test_multi_level_compound(self):
        class Header(metaclass=dtypes.CompoundStructMeta):
            __field_specs__ = (
                dtypes.field('field1', dtypes.Int8),
                dtypes.field('field2', dtypes.Int8),
            )

        class Body(metaclass=dtypes.CompoundStructMeta):
            __field_specs__ = (
                dtypes.field('field', dtypes.Int8),
            )

        class Msg(metaclass=dtypes.CompoundStructMeta):
            __field_specs__ = (
                dtypes.field('header', Header),
                dtypes.field('bodies', Body, count=2),
            )

        m = Msg()
        m['header'] = Header()
        m['bodies'] = [Body(), Body()]

        m['header']['field1'] = 0x7e
        m['header']['field2'] = 0x7f
        m['bodies'][0]['field'] = 1
        m['bodies'][1]['field'] = 2

        self.assertEqual(m.pack(), b'\x7e\x7f\x01\x02')
        self.assertEqual(Msg.unpack(m.pack()), m)
        self.assertEqual(Msg.unpack(m.pack()).pack(), m.pack())

        b = bytearray(6)
        m.pack_into(b, 2)
        self.assertEqual(b, b'\x00\x00\x7e\x7f\x01\x02')
        m2 = Msg.unpack_from(b, 2)
        self.assertEqual(m, m2)
