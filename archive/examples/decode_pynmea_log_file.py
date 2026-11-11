# /// script
# requires-python = ">=3.13"
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

# class ParsedGGAData:
   
class GGAParser:
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.data = []

    def parse_gga_sentences(self):
        found_old = False
        try:
            # Try old format: binary with possible $GNGGA
            with self.file_path.open('rb') as file:
                content = file.read()
            pos = 0
            while True:
                pos = content.find(b'$GNGGA', pos)
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
                except UnicodeDecodeError:
                    pass
                if delimiter_len > 0:
                    pos = end + delimiter_len
                else:
                    break
        except Exception:
            pass

        if not found_old:
            # Try new format: text with <NMEA(GNGGA,...)> 
            try:
                with self.file_path.open('r') as file:
                    content = file.read()
                print("Trying new style GGA sentences")
                gga_pattern = re.compile(r'<NMEA\(GNGGA,(.*?)\)>', re.DOTALL)
                matches = gga_pattern.findall(content)
                print("Found new style GGA sentences:", len(matches))
                for match in matches:
                    self.process_new_gga_sentence(match)
            except Exception as e:
                print("Error processing new style GGA sentences:", e)

                pass

    def process_gga_sentence(self, sentence: str):
        """Process old style $GNGGA sentence"""
        parts = sentence.split(',')
        parts[-1] = parts[-1].split('*')[0]  # Remove checksum part
        raw_data = RawGGAData(*parts)
        self.data.append(raw_data)

    def process_new_gga_sentence(self, match: str):
        """Process new style GNGGA, key=value,..."""
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
        self.data.append(raw_data)

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

    def plot_deviation_map(self):
        if not self.data:
            print("No data to plot")
            return
        # Parse lat lon to decimal
        lats = []
        lons = []
        qualities = []
        for d in self.data:
            lat_dec = self.parse_lat(d.lat, d.lat_dir)
            lon_dec = self.parse_lon(d.long, d.long_dir)
            lats.append(lat_dec)
            lons.append(lon_dec)
            qualities.append(int(d.fix_quality))
        mean_lat = np.mean(lats)
        mean_lon = np.mean(lons)
        cos_lat = math.cos(mean_lat * math.pi / 180)
        # Convert to cm relative
        easts = [(lon - mean_lon) * 111320 * cos_lat * 100 for lon in lons]  # cm
        norths = [(lat - mean_lat) * 111320 * 100 for lat in lats]  # cm
        # Colors
        color_map = {
            1: 'red',    # GPS SPS
            2: 'blue',   # Differential GPS
            4: 'green',  # RTK Fixed
            5: 'yellow'  # Float RTK
        }
        colors = [color_map.get(q, 'black') for q in qualities]
        # Plot
        plt.figure(figsize=(10, 10))
        plt.scatter(easts, norths, c=colors, alpha=0.7)
        plt.xlabel('East (cm)')
        plt.ylabel('North (cm)')
        plt.title(f'Deviation Map "{self.file_path.name}" above ground')
        plt.grid(True)
        # Legend
        legend_elements = [
            Line2D([0], [0], marker='o', color='w', label='GPS SPS (1)', markerfacecolor='red', markersize=10),
            Line2D([0], [0], marker='o', color='w', label='Differential GPS (2)', markerfacecolor='blue', markersize=10),
            Line2D([0], [0], marker='o', color='w', label='RTK Fixed (4)', markerfacecolor='green', markersize=10),
            Line2D([0], [0], marker='o', color='w', label='Float RTK (5)', markerfacecolor='yellow', markersize=10),
        ]
        plt.legend(handles=legend_elements, loc='upper right')
        plt.show()

    def plot_3d_deviation_map(self):
        if not self.data:
            print("No data to plot")
            return
        # Parse lat lon alt to decimal
        lats = []
        lons = []
        alts = []
        qualities = []
        for d in self.data:
            if d.lat and d.long and d.alt and d.fix_quality:
                lat_dec = self.parse_lat(d.lat, d.lat_dir)
                lon_dec = self.parse_lon(d.long, d.long_dir)
                alt = float(d.alt)
                lats.append(lat_dec)
                lons.append(lon_dec)
                alts.append(alt)
                qualities.append(int(d.fix_quality))
        if not lats:
            print("No valid data to plot")
            return
        mean_lat = np.mean(lats)
        mean_lon = np.mean(lons)
        mean_alt = np.mean(alts)
        cos_lat = math.cos(mean_lat * math.pi / 180)
        # Convert to cm relative
        easts = [(lon - mean_lon) * 111320 * cos_lat * 100 for lon in lons]  # cm
        norths = [(lat - mean_lat) * 111320 * 100 for lat in lats]  # cm
        ups = [(alt - mean_alt) * 100 for alt in alts]  # cm
        # Colors
        color_map = {
            1: 'red',    # GPS SPS
            2: 'blue',   # Differential GPS
            4: 'green',  # RTK Fixed
            5: 'yellow'  # Float RTK
        }
        colors = [color_map.get(q, 'black') for q in qualities]
        # Plot
        fig = plt.figure(figsize=(10, 10))
        ax = fig.add_subplot(projection='3d')
        ax.scatter(easts, norths, ups, c=colors, alpha=0.7)
        ax.set_xlabel('East (cm)')
        ax.set_ylabel('North (cm)')
        ax.set_zlabel('Up (cm)')
        ax.set_title(f'3D Deviation Map of "{self.file_path.name}" above ground')
        # Legend
        legend_elements = [
            Line2D([0], [0], marker='o', color='w', label='GPS SPS (1)', markerfacecolor='red', markersize=10),
            Line2D([0], [0], marker='o', color='w', label='Differential GPS (2)', markerfacecolor='blue', markersize=10),
            Line2D([0], [0], marker='o', color='w', label='RTK Fixed (4)', markerfacecolor='green', markersize=10),
            Line2D([0], [0], marker='o', color='w', label='Float RTK (5)', markerfacecolor='yellow', markersize=10),
        ]
        ax.legend(handles=legend_elements, loc='upper right')
        plt.show()

if __name__ == "__main__":
    log_file_path = Path("field_tests/lake_johnson/east.log")
    parser = GGAParser(log_file_path)
    parser.parse_gga_sentences()
    parser.plot_deviation_map()
    parser.plot_3d_deviation_map()