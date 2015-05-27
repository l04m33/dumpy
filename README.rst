#####
Dumpy
#####

Dumpy is a binary parser with a declarative syntax. All you need to
do is telling the framework what your data look like, and let Dumpy
do the rest.

Dumpy supports python versions >= 3.0.

##########
Installing
##########

Just use pip or tools alike:

.. code-block:: sh

    pip install dumpy

#####
Usage
#####

To parse a pre-defined binary structure, you need to define a class
for that structure. For example, a class for `pascal strings`_ :

.. code-block:: python3

    import dumpy.types as dt

    class PString(dict, metaclass=dt.DumpyMeta):
        __field_specs__ = (
            dt.field('len', dt.UInt8, default=dt.count_of('data')),
            dt.field('data', dt.UInt8, count=dt.counted_by('len')),
        )

    s = PString()
    s['data'] = b'\x01\x02\x03\x04'

    # The length field is calculated automatically.
    assert s['len'] == 4

    assert s.pack() == b'\x04\x01\x02\x03\x04'

    s2 = s.unpack(s.pack())
    assert s2['len'] == 4
    assert bytes(s2['data']) == b'\x01\x02\x03\x04'

See ``demo/png_packer.py`` for a real-world format parser.

.. _pascal strings: http://en.wikipedia.org/wiki/String_(computer_science)#Length-prefixed

############
Known Issues
############

1. The type checking and conversion code in Dumpy is kind of naive,
   It does not check element types in a sequence.

2. Dumpy is **very slow** at current stage. You may not want to use
   it to parse network messages or huge data structures.
