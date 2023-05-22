import csv
from datetime import datetime
import hashlib
import struct
import base64
from typing import TypeVar, Generic
import matplotlib.pyplot as plt
import matplotlib.colors as mcolor
from enum import Enum, StrEnum

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
   timestamp:   datetime
   temperature: float
   humidity:    float

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

# To toggle between irrigation modes
class Signal(Enum):
   Low  = 2
   High = 3

class SignalData():
   timestamp: datetime
   type: Signal

   def __init__(self, timestamp: datetime, type: Signal) -> None:
      self.timestamp = timestamp
      self.type = type

   def __str__(self) -> str:
      return "%s, %s" % (self.timestamp, self.type)

   def to_bytes(self) -> bytes:
      return self.type.value.to_bytes()

   @staticmethod
   def from_bytes(bs: bytes):
      return int.from_bytes(bs)

SENSOR_FRAME_SIZE = 6 + 6 + 4 + 35 + 16

T = TypeVar("T", SensorData, SignalData)

# A data unit to carry data over a network
class Frame(Generic[T]):
   # Header
   src: str    # Source address (6 bytes)
   dst: str    # Destination address (6 bytes)
   sno: int    # Frame sequence number (4 bytes)
   # Payload
   dta: T  # Data payload (35 bytes)
   # Checksum
   chk: bytes  # MD5 hash checksum (16 bytes)
   
   def __init__(self, data:        T,
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

SensorFrames     = list[Frame[SensorData]]
EssentialsFrames = list[Frame[SensorData]]
SignalFrames     = list[Frame[SignalData]]

class FrameFlag(Enum):
   HTHH = 1
   HTLH = 2
   LTLH = 3
   LTHH = 4
   MTMH = 5
   HTMH = 6
   LTMH = 7
   MTLH = 8
   MTHH = 9
#          Frame                         SignalFrame
# Sensor --------- Network Layer(Algo) --------------- Target Sensor(Sprinkler Irrigation Switch)

# To test for Essential Frames
class Algorithm:
   lt: float # low  temperature
   ht: float # high temperature
   mt: float # mid  temperature
   lh: float # low  humidity
   hh: float # high humidity
   mh: float # mid  humidity

   def __init__(self, lt: float, ht: float, lh: float, hh: float) -> None:
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

   def isEssential(self, frame: Frame) -> FrameFlag | None:
      temp = frame.dta.temperature
      humi = frame.dta.humidity
      flag: FrameFlag | None = None
      # Checking for essentials Frame
      if   temp >= self.ht and humi >= self.hh:
         flag = FrameFlag.HTHH # Low
      elif temp <= self.lt and humi <= self.lh:
         flag = FrameFlag.LTLH # High
      elif temp >= self.ht and humi <= self.lh:
         flag = FrameFlag.HTLH # High
      elif temp <= self.lt and humi >= self.hh:
         flag = FrameFlag.LTHH # Off
      elif temp >= self.ht and abs(humi - self.mh) <= 1.5:
         flag = FrameFlag.HTMH # Low
      elif temp <= self.lt and abs(humi - self.mh) <= 1.5:
         flag = FrameFlag.LTMH # Low
      elif abs(temp - self.mt) <= 1.5 and humi <= self.lh:
         flag = FrameFlag.MTLH # High
      elif abs(temp - self.mt) <= 1.5 and humi >= self.hh:
         flag = FrameFlag.MTHH # off
      elif abs(temp - self.mt) <= 1.5 and abs(humi - self.mh) <= 1.5:
         flag = FrameFlag.MTMH # off
      self.update(temp, humi)
      return flag

   # Decision support system
   def toggle(self, frame: Frame[SensorData], flag: FrameFlag) -> Frame[SignalData] | None:
      match flag:
         case FrameFlag.HTHH: return Frame[SignalData](SignalData(frame.dta.timestamp, Signal.Low),  frame.sno, destination="025C8H")
         case FrameFlag.LTLH: return Frame[SignalData](SignalData(frame.dta.timestamp, Signal.High), frame.sno, destination="025C8H")
         case FrameFlag.HTLH: return Frame[SignalData](SignalData(frame.dta.timestamp, Signal.High), frame.sno, destination="025C8H")
         case FrameFlag.HTMH: return Frame[SignalData](SignalData(frame.dta.timestamp, Signal.Low), frame.sno, destination="025C8H") 
         case FrameFlag.LTMH: return Frame[SignalData](SignalData(frame.dta.timestamp, Signal.Low), frame.sno, destination="025C8H") 
         case FrameFlag.MTLH: return Frame[SignalData](SignalData(frame.dta.timestamp, Signal.High), frame.sno, destination="025C8H") 
         case              _: return None

   @staticmethod
   def train(frames: SensorFrames):
      temps = [frame.dta.temperature for frame in frames] # list comprehension
      humis = [frame.dta.humidity    for frame in frames]
      lt = min(temps)
      ht = max(temps)
      lh = min(humis)
      hh = max(humis)
      return Algorithm(lt, ht, lh, hh)

def scatter_plot(frames: SensorFrames, essen_frames: EssentialsFrames, signal_frames: SignalFrames) -> None:
   essen_dates  = [date_to_str(frame.dta.timestamp, Format.Date) for frame in essen_frames] 
   essen_times  = [date_to_str(frame.dta.timestamp, Format.Time) for frame in essen_frames]
   signal_dates = [date_to_str(frame.dta.timestamp, Format.Date) for frame in signal_frames]
   signal_times = [date_to_str(frame.dta.timestamp, Format.Time) for frame in signal_frames]
   sensor_dates = [date_to_str(frame.dta.timestamp, Format.Date) for frame in frames] 
   sensor_times = [date_to_str(frame.dta.timestamp, Format.Time) for frame in frames]
   # Calculating percentage of essesntial frames
   percentage = len(essen_times) * 100 / len(sensor_times)
   # Plotting on a Scatter Plot graph
   plt.figure(figsize=(10, 6))
   plt.scatter(sensor_dates,   sensor_times, color=mcolor.CSS4_COLORS["lightskyblue"])
   plt.scatter(essen_dates,    essen_times,  color=mcolor.CSS4_COLORS["blue"])
   for i in range(len(signal_frames)):
      if signal_frames[i].dta.type == Signal.High:
         plt.scatter(signal_dates[i], signal_times[i], color=mcolor.CSS4_COLORS["green"])
      else:
         plt.scatter(signal_dates[i], signal_times[i], color=mcolor.CSS4_COLORS["red"])
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
      out.write(Frame[SensorData](data, sno).to_bytes())

# Reads frame from binary file to simulate generation of frames in the sensor
def generate_frames_from_binary(inputfile: str) -> SensorFrames:
   inp = open(inputfile, "rb")
   frames = []
   while True:
      data = inp.read(SENSOR_FRAME_SIZE)
      if data == b'': break # read() retruns empty string when EOF is reached. 
      frame = Frame[SensorData].from_bytes(data)
      if frame.chk != calculate_checksum(frame.dta.to_bytes()):
         raise ValueError("Invalid Frame")
      frames.append(frame)
   return frames

def simulate_network_layer(sensor: SensorFrames, algo: Algorithm) -> tuple[EssentialsFrames, SignalFrames]:
   essentials = []
   signals = []
   for frame in sensor:
      flag = algo.isEssential(frame)
      if flag is None: continue
      essentials.append(frame)
      signal = algo.toggle(frame, flag)
      if signal is None: continue
      signals.append(signal)
   return essentials, signals

def print_frames(frames: list[Frame[T]], msg: str) -> None:
   for i, frame in enumerate(frames):
      print("%s: %d" % (msg, i + 1))
      print(frame)

def main():
   # Data travels over the network in the form of binary, thats why
   csv_to_binary_file("input/data.csv", "input/frames.bin")
   # Represents Frame traveling over the network
   frames  = generate_frames_from_binary("input/frames.bin")
   sample  = frames[0:24] # Frames received on the first day
   algo    = Algorithm.train(sample)
   essentials, signals = simulate_network_layer(frames, algo)
   print("Essential Frame Count: %d" % len(essentials))
   print("   Signal Frame Count: %d" % len(signals))
   # print_frames(essentials, "Essential Frame")
   # print_frames(signals, "Signal Frame")

if __name__ == "__main__":
   main()