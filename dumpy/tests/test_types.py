import unittest
import random
import dumpy.config as dconfig
import dumpy.types as dtypes


class TestDumpyMeta(unittest.TestCase):
    def test_format_endian(self):
        class A(int, metaclass=dtypes.DumpyMeta):
            __format__ = '<i'
        self.assertEqual(A.__struct__.format, b'<i')

        class A(int, metaclass=dtypes.DumpyMeta):
            __format__ = '>i'
        self.assertEqual(A.__struct__.format, b'>i')

        class A(int, metaclass=dtypes.DumpyMeta):
            __format__ = 'i'
        self.assertTrue(
            chr(A.__struct__.format[0]) in ['@', '=', '<', '>', '!'])
        self.assertEqual(A.__struct__.format[1], ord('i'))

    def test_base_class(self):
        class A(int, metaclass=dtypes.DumpyMeta):
            __format__ = 'i'
        self.assertTrue(issubclass(A, dtypes.PrimitiveStructMixin))

    def test_exceptions(self):
        class A(int, metaclass=dtypes.DumpyMeta): pass
        self.assertFalse(issubclass(A, dtypes.PrimitiveStructMixin))

        class A(int, metaclass=dtypes.DumpyMeta):
            __format__ = b'<B'
        self.assertEqual(A.__struct__.format, b'<B')


class TestInt8(unittest.TestCase):
    def test_int8(self):
        i = dtypes.Int8(0x7f)

        self.assertEqual(i.size, 1)

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
        class ByteArray(tuple, metaclass=dtypes.DumpyMeta):
            __format__ = '4B'

        b = ByteArray((1, 2, 3, 4))
        self.assertEqual(b.size, 4)
        self.assertEqual(b.pack(), b'\x01\x02\x03\x04')
        self.assertEqual(ByteArray.unpack(b.pack()), b)
        self.assertEqual(ByteArray.unpack(b.pack()).pack(), b.pack())

        bb = bytearray(6)
        b.pack_into(bb, 1)
        self.assertEqual(bb, b'\x00\x01\x02\x03\x04\x00')
        self.assertEqual(ByteArray.unpack_from(bb, 1), b)
        self.assertEqual(ByteArray.unpack_from(bb, 1).pack(), b.pack())


