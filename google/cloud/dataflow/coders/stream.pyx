# Copyright 2016 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

cimport libc.stdlib
cimport libc.string


cdef class OutputStream(object):
  """An output string stream implementation supporting write() and get()."""

  #TODO(robertwb): Consider using raw C++ streams.

  def __cinit__(self):
    self.size = 1024
    self.pos = 0
    self.data = <char*>libc.stdlib.malloc(self.size)

  def __dealloc__(self):
    if self.data:
      libc.stdlib.free(self.data)

  cpdef write(self, bytes b, bint nested=False):
    cdef size_t blen = len(b)
    if nested:
      self.write_var_int64(blen)
    if blen > self.size - self.pos:
      self.extend(blen)
    libc.string.memcpy(self.data + self.pos, <char*>b, blen)
    self.pos += blen

  cpdef write_byte(self, unsigned char val):
    assert 0 <= val <= 0xFF
    if  self.size <= self.pos:
      self.extend(1)
    self.data[self.pos] = val
    self.pos += 1

  cpdef write_var_int64(self, libc.stdint.int64_t signed_v):
    """Encode a long using variable-length encoding to a stream."""
    cdef libc.stdint.uint64_t v = signed_v
    cdef long bits
    while True:
      bits = v & 0x7F
      v >>= 7
      if v:
        bits |= 0x80
      self.write_byte(bits)
      if not v:
        break

  cpdef bytes get(self):
    return self.data[:self.pos]

  cdef extend(self, size_t missing):
    while missing > self.size - self.pos:
      self.size *= 2
    self.data = <char*>libc.stdlib.realloc(self.data, self.size)


cdef class InputStream(object):
  """An input string stream implementation supporting read() and size()."""

  def __init__(self, all):
    self.allc = self.all = all

  cpdef bytes read(self, size_t size):
    self.pos += size
    return self.allc[self.pos - size : self.pos]

  cpdef long read_byte(self) except? -1:
    self.pos += 1
    # Note: the C++ compiler on Dataflow workers treats the char array below as
    # a signed char.  This causes incorrect coder behavior unless explicitly
    # cast to an unsigned char here.
    return <long>(<unsigned char> self.allc[self.pos - 1])

  cpdef size_t size(self) except? -1:
    return len(self.all) - self.pos

  cpdef bytes read_all(self, bint nested=False):
    return self.read(self.read_var_int64() if nested else self.size())

  cpdef libc.stdint.int64_t read_var_int64(self) except? -1:
    """Decode a variable-length encoded long from a stream."""
    cdef long byte
    cdef long bits
    cdef long shift = 0
    cdef libc.stdint.int64_t result = 0
    while True:
      byte = self.read_byte()
      if byte < 0:
        raise RuntimeError('VarInt not terminated.')

      bits = byte & 0x7F
      if (shift >= sizeof(long) * 8 or
          (shift >= (sizeof(long) * 8 - 1) and bits > 1)):
        raise RuntimeError('VarLong too long.')
      result |= bits << shift
      shift += 7
      if not (byte & 0x80):
        break
    return result
