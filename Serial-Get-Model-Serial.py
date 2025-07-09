import serial
import sys

def build_packet(body_bytes):
    # Convert body_bytes to bytearray if it's a list
    body_bytes = bytearray(body_bytes)
    # Header: 0xAA, 0x55, length (2 bytes)
    body_len = len(body_bytes)
    header = bytearray([
        0xAA,
        0x55,
        (body_len >> 8) & 0xFF,
        body_len & 0xFF
    ])
    # Checksum: 0xFF - sum of length bytes + body bytes
    checksum_base = header[2] + header[3] + sum(body_bytes)
    checksum = (0xFF - (checksum_base & 0xFF)) & 0xFF
    return header + body_bytes + bytes([checksum])

def read_response(ser, expected_len):
    # Read until header found
    while True:
        b1 = ser.read(1)
        if b1 == b'\xAA':
            b2 = ser.read(1)
            if b2 == b'\x55':
                break
    # Read length
    length_bytes = ser.read(2)
    length = (length_bytes[0] << 8) | length_bytes[1]
    body = ser.read(length)
    checksum = ser.read(1)
    # Verify checksum
    checksum_base = length_bytes[0] + length_bytes[1] + sum(body)
    expected_checksum = (0xFF - (checksum_base & 0xFF)) & 0xFF
    if checksum[0] != expected_checksum:
        raise ValueError("Checksum mismatch!")
    return body

def main():
    port = input("Enter COM port (e.g., COM3 or /dev/ttyUSB0): ").strip()

    try:
        ser = serial.Serial(
            port,
            baudrate=3000000,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            rtscts=True,
            timeout=2
        )
    except Exception as e:
        print(f"Error opening port: {e}")
        sys.exit(1)

    # Enable user control
    pkt_enable = build_packet([0x08, 0x01])
    ser.write(pkt_enable)
    _ = read_response(ser, expected_len=2)  # Ignore response

    # Read model number
    pkt_model = build_packet([0x07, 0x02])
    ser.write(pkt_model)
    resp_model = read_response(ser, expected_len=18)
    model_str = bytes(resp_model[2:]).decode('ascii').rstrip()
    print(f"Model Number: {model_str}")

    # Read serial number
    pkt_serial = build_packet([0x07, 0x03])
    ser.write(pkt_serial)
    resp_serial = read_response(ser, expected_len=18)
    serial_str = bytes(resp_serial[2:]).decode('ascii').rstrip()
    print(f"Serial Number: {serial_str}")

    ser.close()

if __name__ == "__main__":
    main()