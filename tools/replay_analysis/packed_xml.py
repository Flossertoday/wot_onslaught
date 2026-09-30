# Read-only BigWorld packed XML decoder for local investigation.
# Format reference: chirimenmonster/wotmods-tools/utils/XmlUnpacker.py
import base64
import io
import struct
import xml.etree.ElementTree as ET


def unpack(data):
    if data[:4] != bytes.fromhex('454ea162'):
        return ET.fromstring(data)
    f = io.BytesIO(data)
    f.seek(5)
    names = []
    while True:
        b = bytearray()
        while True:
            ch = f.read(1)
            if not ch:
                raise ValueError('EOF in dictionary')
            if ch == b'\0':
                break
            b.extend(ch)
        if not b:
            break
        names.append(b.decode('utf-8'))

    def u(fmt):
        n = struct.calcsize(fmt)
        return struct.unpack(fmt, f.read(n))[0]

    def node(tag):
        e = ET.Element(tag)
        count = u('<H')
        head = u('<I')
        kids = [(u('<H'), u('<I')) for _ in range(count)]

        def value(target, desc, prev):
            typ = desc >> 28
            end = desc & 0xfffffff
            length = end - prev
            if length < 0:
                raise ValueError('negative range')
            start = f.tell()
            if typ == 0:
                child = node(target.tag)
                target.text = child.text
                target.extend(child)
            else:
                raw = f.read(length)
                if len(raw) != length:
                    raise ValueError('EOF')
                if typ == 1:
                    target.text = raw.decode('utf-8')
                elif typ == 2:
                    target.text = str(int.from_bytes(raw, 'little', signed=True))
                elif typ == 3:
                    target.text = ' '.join(str(x) for x in struct.unpack('<' + 'f' * (length // 4), raw))
                elif typ == 4:
                    target.text = 'true' if any(raw) else 'false'
                elif typ == 5:
                    target.text = base64.b64encode(raw).decode('ascii')
                else:
                    raise ValueError(typ)
            if f.tell() != start + length:
                raise ValueError(('range mismatch', tag, length, f.tell() - start))
            return end

        offset = value(e, head, 0)
        for idx, desc in kids:
            child = ET.SubElement(e, names[idx])
            offset = value(child, desc, offset)
        return e

    root = node('root')
    if f.tell() != len(data):
        raise ValueError('unconsumed data')
    return root
