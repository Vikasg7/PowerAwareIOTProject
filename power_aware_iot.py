import csv
from datetime import datetime
import hashlib
import struct
import base64
import matplotlib.pyplot as plt
import matplotlib.colors as mcolor

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

# To test for Essential Frames
class Algorithm:
   lt: float # low  temperature
   ht: float # high temperature
   mt: float # mid  temperature
   lh: float # low  humidity
   hh: float # high humidity
   mh: float # mid  humidity

   def __init__(self, lt: float = 0, ht: float = 0, lh: float = 0, hh: float = 0) -> None:
      self.ht = ht
      self.lt = lt
      self.mt = (self.ht + self.lt) / 2
      self.hh = hh
      self.lh = lh
      self.mh = (self.hh + self.lh) / 2

   def __str__(self) -> str:
      return "lt: %f  ht: %f mt: %f\nlh: %f  hh: %f mh: %f" % (self.lt, self.ht, self.mt, self.lh, self.hh, self.mh)

   def update(self, temp, humi) -> None:
      if temp < self.lt: self.lt = temp # Updating Temperature
      if temp > self.ht: self.ht = temp 
      self.mt = (self.mt + temp) / 2
      if humi < self.lh: self.lh = humi # Updating Humidity
      if humi > self.hh: self.hh = humi 
      self.mh = (self.mh + humi) / 2

   def test(self, frame: Frame) -> bool:
      temp = frame.dta.temperature
      humi = frame.dta.humidity
      isEssential = False

      if ((temp >= self.ht and humi >= self.hh) or
          (temp <= self.lt and humi <= self.lh) or
          (temp >= self.ht and humi <= self.lh) or
          (temp <= self.lt and humi >= self.hh) or
          (abs(temp - self.mt) <= 1.5 and abs(humi - self.mh) <= 1.5)):
         isEssential = True

      self.update(temp, humi)
      return isEssential

   @staticmethod
   def train(frames: list[Frame]):
      temps = [frame.dta.temperature for frame in frames] # list comprehension
      humis = [frame.dta.humidity    for frame in frames]
      lt = min(temps)
      ht = max(temps)
      lh = min(humis)
      hh = max(humis)
      return Algorithm(lt, ht, lh, hh)

# List Comprehension
# temps = [frame.dta.temperature for frame in frames]
# equivalent to 
# temps = []
# for frame in frames:
#    temps.append(frame.dta.temperature)

def scatter_plot(frames: list[Frame], essen_frames: list[Frame]) -> None:
   essen_dates = [frame.dta.timestamp.strftime("%Y-%m-%d") for frame in essen_frames] 
   essentials  = [frame.dta.timestamp.strftime("%H:%M:%S") for frame in essen_frames]
   
   all_dates  = [frame.dta.timestamp.strftime("%Y-%m-%d") for frame in frames] 
   all_frames = [frame.dta.timestamp.strftime("%H:%M:%S") for frame in frames]

   percentage = len(essentials) * 100 / len(all_frames)

   plt.figure(figsize=(10, 6))
   plt.scatter(all_dates,   all_frames, color=mcolor.CSS4_COLORS["lightskyblue"])
   plt.scatter(essen_dates, essentials, color=mcolor.CSS4_COLORS["blue"])
   plt.xlabel('Frames over a period of Month')
   plt.title("Only %.2f%% Frames are passing from Network Layer => Data Link Layer" % percentage)
   plt.tick_params(axis='x', which='both', bottom=False, labelbottom=False)
   plt.show()

# Generate a binary file containing frames from a csv file 
# containing timestamp, temperature, humidity
def csv_to_binary_file(csvfile: str, outfile: str) -> None:
   out = open(outfile, "wb")
   inp = open(csvfile)
   reader = csv.reader(inp)
   for i, line in enumerate(reader):
      timestamp, temp, humi = line # destructuring
      data = Data(str_to_datetime(timestamp, "%Y-%m-%d %H:%M:%S"), float(temp), float(humi))
      sno = i + 1
      out.write(Frame(data, sno).to_bytes())

# Reads frame from binary file
def read_frames_from_file(inputfile: str) -> list[Frame]:
   inp = open(inputfile, "rb")
   frames = []
   while True:
      data = inp.read(FRAME_SIZE)
      if data == b'': break # read() retruns empty string when EOF is reached. 
      frame = Frame.from_bytes(data)
      if frame.chk != calculate_checksum(frame.dta.to_bytes()):
         raise ValueError("Invalid Frame")
      frames.append(frame)
   return frames

def simulate_network_layer(sensor: list[Frame], checker: Algorithm) -> list[Frame]:
   essential = []
   for frame in sensor:
      if checker.test(frame):
         essential.append(frame)
   return essential

def main():
   # Data travels over the network in the form of binary, thats why
   csv_to_binary_file("input_data.csv", "input_frames.bin")
   # Represents Frame traveling over the network
   frames  = read_frames_from_file("input_frames.bin")
   sample  = frames[0:24] # Frames received on the first day
   algo    = Algorithm.train(sample)
   essentials = simulate_network_layer(frames, algo)
   for i, frame in enumerate(essentials):
      print("Essential Frame: %d" % (i+1))
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

# pip install -r requirements.txt