class TestCompositeDumpyMeta(unittest.TestCase):
    def test_field_specs(self):
        class A(dict, metaclass=dtypes.DumpyMeta):
            __field_specs__ = (
                dtypes.field('field1', dtypes.Int8),
                dtypes.field('field2', dtypes.Int8, default=9),
                dtypes.field('field3', dtypes.Int8, 4),
                dtypes.field('field4', dtypes.Int8, 4, 1),
            )

        self.assertTrue(issubclass(A, dtypes.CompositeStructMixin))

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

        class B(dict, metaclass=dtypes.DumpyMeta):
            __field_specs__ = (
                dtypes.field('field', dtypes.Int8, count=0),
            )

        b = B()
        self.assertEqual(b.size, 0)
        with self.assertRaises(ValueError):
            b['field'] = 0
        with self.assertRaises(ValueError):
            b['field']

        self.assertEqual(B.unpack(b''), {})
        self.assertEqual(B.unpack_from(b'\x00\x00'), {})
        self.assertEqual(b.pack(), b'')
        bb = bytearray(b'\x7e\x7f')
        b.pack_into(bb, 1)
        self.assertEqual(bb, b'\x7e\x7f')

    def test_multi_level_composite(self):
        class Header(dict, metaclass=dtypes.DumpyMeta):
            __field_specs__ = (
                dtypes.field('field1', dtypes.Int8),
                dtypes.field('field2', dtypes.Int8),
            )

        class Body(dict, metaclass=dtypes.DumpyMeta):
            __field_specs__ = (
                dtypes.field('field', dtypes.Int8),
            )

        class Msg(dict, metaclass=dtypes.DumpyMeta):
            __field_specs__ = (
                dtypes.field('header', Header),
                dtypes.field('bodies', Body, count=2),
            )

        m = Msg()
        m['header'] = {'field1': 0, 'field2': 0}
        m['bodies'] = [Body(), Body()]

        self.assertEqual(m['header'].parent, m)
        self.assertEqual(m['bodies'][0].parent, m)
        self.assertEqual(m['bodies'][1].parent, m)

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

        with self.assertRaises(ValueError):
            m.pack_into(b, 3)

    def test_variable_length_field(self):
        class A(dict, metaclass=dtypes.DumpyMeta):
            __field_specs__ = (
                dtypes.field('len', dtypes.Int8,
                             default=dtypes.count_of('numbers')),
                dtypes.field('numbers', dtypes.Int8,
                             count=dtypes.counted_by('len')),
            )

        a = A()
        self.assertEqual(a['len'], 0)

        with self.assertRaises(TypeError):
            a['numbers'] = 1

        a['numbers'] = [1, 2, 3, 4]
        self.assertEqual(a['len'], 4)
        self.assertEqual(a.pack(), b'\x04\x01\x02\x03\x04')
        self.assertEqual(A.unpack(a.pack()).pack(), a.pack())

        a['numbers'] = []
        self.assertEqual(a.pack(), b'\x00')
        self.assertEqual(A.unpack(a.pack()).pack(), a.pack())

        self.assertEqual(
            A.unpack_from(b'\x02\x01\x02\x03\x04').pack(), b'\x02\x01\x02')

    def test_variable_type(self):
        def get_type(obj):
            if obj['type'] == 0:
                return dtypes.Int8
            elif obj['type'] == 1:
                return dtypes.Int32

        class A(dict, metaclass=dtypes.DumpyMeta):
            __field_specs__ = (
                dtypes.field('type', dtypes.Int8),
                dtypes.field('data', dtypes.VariableType(get_type)),
            )

        a = A()
        a['type'] = 0
        a['data'] = 0x7f
        self.assertEqual(a.size, 2)
        self.assertEqual(a.pack(), b'\x00\x7f')
        self.assertEqual(A.unpack(b'\x00\x7f'), a)
        self.assertEqual(A.unpack(b'\x00\x7f').pack(), a.pack())

        b = bytearray(4)
        a.pack_into(b, 1)
        self.assertEqual(b, b'\x00\x00\x7f\x00')

        a['type'] = 1
        self.assertEqual(a.size, 5)
        if dconfig.ENDIAN == '<':
            self.assertEqual(a.pack(), b'\x01\x7f\x00\x00\x00')
            self.assertEqual(A.unpack(b'\x01\x7f\x00\x00\x00'), a)
            self.assertEqual(A.unpack(b'\x01\x7f\x00\x00\x00').pack(), a.pack())
            b = bytearray(7)
            a.pack_into(b, 1)
            self.assertEqual(b, b'\x00\x01\x7f\x00\x00\x00\x00')
        elif dconfig.ENDIAN == '>':
            self.assertEqual(a.pack(), b'\x01\x00\x00\x00\x7f')
            self.assertEqual(A.unpack(b'\x01\x00\x00\x00\x7f'), a)
            self.assertEqual(A.unpack(b'\x01\x00\x00\x00\x7f').pack(), a.pack())
            b = bytearray(7)
            a.pack_into(b, 1)
            self.assertEqual(b, b'\x00\x01\x00\x00\x00\x7f\x00')

    def test_dynamic_default(self):
        i = 0
        def dyn_default(_obj):
            nonlocal i
            i += 1
            return i

        class A(dict, metaclass=dtypes.DumpyMeta):
            __field_specs__ = (
                dtypes.field('misc', dtypes.UInt8,
                             count=4,
                             default=dyn_default),
            )

        a = A()
        self.assertEqual(a['misc'], [1, 2, 3, 4])
        i = 0
        self.assertEqual(a.pack(), b'\x01\x02\x03\x04')

    def test_exceptions(self):
        with self.assertRaises(RuntimeError):
            dtypes.NoDefault()

        class A(dict, metaclass=dtypes.DumpyMeta): pass
        self.assertFalse(issubclass(A, dtypes.CompositeStructMixin))

        class A(dict, metaclass=dtypes.DumpyMeta):
            __field_specs__ = (
                dtypes.field('field', dtypes.UInt8, count=4),
            )

        a = A()

        with self.assertRaises(KeyError):
            a['not_a_field'] = 1

        with self.assertRaises(ValueError):
            a['field'] = [1, 2, 3, 4, 5]
