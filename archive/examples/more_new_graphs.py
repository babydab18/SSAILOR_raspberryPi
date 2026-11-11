# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "matplotlib",
#     "numpy",
#     "scipy",
# ]
# ///
from pathlib import Path
from dataclasses import dataclass
import math
import re
import collections

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from scipy.ndimage import gaussian_filter1d

# -------------------------
# Data classes
# -------------------------

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
class ENUData:
    east_cm: np.ndarray
    north_cm: np.ndarray
    up_cm: np.ndarray
    fix_quality: np.ndarray

@dataclass
class ErrorStats:
    horiz_cm: np.ndarray
    vert_cm: np.ndarray
    err3d_cm: np.ndarray

@dataclass
class Track:
    s: np.ndarray      # along-track distance (m)
    east_m: np.ndarray
    north_m: np.ndarray

# -------------------------
# GGA parser
# -------------------------

class GGAParser:
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.data: list[RawGGAData] = []

    def parse_gga_sentences(self):
        found_old = False
        try:
            with self.file_path.open('rb') as file:
                content = file.read()
            pos = 0
            while True:
                pos = content.find(b'$GNGGA', pos)
                if pos == -1:
                    break
                found_old = True
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
            try:
                with self.file_path.open('r') as file:
                    content = file.read()
                gga_pattern = re.compile(r'<NMEA\(GNGGA,(.*?)\)>', re.DOTALL)
                matches = gga_pattern.findall(content)
                for match in matches:
                    self.process_new_gga_sentence(match)
            except Exception:
                pass

    def process_gga_sentence(self, sentence: str):
        parts = sentence.split(',')
        parts[-1] = parts[-1].split('*')[0]  # Remove checksum
        if len(parts) < 15:
            parts += [''] * (15 - len(parts))
        raw_data = RawGGAData(*parts[:15])
        self.data.append(raw_data)

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
        self.data.append(raw_data)

    def parse_lat(self, lat_str: str, lat_dir: str):
        if not lat_str:
            return None
        lat = float(lat_str)
        if abs(lat) > 90:  # DDMM.mmmm
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
            return None
        lon = float(long_str)
        if abs(lon) > 180:  # DDDMM.mmmm
            degrees = int(abs(lon) // 100)
            minutes = abs(lon) - degrees * 100
            dec = degrees + minutes / 60.0
            if long_dir == 'W' or lon < 0:
                dec = -dec
        else:
            dec = lon
        return dec

# -------------------------
# ENU + error metrics
# -------------------------

def compute_local_enu(data: list[RawGGAData]) -> ENUData:
    lats = []
    lons = []
    alts = []
    quals = []
    parser_dummy = GGAParser(Path("."))
    for d in data:
        if not (d.lat and d.long and d.alt and d.fix_quality):
            continue
        lat_dec = parser_dummy.parse_lat(d.lat, d.lat_dir)
        lon_dec = parser_dummy.parse_lon(d.long, d.long_dir)
        if lat_dec is None or lon_dec is None:
            continue
        try:
            alt = float(d.alt)
            q = int(d.fix_quality)
        except ValueError:
            continue
        lats.append(lat_dec)
        lons.append(lon_dec)
        alts.append(alt)
        quals.append(q)
    if not lats:
        raise RuntimeError("No valid GGA samples")

    lats = np.array(lats)
    lons = np.array(lons)
    alts = np.array(alts)
    quals = np.array(quals, dtype=int)

    mean_lat = np.mean(lats)
    mean_lon = np.mean(lons)
    mean_alt = np.mean(alts)
    cos_lat = math.cos(mean_lat * math.pi / 180.0)

    east_cm  = (lons - mean_lon) * 111320.0 * cos_lat * 100.0
    north_cm = (lats - mean_lat) * 111320.0 * 100.0
    up_cm    = (alts - mean_alt) * 100.0

    return ENUData(east_cm=east_cm, north_cm=north_cm, up_cm=up_cm, fix_quality=quals)

def compute_error_stats(enu: ENUData) -> ErrorStats:
    horiz_cm = np.sqrt(enu.east_cm**2 + enu.north_cm**2)
    vert_cm  = enu.up_cm
    err3d_cm = np.sqrt(enu.east_cm**2 + enu.north_cm**2 + enu.up_cm**2)
    return ErrorStats(horiz_cm=horiz_cm, vert_cm=vert_cm, err3d_cm=err3d_cm)

def print_basic_stats(label: str, stats: ErrorStats):
    def describe(x: np.ndarray, name: str):
        mean = np.mean(x)
        std = np.std(x)
        rms = math.sqrt(np.mean(x**2))
        p95 = np.percentile(x, 95)
        print(f"{label} {name}: mean={mean:.2f} cm, std={std:.2f} cm, "
              f"RMS={rms:.2f} cm, 95%={p95:.2f} cm")
    describe(stats.horiz_cm, "Horiz")
    describe(np.abs(stats.vert_cm), "VertAbs")
    describe(stats.err3d_cm, "3D")

def summarize_fix_quality(label: str, enu: ENUData):
    total = len(enu.fix_quality)
    counts = collections.Counter(enu.fix_quality)
    print(f"=== {label} fix quality ===")
    for q in sorted(counts.keys()):
        pct = 100.0 * counts[q] / total
        desc = {
            0: "Invalid",
            1: "SPS",
            2: "DGNSS",
            4: "RTK fixed",
            5: "RTK float",
        }.get(q, "Other")
        print(f"  Q={q} ({desc}): {counts[q]} samples ({pct:.1f}%)")

# -------------------------
# Tracks and lateral error
# -------------------------

def build_track_from_enu(enu: ENUData, only_q: int | None = None) -> Track:
    E = enu.east_cm / 100.0
    N = enu.north_cm / 100.0
    if only_q is not None:
        mask = enu.fix_quality == only_q
        E = E[mask]
        N = N[mask]
    dE = np.diff(E, prepend=E[0])
    dN = np.diff(N, prepend=N[0])
    ds = np.sqrt(dE**2 + dN**2)
    s = np.cumsum(ds)
    E_smooth = gaussian_filter1d(E, sigma=5)
    N_smooth = gaussian_filter1d(N, sigma=5)
    return Track(s=s, east_m=E_smooth, north_m=N_smooth)

def resample_track_to_reference(enu: ENUData, ref: Track):
    E = enu.east_cm / 100.0
    N = enu.north_cm / 100.0
    dE = np.diff(E, prepend=E[0])
    dN = np.diff(N, prepend=N[0])
    ds = np.sqrt(dE**2 + dN**2)
    s_run = np.cumsum(ds)

    E_ref = np.interp(s_run, ref.s, ref.east_m)
    N_ref = np.interp(s_run, ref.s, ref.north_m)

    dE_err = E - E_ref
    dN_err = N - N_ref

    dE_ref = np.gradient(E_ref)
    dN_ref = np.gradient(N_ref)
    norm = np.sqrt(dE_ref**2 + dN_ref**2) + 1e-9
    tE = dE_ref / norm
    tN = dN_ref / norm
    lat_err_m = dE_err * (-tN) + dN_err * tE
    return s_run, lat_err_m

# -------------------------
# Plotting
# -------------------------

def plot_deviation_by_height(enu_datasets: dict[str, ENUData]):
    plt.figure(figsize=(8, 10))
    height_colors = {
        "0 ft": "tab:blue",
        "3 ft": "tab:orange",
        "3 ft no plane": "tab:purple",
        "5 ft": "tab:green",
    }
    markers = {1: "x", 2: "s", 4: "o", 5: "^"}

    for label, enu in enu_datasets.items():
        color = height_colors.get(label, "gray")
        for q in np.unique(enu.fix_quality):
            mask = enu.fix_quality == q
            if not np.any(mask):
                continue
            plt.scatter(
                enu.east_cm[mask],
                enu.north_cm[mask],
                s=10,
                c=color,
                marker=markers.get(int(q), "."),
                alpha=0.7,
                label=f"{label}, Q={q}"
            )

    plt.xlabel("East (cm)")
    plt.ylabel("North (cm)")
    plt.title("Volleyball Court Deviation by Height")
    plt.grid(True)
    handles, labels = plt.gca().get_legend_handles_labels()
    uniq = dict(zip(labels, handles))
    plt.legend(uniq.values(), uniq.keys(), fontsize=8, loc="upper right")
    plt.gca().set_aspect("equal", adjustable="box")
    plt.tight_layout()
    plt.show()

def plot_lateral_error_vs_distance(enu_datasets: dict[str, ENUData],
                                   ref_label: str,
                                   ref_q: int = 4):
    ref_track = build_track_from_enu(enu_datasets[ref_label], only_q=ref_q)

    plt.figure(figsize=(10, 6))
    colors = {
        "0 ft": "tab:blue",
        "3 ft": "tab:orange",
        "3 ft no plane": "tab:purple",
        "5 ft": "tab:green",
    }

    for label, enu in enu_datasets.items():
        s, lat_err_m = resample_track_to_reference(enu, ref_track)
        plt.plot(s, lat_err_m * 100.0, ".", markersize=4,
                 color=colors.get(label, "gray"), alpha=0.7, label=label)

    plt.axhline(0, color="k", linewidth=0.5)
    plt.xlabel("Along-track distance (m)")
    plt.ylabel("Lateral error (cm)")
    plt.title("Lateral deviation from reference track")
    handles, labels = plt.gca().get_legend_handles_labels()
    uniq = dict(zip(labels, handles))
    plt.legend(uniq.values(), uniq.keys(), fontsize=8)
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def plot_lateral_error_hist_by_q(label: str, enu: ENUData, ref: Track):
    s, lat_err_m = resample_track_to_reference(enu, ref)
    q_vals = enu.fix_quality
    plt.figure(figsize=(10, 6))
    q_colors = {1: "red", 2: "blue", 4: "green", 5: "gold"}
    for q, color in q_colors.items():
        mask = q_vals == q
        if not np.any(mask):
            continue
        plt.hist(lat_err_m[mask]*100.0, bins=50, histtype="step",
                 density=True, color=color, label=f"Q={q}")
    plt.xlabel("Lateral error (cm)")
    plt.ylabel("Density")
    plt.title(f"Lateral error distribution by fix type ({label})")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()

# -------------------------
# Main
# -------------------------

if __name__ == "__main__":
    # Update these paths/labels to match your logs
    files = {
        "0 ft": Path("field_tests/volleyball/0ft.log"),
        "3 ft": Path("field_tests/volleyball/3ft.log"),
        "3 ft no plane": Path("field_tests/volleyball/3ft_no_ground_plane.log"),
        "5 ft": Path("field_tests/volleyball/5ft.log"),
    }

    enu_datasets: dict[str, ENUData] = {}
    err_datasets: dict[str, ErrorStats] = {}

    for label, path in files.items():
        parser = GGAParser(path)
        parser.parse_gga_sentences()
        enu = compute_local_enu(parser.data)
        enu_datasets[label] = enu
        stats = compute_error_stats(enu)
        err_datasets[label] = stats
        print_basic_stats(label, stats)
        summarize_fix_quality(label, enu)

    # Court shape with Q markers
    plot_deviation_by_height(enu_datasets)

    # Lateral deviation vs distance using 5 ft fixed as reference
    plot_lateral_error_vs_distance(enu_datasets, ref_label="5 ft", ref_q=4)

    # Per-dataset lateral error histograms by Q
    ref_track = build_track_from_enu(enu_datasets["5 ft"], only_q=4)
    for label, enu in enu_datasets.items():
        plot_lateral_error_hist_by_q(label, enu, ref_track)
