import csv
from datetime import datetime
import hashlib
import struct
import base64
import matplotlib.pyplot as plt
import matplotlib.colors as mcolor
from enum import StrEnum

# Enum for various format strings
class Format(StrEnum):
   DateTime = "%Y-%m-%d %H:%M:%S"
   Date     = "%Y-%m-%d"
   Time     = "%H:%M:%S"

# Converts a binary checksum to utf-8 str
def checksum_to_str(bs: bytes) -> str:
   return base64.b64encode(bs).decode('utf-8')

# Calculate the MD5 hash checksum of the frame data
def calculate_checksum(data: bytes) -> bytes:
   md5_hash = hashlib.md5()
   md5_hash.update(data)
   return md5_hash.digest()

# Converts string to date using a format
def str_to_datetime(datestr: str, format: Format) -> datetime:
   return datetime.strptime(datestr, format)

# Converts date to bytes represenation using a format
def date_to_bytes(date: datetime, format: Format) -> bytes:
   return date.strftime(format).encode()

# Converts date to string represenation using a format
def date_to_str(date: datetime, format: Format) -> str:
   return date.strftime(format)

# Represents the data carried by the frame
class SensorData:
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
      return date_to_bytes(self.timestamp, Format.DateTime) + \
             struct.pack('d', self.temperature) + \
             struct.pack('d', self.humidity)

   @staticmethod
   def from_bytes(bs: bytes):
      date = str_to_datetime(bs[0:19].decode(), Format.DateTime)
      temp = struct.unpack('d', bs[19:27])[0]
      humi = struct.unpack('d', bs[27:])[0]
      return SensorData(date, temp, humi)

SENSOR_FRAME_SIZE = 6 + 6 + 4 + 35 + 16

# A data unit to carry data over a network
class Frame:
   # Header
   src: str    # Source address (6 bytes)
   dst: str    # Destination address (6 bytes)
   sno: int    # Frame sequence number (4 bytes)
   # Payload
   dta: SensorData   # Data payload (35 bytes)
   # Checksum
   chk: bytes  # MD5 hash checksum (16 bytes)
   
   def __init__(self, data:        SensorData,
                      serial_no:   int, 
                      source:      str          = "013A5B", 
                      destination: str          = "014D8E", 
                      checksum:    bytes | None = None ) -> None:
      self.src = source
      self.dst = destination
      self.sno = serial_no
      self.dta = data
      self.chk = checksum if checksum else calculate_checksum(data.to_bytes())

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
      dta = SensorData.from_bytes(bs[16:51])
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
      # Checking for essentials Frame
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

def scatter_plot(frames: list[Frame], essen_frames: list[Frame]) -> None:
   essen_dates = [date_to_str(frame.dta.timestamp, Format.Date) for frame in essen_frames] 
   essentials  = [date_to_str(frame.dta.timestamp, Format.Time) for frame in essen_frames]
   all_dates   = [date_to_str(frame.dta.timestamp, Format.Date) for frame in frames] 
   all_frames  = [date_to_str(frame.dta.timestamp, Format.Time) for frame in frames]
   # Calculating percentage of essesntial frames
   percentage = len(essentials) * 100 / len(all_frames)
   # Plotting on a Scatter Plot graph
   plt.figure(figsize=(10, 6))
   plt.scatter(all_dates,   all_frames, color=mcolor.CSS4_COLORS["lightskyblue"])
   plt.scatter(essen_dates, essentials, color=mcolor.CSS4_COLORS["blue"])
   plt.xlabel('Frames over a period of Month')
   plt.title("Only %.2f%% Frames are passing from Network Layer to Data Link Layer" % percentage)
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
      data = SensorData(str_to_datetime(timestamp, Format.DateTime), float(temp), float(humi))
      sno = i + 1
      out.write(Frame(data, sno).to_bytes())

# Reads frame from binary file
def read_frames_from_file(inputfile: str) -> list[Frame]:
   inp = open(inputfile, "rb")
   frames = []
   while True:
      data = inp.read(SENSOR_FRAME_SIZE)
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
   csv_to_binary_file("input/data.csv", "input/frames.bin")
   # Represents Frame traveling over the network
   frames  = read_frames_from_file("input/frames.bin")
   sample  = frames[0:24] # Frames received on the first day
   algo    = Algorithm.train(sample)
   essentials = simulate_network_layer(frames, algo)
   for i, frame in enumerate(essentials):
      print("Essential Frame: %d" % (i+1))
      print(frame)

if __name__ == "__main__":
   main()