# Historical MAARCO material

These files are retained for reference, not used by the active GPS application,
and excluded from the Pi transfer package.

- `field_tests/`: original GPS, correction, sensor recordings, and GPX exports.
- `src/usb_serial.rs`: retired Arduino sensor reader.
- `examples/`: retired motor/PID code, prototype NTRIP clients, old SSH tools,
  and historical plotting experiments. Some contain old connection settings or
  assume the original directory layout; they are not maintained entry points.
- `Cross.toml`: obsolete configuration referring to a missing Dockerfile.

The original source is also available at https://github.com/EMSSL-Lab/MAARCO.
Preserve the root LICENSE when reusing it.
