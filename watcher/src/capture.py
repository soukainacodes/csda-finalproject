"""Read the sniffer's JSON record stream over USB serial."""
import json
import time


def _parse_line(line: str):
    line = line.strip()
    if not line.startswith("{"):
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def capture_window(seconds: float, port: str, baud: int) -> list:
    """Collect beacon/probe records for `seconds`. Requires pyserial.

    Opens with DTR/RTS deasserted so we do NOT reset the sniffer (its CP2102
    reset line is wired to those) between rounds, the sniffer keeps running.
    """
    import serial  # imported lazily so the synth pipeline needs no hardware deps
    records = []
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = baud
    ser.timeout = 1
    ser.dtr = False
    ser.rts = False
    ser.open()
    try:
        end = time.time() + seconds
        while time.time() < end:
            raw = ser.readline().decode("utf-8", "ignore")
            obj = _parse_line(raw)
            if obj and obj.get("k") in ("beacon", "probe_resp"):
                records.append(obj)
    finally:
        ser.close()
    return records


def stream(port: str, baud: int):
    """Yield records forever (for live dashboards)."""
    import serial
    with serial.Serial(port, baud, timeout=1) as ser:
        while True:
            obj = _parse_line(ser.readline().decode("utf-8", "ignore"))
            if obj:
                yield obj
