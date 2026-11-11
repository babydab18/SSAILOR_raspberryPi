# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "matplotlib",
#     "numpy",
# ]
# ///
from pathlib import Path
from dataclasses import dataclass
import math
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import re

@dataclass
class RawGGAData:
    talker: str
    utc: str
    lat: str
    lat_dir: str
    long: str
    long_dir: str
    fix_quality: str
    num_sat_used: str
    hdop: str
    alt: str
    alt_unit: str
    geoid_sep: str
    geoid_sep_unit: str
    age_gps_data: str
    ref_station_id: str

@dataclass
class RawRMCData:
    talker: str
    utc: str
    status: str
    lat: str
    lat_dir: str
    long: str
    long_dir: str
    speed: str
    track: str
    date: str
    mag_var: str
    mag_dir: str
    mode: str
    nav_status: str

@dataclass
class GPSData:
    utc: str
    lat: float
    lon: float
    alt: float
    quality: int
    speed_knots: float = None
    heading: float = None

class GGAParser:
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.gga_data = {}
        self.rmc_data = {}
        self.data = []

    def parse_sentences(self):
        found_old = False
        # Try old format: binary with possible $GNGGA or $GNRMC
        with self.file_path.open('rb') as file:
            content = file.read()
        pos = 0
        while True:
            pos = min(content.find(b'$GNGGA', pos), content.find(b'$GNRMC', pos))
            if pos == -1:
                break
            found_old = True
            # Try to find \r\n first
            end = content.find(b'\r\n', pos)
            delimiter_len = 2
            if end == -1:
                end = content.find(b'\n', pos)
                delimiter_len = 1
            if end == -1:
                end = len(content)
                delimiter_len = 0
            sentence_bytes = content[pos:end]
            try:
                sentence = sentence_bytes.decode('ascii')
                if sentence.startswith('$GNGGA'):
                    self.process_gga_sentence(sentence)
                elif sentence.startswith('$GNRMC'):
                    self.process_rmc_sentence(sentence)
            except UnicodeDecodeError:
                pass
            if delimiter_len > 0:
                pos = end + delimiter_len
            else:
                break

        if not found_old:
            # Try new format: text with <NMEA(GNGGA,...)> or <NMEA(GNRMC,...)> 
            with self.file_path.open('r') as file:
                content = file.read()
            pattern = re.compile(r'<NMEA\((GN\w+), (.*?)\)>', re.DOTALL)
            matches = pattern.finditer(content)
            for match in matches:
                sentence_type = match.group(1)
                params = match.group(2)
                if sentence_type == 'GNGGA':
                    self.process_new_gga_sentence(params)
                elif sentence_type == 'GNRMC':
                    self.process_new_rmc_sentence(params)

        # Combine data
        utcs = sorted(set(list(self.gga_data.keys()) + list(self.rmc_data.keys())))
        for utc in utcs:
            gga = self.gga_data.get(utc)
            rmc = self.rmc_data.get(utc)
            if gga:
                lat = self.parse_lat(gga.lat, gga.lat_dir)
                lon = self.parse_lon(gga.long, gga.long_dir)
                alt = float(gga.alt) if gga.alt else 0.0
                quality = int(gga.fix_quality) if gga.fix_quality else 0
                speed_knots = float(rmc.speed) if rmc and rmc.speed else None
                heading = float(rmc.track) if rmc and rmc.track else None
                self.data.append(GPSData(utc, lat, lon, alt, quality, speed_knots, heading))

    def process_gga_sentence(self, sentence: str):
        parts = sentence.split(',')
        parts[-1] = parts[-1].split('*')[0]
        raw_data = RawGGAData(*parts)
        self.gga_data[raw_data.utc] = raw_data

    def process_rmc_sentence(self, sentence: str):
        parts = sentence.split(',')
        parts[-1] = parts[-1].split('*')[0]
        if len(parts) >= 14:
            raw_data = RawRMCData(*parts)
            if raw_data.status == 'A':
                self.rmc_data[raw_data.utc] = raw_data

    def process_new_gga_sentence(self, match: str):
        parts = [p.strip() for p in match.split(',')]
        data_dict = {'talker': '$GNGGA'}
        for p in parts:
            if '=' in p:
                key, val = [x.strip() for x in p.split('=', 1)]
                data_dict[key] = val
        raw_data = RawGGAData(
            talker=data_dict.get('talker', '$GNGGA'),
            utc=data_dict.get('time', ''),
            lat=data_dict.get('lat', ''),
            lat_dir=data_dict.get('NS', ''),
            long=data_dict.get('lon', ''),
            long_dir=data_dict.get('EW', ''),
            fix_quality=data_dict.get('quality', ''),
            num_sat_used=data_dict.get('numSV', ''),
            hdop=data_dict.get('HDOP', ''),
            alt=data_dict.get('alt', ''),
            alt_unit=data_dict.get('altUnit', ''),
            geoid_sep=data_dict.get('sep', ''),
            geoid_sep_unit=data_dict.get('sepUnit', ''),
            age_gps_data=data_dict.get('diffAge', ''),
            ref_station_id=data_dict.get('diffStation', '')
        )
        self.gga_data[raw_data.utc] = raw_data

    def process_new_rmc_sentence(self, match: str):
        parts = [p.strip() for p in match.split(',')]
        data_dict = {'talker': '$GNRMC'}
        for p in parts:
            if '=' in p:
                key, val = [x.strip() for x in p.split('=', 1)]
                data_dict[key] = val
        raw_data = RawRMCData(
            talker=data_dict.get('talker', '$GNRMC'),
            utc=data_dict.get('time', ''),
            status=data_dict.get('status', ''),
            lat=data_dict.get('lat', ''),
            lat_dir=data_dict.get('NS', ''),
            long=data_dict.get('lon', ''),
            long_dir=data_dict.get('EW', ''),
            speed=data_dict.get('spd', ''),
            track=data_dict.get('cog', ''),
            date=data_dict.get('date', ''),
            mag_var=data_dict.get('mv', ''),
            mag_dir=data_dict.get('mvEW', ''),
            mode=data_dict.get('posMode', ''),
            nav_status=data_dict.get('navStatus', '')
        )
        if raw_data.status == 'A':
            self.rmc_data[raw_data.utc] = raw_data

    def parse_lat(self, lat_str: str, lat_dir: str):
        if not lat_str:
            return 0.0
        lat = float(lat_str)
        if abs(lat) > 90:  # DDMM.mmmm format
            degrees = int(lat // 100)
            minutes = lat - degrees * 100
            dec = degrees + minutes / 60.0
        else:
            dec = lat
        if lat_dir == 'S':
            dec = -dec
        return dec

    def parse_lon(self, long_str: str, long_dir: str):
        if not long_str:
            return 0.0
        lon = float(long_str)
        if abs(lon) > 180:  # DDDMM.mmmm format
            degrees = int(abs(lon) // 100)
            minutes = abs(lon) - degrees * 100
            dec = degrees + minutes / 60.0
            if long_dir == 'W' or lon < 0:
                dec = -dec
        else:
            dec = lon
        return dec

    def plot_deviation_with_prediction(self):
        if not self.data:
            print("No data to plot")
            return
        # Parse data
        lats = [d.lat for d in self.data]
        lons = [d.lon for d in self.data]
        qualities = [d.quality for d in self.data]
        ref_lat = lats[0] if lats else 0.0
        ref_lon = lons[0] if lons else 0.0
        cos_lat = math.cos(math.radians(ref_lat))
        # Convert to cm relative
        easts = [(lon - ref_lon) * 111320 * cos_lat * 100 for lon in lons]  # cm
        norths = [(lat - ref_lat) * 111320 * 100 for lat in lats]  # cm
        # Colors
        color_map = {
            1: 'red',    # GPS SPS
            2: 'blue',   # Differential GPS
            4: 'green',  # RTK Fixed
            5: 'yellow'  # Float RTK
        }
        colors = [color_map.get(q, 'black') for q in qualities]
        # Predictions
        predicted_easts = []
        predicted_norths = []
        predicted_colors = []
        dt = 1.0  # 1 second as per user
        for i in range(len(self.data) - 1):
            d = self.data[i]
            if d.speed_knots is None or d.heading is None:
                continue
            speed_ms = d.speed_knots * 0.514444  # knots to m/s
            ve = speed_ms * math.sin(math.radians(d.heading))  # east
            vn = speed_ms * math.cos(math.radians(d.heading))  # north
            delta_e = ve * dt * 100  # cm
            delta_n = vn * dt * 100  # cm
            curr_e = easts[i]
            curr_n = norths[i]
            pred_e = curr_e + delta_e
            pred_n = curr_n + delta_n
            predicted_easts.append(pred_e)
            predicted_norths.append(pred_n)
            predicted_colors.append(color_map.get(d.quality, 'black'))
        # Plot
        plt.figure(figsize=(10, 10))
        plt.scatter(easts, norths, c=colors, marker='o', alpha=0.7, label='Actual')
        plt.scatter(predicted_easts, predicted_norths, c=predicted_colors, marker='x', alpha=0.7, label='Predicted')
        plt.xlabel('East (cm)')
        plt.ylabel('North (cm)')
        plt.title('Deviation Map with Predictions')
        plt.grid(True)
        # Legend for colors
        legend_elements = [
            Line2D([0], [0], marker='o', color='w', label='GPS SPS (1)', markerfacecolor='red', markersize=10),
            Line2D([0], [0], marker='o', color='w', label='Differential GPS (2)', markerfacecolor='blue', markersize=10),
            Line2D([0], [0], marker='o', color='w', label='RTK Fixed (4)', markerfacecolor='green', markersize=10),
            Line2D([0], [0], marker='o', color='w', label='Float RTK (5)', markerfacecolor='yellow', markersize=10),
        ]
        plt.legend(handles=legend_elements + [Line2D([0], [0], marker='o', color='black', label='Actual', markersize=10),
                                              Line2D([0], [0], marker='x', color='black', label='Predicted', markersize=10)],
                   loc='upper right')
        plt.show()

if __name__ == "__main__":
    log_file_path = Path("field_tests/volleyball/3ft.log")
    parser = GGAParser(log_file_path)
    parser.parse_sentences()
    parser.plot_deviation_with_prediction()