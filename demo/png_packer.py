"""
This little script demonstrates how to use ``Dumpy`` composite types.

You can use this script to list the chunks in a PNG file, or embed/extract
arbitrary files into/from PNG files. It has no dependency except ``Dumpy``
itself.

Invoke with no argument to see the full usage.

See http://www.w3.org/TR/PNG/ for the full spec of the PNG format.

"""


import sys
import os
import argparse
import dumpy.config as dc

# You can set the global endianness by assigning a ``struct`` endian character
# to ``dumpy.config.ENDIAN`` **before** importing ``dumpy.types``.
# See the documentation of the ``struct`` module for supported endians.
dc.ENDIAN = '>'     # Big endian for PNG
import dumpy.types as dt


# ================== Data Structures ==================
#
# The PNG format is organized in different types of ``chunks``, and each
# type has its pre-defined structure. The whole PNG structure looks like
# this:
#
# PNG_FILE
#     SIGNATURE
#     CHUNK_1
#     CHUNK_2
#     CHUNK_3
#     ....
#     CHUNK_n
#
# The data structures defined here are to handle the signature and different
# kinds of chunks.
#

# We need to define a class for each composite type. The class
# has to inherit from a mapping type (Usually the built-in ``dict``)
# and use ``dumpy.types.DumpyMeta`` as its meta class.
class PNGSignature(dict, metaclass=dt.DumpyMeta):
    """This class represents the 8-byte PNG signature:
    b'\x89\x50\x4e\x47\x0d\x0a\x1a\x0a'
    """

    # Each class for a composite type must have a ``__field_specs__``
    # member, to specify the fields it contains. ``__field_specs__``
    # can be any iterable that yields field specifications. Since we
    # cannot modify the field specs after the class definition, a tuple
    # is sufficient.
    __field_specs__ = (
        # A field spec is in the form ``(name, type, count, default)``.
        # You can write a tuple directly, or you can also use the convenient
        # function ``dumpy.types.field(...)`` to make the specs more clear.

        # Here we have a field named ``signature``, with a size of 8 bytes.
        dt.field('signature', dt.UInt8, count=8),
    )


class DataIHDR(dict, metaclass=dt.DumpyMeta):
    """This class represents the PNG IHDR chunk, which stores basic
    image properties.
    """

    __field_specs__ = (
        # Unspecified field counts default to 1
        # And unspecified default values default to ``dumpy.types.NoDefault``

        dt.field('width',              dt.UInt32),
        dt.field('height',             dt.UInt32),
        dt.field('bit_depth',          dt.UInt8),
        dt.field('color_type',         dt.UInt8),
        dt.field('compression_method', dt.UInt8),
        dt.field('filter_method',      dt.UInt8),
        dt.field('interlace_method',   dt.UInt8),
    )


class DataDEAD(dict, metaclass=dt.DumpyMeta):
    """This class represents our custom ``deAd`` chunk, which contains
    the name and the content of a single file. The type of a ``deAd`` chunk
    is b'deAd'.
    """

    __field_specs__ = (
        # Field counts and default values can be calculated on the fly.
        # Just pass a callable, and the callable will be called with the
        # object parsed so far as its sole argument, to get the proper value.

        # ``dumpy.types.count_of(...)`` and ``dumpy.types.counted_by(...)``
        # are two convenient functions to calculate lengths.

        dt.field('name_len', dt.UInt32, default=dt.count_of('name')),
        dt.field('name', dt.UInt8, count=dt.counted_by('name_len')),
        dt.field('data_len', dt.UInt32, default=dt.count_of('data')),
        dt.field('data', dt.UInt8, count=dt.counted_by('data_len')),
    )


def get_unknown_data_count(obj):
    """Used by ``DataUnknown`` to determine how many data bytes are there in
    the ``data`` field."""

    # All ``Dumpy`` composite objects have a ``parent`` attribute, which is a
    # weakref to the upper level object. The ``parent`` is ``None`` if the
    # object have no parent.

    # We are dealing with ``DataUnknown`` objects here, so the parent is a
    # ``PNGChunk`` object. The length of the ``data`` field in ``DataUnknown``
    # is determined by the ``length`` field in ``PNGChunk``.
    # See http://www.w3.org/TR/PNG/#5Chunk-layout
    chunk_obj = obj.parent()
    return chunk_obj['length']


class DataUnknown(dict, metaclass=dt.DumpyMeta):
    """This class represents the chunk data that we don't recognize."""

    __field_specs__ = (
        dt.field('data', dt.UInt8, count=get_unknown_data_count),
    )


def get_chunk_data_type(obj):
    """Used by PNGChunk to determine which class to use when dealing with
    chunk data."""

    # ``obj`` is a ``PNGChunk`` instance.
    # Any field with a count larger than 1, or with a dynamic count,
    # will be turned into a ``list``. Here we convert the ``type`` field to
    # ``bytes``, to ease subsequent processing.
    chunk_type = bytes(obj['type'])
    try:
        return obj.data_types[chunk_type]
    except KeyError:
        return DataUnknown


class PNGChunk(dict, metaclass=dt.DumpyMeta):
    __field_specs__ = (
        # The ``data`` field is always a Dumpy composite type, and each
        # composite type automatically provides a ``size`` property.
        dt.field('length', dt.UInt32, default=lambda o: o['data'].size),
        dt.field('type',   dt.UInt8,  count=4),

        # Here's a variable field type. We pass a callable to
        # ``dumpy.types.VariableType``, and this callable will be called when
        # the framework needs to determine which class to use when dealing with
        # this field. The callable works just like dynamic counts and dynamic
        # defaults.
        dt.field('data',   dt.VariableType(get_chunk_data_type)),

        # TODO: Add a calculated default CRC value
        dt.field('crc',    dt.UInt32, default=0),
    )

    data_types = {
        b'IHDR': DataIHDR,
        b'deAd': DataDEAD,
    }


