# /// script
# requires-python = ">=3.11"
# dependencies = [
# "matplotlib",
# "numpy",
# ]
# ///
from pathlib import Path
from dataclasses import dataclass
import math
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MultipleLocator
import csv
import argparse
from html import escape

@dataclass
class ParsedGpsData:
    timestamp: int
    lat: float
    long: float
    alt: float
    fix_quality: str

class CsvGpsParser:
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.data = []

    def parse_csv(self):
        try:
            with self.file_path.open('r', newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    # Check if we have valid lat/long/alt
                    if not row.get('latitude') or not row.get('longitude') or not row.get('timestamp_ns'):
                        continue
                    
                    try:
                        timestamp = int(row['timestamp_ns'])
                        lat = float(row['latitude'])
                        long = float(row['longitude'])
                        alt = float(row.get('altitude_m') or row.get('altitude') or 0.0)
                        fix_quality = row.get('gga_fix_quality', 'Invalid')
                        
                        self.data.append(ParsedGpsData(timestamp, lat, long, alt, fix_quality))
                    except ValueError:
                        continue
                        
        except Exception as e:
            print(f"Error parsing CSV: {e}")

    def plot_deviation_map(self):
        if not self.data:
            print("No data to plot")
            return
        
        lats = [d.lat for d in self.data]
        lons = [d.long for d in self.data]
        qualities = [d.fix_quality for d in self.data]
        
        # Use first data point as reference
        ref_lat = self.data[0].lat
        ref_lon = self.data[0].long
        cos_lat = math.cos(ref_lat * math.pi / 180)
        
        # Convert to cm relative to first point
        easts = [(lon - ref_lon) * 111320 * cos_lat * 100 for lon in lons] # cm
        norths = [(lat - ref_lat) * 111320 * 100 for lat in lats] # cm
        
        # Colors
        # Mapping based on src/logging.rs
        color_map = {
            'GPS Fix': 'red',
            'DGPS': 'blue',
            'Fixed': 'green',
            'Float': 'yellow',
            'Invalid': 'black',
            'Simulation mode': 'magenta'
        }
        
        colors = [color_map.get(q, 'black') for q in qualities]
        
        # Plot
        plt.figure(figsize=(10, 10))
        # Add line connecting points in chronological order
        plt.plot(easts, norths, color='gray', alpha=0.5, linewidth=1)
        plt.scatter(easts, norths, c=colors, alpha=0.7)
        plt.xlabel('East (cm)')
        plt.ylabel('North (cm)')
        plt.title(f'Deviation Map "{self.file_path.name}" relative to first point')
        plt.grid(True)
        
        # Set equal aspect ratio
        plt.axis('equal')
        
        # Set tick intervals (e.g., every 20 cm for grid squares)
        tick_interval = 60  # cm
        plt.gca().xaxis.set_major_locator(MultipleLocator(tick_interval))
        plt.gca().yaxis.set_major_locator(MultipleLocator(tick_interval))
        
        # Legend
        legend_elements = [
            Line2D([0], [0], marker='o', color='w', label='GPS Fix', markerfacecolor='red', markersize=10),
            Line2D([0], [0], marker='o', color='w', label='DGPS', markerfacecolor='blue', markersize=10),
            Line2D([0], [0], marker='o', color='w', label='Fixed', markerfacecolor='green', markersize=10),
            Line2D([0], [0], marker='o', color='w', label='Float', markerfacecolor='yellow', markersize=10),
        ]
        plt.legend(handles=legend_elements, loc='upper right')
        plt.show()

    def plot_3d_deviation_map(self):
        if not self.data:
            print("No data to plot")
            return
            
        lats = [d.lat for d in self.data]
        lons = [d.long for d in self.data]
        ups = [d.alt for d in self.data]
        qualities = [d.fix_quality for d in self.data]
        
        # Use first data point as reference
        ref_lat = self.data[0].lat
        ref_lon = self.data[0].long
        cos_lat = math.cos(ref_lat * math.pi / 180)
        
        # Convert to m relative to first point
        easts = [(lon - ref_lon) * 111320 * cos_lat for lon in lons] # m
        norths = [(lat - ref_lat) * 111320 for lat in lats] # m
        
        # Colors
        color_map = {
            'GPS Fix': 'red',
            'DGPS': 'blue',
            'Fixed': 'green',
            'Float': 'yellow',
            'Invalid': 'black',
            'Simulation mode': 'magenta'
        }
        
        colors = [color_map.get(q, 'black') for q in qualities]
        
        # Plot
        fig = plt.figure(figsize=(10, 10))
        ax = fig.add_subplot(projection='3d')
        # Add line connecting points in chronological order
        ax.plot(easts, norths, ups, color='gray', alpha=0.5, linewidth=1)
        ax.scatter(easts, norths, ups, c=colors, alpha=0.7)
        ax.set_xlabel('East (m)')
        ax.set_ylabel('North (m)')
        ax.set_zlabel('Up (m)')
        ax.set_title(f'3D Deviation Map of "{self.file_path.name}" relative to first point')
        
        # Legend
        legend_elements = [
            Line2D([0], [0], marker='o', color='w', label='GPS Fix', markerfacecolor='red', markersize=10),
            Line2D([0], [0], marker='o', color='w', label='DGPS', markerfacecolor='blue', markersize=10),
            Line2D([0], [0], marker='o', color='w', label='Fixed', markerfacecolor='green', markersize=10),
            Line2D([0], [0], marker='o', color='w', label='Float', markerfacecolor='yellow', markersize=10),
        ]
        ax.legend(handles=legend_elements, loc='upper right')
        plt.show()

    def export_to_kml(self, output_path: Path):
        if not self.data:
            print("No data to export")
            return
        # Color map with ABGR hex values for KML (alpha ff for opaque)
        color_map_abgr = {
            'GPS Fix': 'ff0000ff', # red
            'DGPS': 'ffff0000', # blue
            'Fixed': 'ff00ff00', # green
            'Float': 'ff00ffff', # yellow
            'Invalid': 'ff000000', # black
            'Simulation mode': 'ffff00ff' # magenta
        }
        # Start building KML string
        kml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        kml += '<kml xmlns="http://www.opengis.net/kml/2.2">\n'
        kml += '<Document>\n'
        kml += f' <name>{escape(self.file_path.name)}</name>\n'
        # Define styles for each fix quality
        unique_qualities = set(d.fix_quality for d in self.data)
        for q in unique_qualities:
            color = color_map_abgr.get(q, 'ff000000') # default black
            kml += f' <Style id="{q.replace(" ", "_")}">\n'
            kml += ' <IconStyle>\n'
            kml += f' <color>{color}</color>\n'
            kml += ' <scale>1.0</scale>\n'
            kml += ' <Icon>\n'
            kml += ' <href>http://maps.google.com/mapfiles/kml/shapes/shaded_dot.png</href>\n'
            kml += ' </Icon>\n'
            kml += ' </IconStyle>\n'
            kml += ' </Style>\n'
        # Add placemarks
        for d in self.data:
            style_id = d.fix_quality.replace(" ", "_")
            kml += ' <Placemark>\n'
            kml += f' <description>Altitude: {d.alt} m\nFix Quality: {d.fix_quality}\nTimestamp: {d.timestamp}</description>\n'
            kml += f' <styleUrl>#{style_id}</styleUrl>\n'
            kml += ' <Point>\n'
            kml += f' <coordinates>{d.long},{d.lat},{d.alt}</coordinates>\n'
            kml += ' </Point>\n'
            kml += ' </Placemark>\n'
        kml += '</Document>\n'
        kml += '</kml>'
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open('w', encoding='utf-8') as f:
            f.write(kml)
        print(f"Exported to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Plot GPS log data')
    parser.add_argument('file', type=Path, help='Path to the GPS CSV log file')
    parser.add_argument('--kml', type=Path, help='Path to export KML file for Google Earth', default=None)
    parser.add_argument('--no-show', action='store_true', help='Skip plot windows (useful for KML export over SSH)')
    args = parser.parse_args()
    if not args.file.exists():
        print(f"File {args.file} does not exist")
        exit(1)
    parser = CsvGpsParser(args.file)
    parser.parse_csv()
    if not args.no_show:
        parser.plot_deviation_map()
        parser.plot_3d_deviation_map()
    if args.kml:
        parser.export_to_kml(args.kml)