import csv
from datetime import datetime, date
import hashlib
import struct
from typing import Iterator 
import base64

# Converts a binary checksum to utf-8 str
def checksum_to_str(bs: bytes) -> str:
   return base64.b64encode(bs).decode('utf-8')

# Calculate the MD5 hash checksum of the frame data
def calculate_checksum(data: bytes) -> bytes:
   md5_hash = hashlib.md5()
   md5_hash.update(data)
   return md5_hash.digest()

# Converts string to date using a formatstr
def str_to_datetime(datestr: str, formatstr: str) -> datetime:
   return datetime.strptime(datestr, formatstr)

# Converts date to string represenation using a formatstr
def date_to_bytes(date: datetime, formatstr: str) -> bytes:
   return date.strftime(formatstr).encode()

# Represents the data carried by the frame
class Data:
   timestamp: datetime
   temperature: float
   humidity: float

   def __init__(self, timestamp: datetime, temperature: float, humidity: float) -> None:
      self.timestamp   = timestamp
      self.temperature = temperature
      self.humidity    = humidity

   def __str__(self) -> str:
      return "%s, %.2f, %.2f" % (self.timestamp, self.temperature, self.humidity)

   def to_bytes(self) -> bytes:
      return date_to_bytes(self.timestamp, "%Y-%m-%d %H:%M:%S") + \
             struct.pack('d', self.temperature) + \
             struct.pack('d', self.humidity)

   @staticmethod
   def from_bytes(bs: bytes):
      date = str_to_datetime(bs[0:19].decode(), "%Y-%m-%d %H:%M:%S")
      temp = struct.unpack('d', bs[19:27])[0]
      humi = struct.unpack('d', bs[27:])[0]
      return Data(date, temp, humi)

FRAME_SIZE = 6 + 6 + 4 + 35 + 16

# A data unit to carry data over a network
class Frame:
   # Header
   src: str    # Source address (6 bytes)
   dst: str    # Destination address (6 bytes)
   sno: int    # Frame sequence number (4 bytes)
   # Payload
   dta: Data   # Data payload (35 bytes)
   # Checksum
   chk: bytes  # MD5 hash checksum (16 bytes)
   
   def __init__(self, data:        Data,
                      serial_no:   int, 
                      source:      str          = "013A5B", 
                      destination: str          = "014D8E", 
                      checksum:    bytes | None = None ) -> None:
      self.src = source
      self.dst = destination
      self.sno = serial_no
      self.dta = data
      self.chk = checksum if checksum else calculate_checksum(data.to_bytes())
      # if checksum:
      #    self.chk = checksum
      # else:
      #    self.chk = calculate_checksum(data.to_bytes())

   def __str__(self) -> str:
      return "Frame: %d\n"\
             "  source      : %s\n" \
             "  destination : %s\n" \
             "  data        : %s\n" \
             "  checksum    : %s\n" % (self.sno, self.src, self.dst, self.dta, checksum_to_str(self.chk))
            

   # Convert the frame object to bytes representation
   def to_bytes(self) -> bytes:
      frame_bytes = b''
      frame_bytes += self.src.encode()
      frame_bytes += self.dst.encode()
      frame_bytes += self.sno.to_bytes(4)
      frame_bytes += self.dta.to_bytes()
      frame_bytes += self.chk
      return frame_bytes

   @staticmethod
   def from_bytes(bs: bytes):
      src = bs[0:6].decode()
      dst = bs[6:12].decode()
      sno = int.from_bytes(bs[12:16])
      dta = Data.from_bytes(bs[16:51])
      chk = bs[51:]
      return Frame(dta, sno, src, dst, chk)


# Generate a binary file containing frames from a csv file 
# containing timestamp, temperature, humidity
def csv_to_binary_file(csvfile: str, outfile: str) -> None:
   out = open(outfile, "wb")
   inp = open(csvfile)
   reader = csv.reader(inp)
   i = 1
   for line in reader:
      timestamp, temp, humi = line # destructuring
      data = Data(str_to_datetime(timestamp, "%Y-%m-%d %H:%M:%S"), float(temp), float(humi))
      sno = i
      out.write(Frame(data, sno).to_bytes())
      i += 1

# Reads frame from binary file
def read_frames_from_file(inputfile: str) -> Iterator[Frame]:
   inp = open(inputfile, "rb")
   while True:
      data = inp.read(FRAME_SIZE)
      if data == b'': break # read() retruns empty string when EOF is reached. 
      frame = Frame.from_bytes(data)
      if frame.chk != calculate_checksum(frame.dta.to_bytes()):
         raise ValueError("Invalid Frame")
      yield frame

def main():
   csv_to_binary_file("input_data2.csv", "input_frames.bin")
   frames = read_frames_from_file("input_frames.bin")
   for frame in frames:
      print(frame)

if __name__ == "__main__":
   main()
   
# def mygen(bs):
#    for b in bs:
#       print("Generating value for %d" % b)
#       yield b * 2
#    print("Generator finished.")

# gen = mygen([1,2,3,2,34,565,48,4,0])
# print(gen.__next__())
# print(gen.__next__())
# print(type(gen))
# for element in gen:
#    print("Printing %d" % element)