# ================== Data Structures end ==================


def unpack_png_chunks(png_file):
    data = png_file.read()
    offset = 0
    chunks = []
    ended = False

    while not ended:
        chunk = PNGChunk.unpack_from(data, offset)
        chunks.append(chunk)
        offset += chunk.size
        chunk_type = bytes(chunk['type'])
        if chunk_type == b'IEND':
            ended = True

    # ``data`` should be empty at this point, but the PNG format seems to allow
    # trailing bytes, so save the remaining bytes, just in case.
    data = data[offset:]

    return (chunks, data)


def read_png(png_file):
    with png_file:
        data = png_file.read(8)
        signature = PNGSignature.unpack(data)
        if signature['signature'] != [137, 80, 78, 71, 13, 10, 26, 10]:
            raise RuntimeError('Not a PNG file.')
        chunks, extra_data = unpack_png_chunks(png_file)
        return (signature, chunks, extra_data)


def pack_file_into_dead_chunk(extra_file):
    dead = DataDEAD()
    # Field types are checked (partially) when assigning field values:
    # 1. A field with a count larger than 1, or a dynamic count, can only be
    #    assigned a sequence of Dumpy objects, or a sequence of objects that can
    #    be automatically converted to Dumpy objects.
    # 2. A field with a count of 1 can only accept a single Dumpy object, or an
    #    object that can be automatically converted to a Dumpy object.
    # 3. A field with a count smaller than 1 cannot be assigned any value.
    #    Trying to do so will cause a ValueError. Dynamic count functions may
    #    return 0 to indicate that the field doesn't exist.
    dead['name'] = os.path.split(extra_file.name)[1].encode()
    dead['data'] = extra_file.read()

    chunk = PNGChunk()
    chunk['type'] = b'deAd'
    chunk['data'] = dead

    return chunk


def list_chunks(args):
    if args.png_file is None:
        raise RuntimeError('No PNG file to list.')

    signature, chunks, extra_data = read_png(args.png_file)

    for chunk in chunks:
        chunk_type = bytes(chunk['type'])

        print('Chunk: {} {:8} bytes'
                .format(chunk_type.decode(), chunk['length']))

        if chunk_type == b'deAd':
            print('    deAd chunk, file name: {}, file size: {}'
                    .format(repr(bytes(chunk['data']['name']).decode()),
                            chunk['data']['data_len']))
        elif chunk_type in PNGChunk.data_types:
            print('    data: {}'.format(chunk['data']))

    print('{} extra bytes in PNG stream'.format(len(extra_data)))


def pack_files(args):
    if args.png_file is None:
        raise RuntimeError('No PNG file to pack into.')

    if args.output is None:
        raise RuntimeError('Output file not specified.')

    signature, chunks, extra_data = read_png(args.png_file)

    with open(args.output, 'xb') as out_file:
        for f in args.pack:
            print('Packing {} ....'.format(repr(f.name)))
            with f:
                new_chunk = pack_file_into_dead_chunk(f)
                chunks.insert(-1, new_chunk)

        out_file.write(signature.pack())
        for c in chunks:
            out_file.write(c.pack())
        out_file.write(extra_data)

    print('Done.')


def extract_files(args):
    if args.png_file is None:
        raise RuntimeError('No PNG file to extract from.')

    if args.output is None:
        raise RuntimeError('Output directory not specified.')

    if not os.path.isdir(args.output):
        raise RuntimeError('\'--output\' argument is not a directory.')

    signature, chunks, extra_data = read_png(args.png_file)

    for c in chunks:
        if isinstance(c['data'], DataDEAD):
            file_name = bytes(c['data']['name']).decode()
            if file_name in args.extract:
                print('Extracting {} ....'.format(repr(file_name)))
                full_name = os.path.join(args.output, file_name)
                with open(full_name, 'xb') as out_file:
                    out_file.write(bytes(c['data']['data']))
                args.extract.remove(file_name)

    if len(args.extract) > 0:
        print('File(s) not found:')
        for f in args.extract:
            print('    {}'.format(repr(f)))

    print('Done.')


def parse_arguments():
    parser = argparse.ArgumentParser()

    parser.add_argument('png_file',
                        help='The PNG file to read',
                        metavar='PNG',
                        nargs='?',
                        type=argparse.FileType(mode='rb'))

    parser.add_argument('-o', '--output',
                        help='The file to write to. When extracting files, '
                             'this should be a directory for storing extracted '
                             'files',
                        type=str)

    cmd_group = parser.add_mutually_exclusive_group()

    cmd_group.add_argument('-l', '--list-chunks',
                           help='List the chunks in a PNG file',
                           action='store_true')

    cmd_group.add_argument('-p', '--pack',
                           help='Pack file(s) into the PNG file',
                           metavar='FILE',
                           nargs='+',
                           action='append',
                           type=argparse.FileType(mode='rb'))

    cmd_group.add_argument('-x', '--extract',
                           help='Extract files from the PNG file',
                           metavar='FILE',
                           nargs='+',
                           action='append',
                           type=str)

    return (parser, parser.parse_args())


if __name__ == '__main__':
    parser, args = parse_arguments()

    if args.list_chunks:
        list_chunks(args)
    elif args.pack:
        pack_files(args)
    elif args.extract:
        extract_files(args)
    else:
        parser.print_help()
