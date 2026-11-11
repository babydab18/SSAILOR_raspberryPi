import importlib.util
import os
from pathlib import Path
import socket
import tempfile
import threading
import unittest

os.environ.setdefault("MPLBACKEND", "Agg")
ROOT = Path(__file__).resolve().parents[1]

def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

plot = load("gps_plot", "examples/plot_gps_log.py")
capture = load("gps_capture", "tools/capture_serial.py")
bridge = load("gps_bridge", "tools/serial_bridge.py")

class GpsToolsTests(unittest.TestCase):
    def test_current_and_historical_altitude_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            for column in ["altitude_m", "altitude"]:
                path = Path(directory) / f"{column}.csv"
                path.write_text(f"timestamp_ns,latitude,longitude,{column},gga_fix_quality\n1,35,-78,123.5,Fixed\n", encoding="utf-8")
                parser = plot.CsvGpsParser(path)
                parser.parse_csv()
                self.assertEqual(parser.data[0].alt, 123.5)
                self.assertEqual(parser.data[0].fix_quality, "Fixed")

    def test_kml_creates_export_directory_and_escapes_filename(self):
        import xml.etree.ElementTree as ET
        with tempfile.TemporaryDirectory() as directory:
            parser = plot.CsvGpsParser(Path(directory) / "test & run.csv")
            parser.data = [plot.ParsedGpsData(1, 35, -78, 123.5, "Fixed")]
            output = Path(directory) / "exports" / "track.kml"
            parser.export_to_kml(output)
            document = ET.parse(output)
            name = document.find(".//{http://www.opengis.net/kml/2.2}name")
            self.assertEqual(name.text, "test & run.csv")

    def test_capture_refuses_overwriting_an_existing_recording(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.bin"
            path.write_bytes(b"original")
            with self.assertRaises(FileExistsError):
                capture.capture("loop://", 115200, 0.01, path)
            self.assertEqual(path.read_bytes(), b"original")

    def test_bridge_preserves_binary_in_both_directions(self):
        import serial
        payload = bytes([0xd3, 0, 0x13, 0xff, 0, 0x0a, 0x80])
        client, server = socket.socketpair()
        errors = []
        with serial.serial_for_url("loop://", timeout=0.05) as receiver:
            def run():
                try:
                    bridge.bridge(server, receiver)
                except Exception as error:
                    errors.append(error)
                finally:
                    server.close()
            worker = threading.Thread(target=run, daemon=True)
            worker.start()
            with client:
                client.settimeout(3)
                client.sendall(payload)
                result = bytearray()
                while len(result) < len(payload):
                    result.extend(client.recv(len(payload) - len(result)))
                self.assertEqual(result, payload)
            worker.join(timeout=3)
            self.assertFalse(worker.is_alive())
            self.assertFalse(errors)

if __name__ == "__main__":
    unittest.main()
