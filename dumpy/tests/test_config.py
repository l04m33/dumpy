import unittest
import dumpy.config
dumpy.config.ENDIAN = '<'
import dumpy.types


class TestConfig(unittest.TestCase):
    def test_endian_config(self):
        self.assertEqual(dumpy.types.ENDIAN, '<')
        self.assertEqual(dumpy.types.Int32.__struct__.format, b'<i')
