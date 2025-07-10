import serial
import struct
import time

class TPIController:
    def __init__(self, port, baudrate=3000000, timeout=1, retries=3, retry_delay=2):
        """
        Opens the serial connection reliably with retries.
        """
        self.port = port
        self.ser = None

        for attempt in range(1, retries + 1):
            try:
                print(f"Attempt {attempt} to open {port}...")
                self.ser = serial.Serial(
                    port=port,
                    baudrate=baudrate,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    rtscts=True,
                    timeout=timeout
                )
                if self.ser.is_open:
                    print(f"Serial port {self.ser.name} opened successfully.")
                    break
            except serial.SerialException as e:
                print(f"SerialException on attempt {attempt}: {e}")
            except Exception as e:
                print(f"Unexpected error on attempt {attempt}: {e}")

            if attempt < retries:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                raise RuntimeError(f"Failed to open serial port {port} after {retries} attempts.")

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("Serial port closed.")

    def _build_packet(self, body_bytes):
        length = len(body_bytes)
        header = bytearray([0xAA, 0x55, (length >> 8) & 0xFF, length & 0xFF])
        chk = (0xFF - ((header[2] + header[3] + sum(body_bytes)) & 0xFF)) & 0xFF
        return header + bytearray(body_bytes) + bytes([chk])

    def _send_command(self, body_bytes):
        pkt = self._build_packet(body_bytes)
        self.ser.reset_input_buffer()
        self.ser.write(pkt)
        return self._read_response()

    def _read_response(self):
        header = self.ser.read(4)
        if len(header) < 4:
            raise RuntimeError("Timeout waiting for response header.")
        if header[0] != 0xAA or header[1] != 0x55:
            raise RuntimeError(f"Invalid response header: {header.hex()}")
        length = (header[2] << 8) | header[3]
        body = self.ser.read(length)
        if len(body) < length:
            raise RuntimeError("Timeout reading response body.")
        checksum = self.ser.read(1)
        if len(checksum) < 1:
            raise RuntimeError("Timeout reading checksum.")
        chk = (0xFF - ((header[2] + header[3] + sum(body)) & 0xFF)) & 0xFF
        if checksum[0] != chk:
            raise RuntimeError("Checksum mismatch.")
        return body

    def enable_user_control(self):
        try:
            resp = self._send_command([0x07, 0x02])
            if resp[:2] == b'\x07\x02':
                return
        except:
            pass
        resp = self._send_command([0x08, 0x01])
        if resp[:2] != b'\x08\x01':
            raise RuntimeError("Failed to enable user control.")
        resp = self._send_command([0x07, 0x02])
        if resp[:2] != b'\x07\x02':
            raise RuntimeError("User control verification failed.")

    def set_rf_power(self, dbm):
        if dbm < -90 or dbm > 10:
            raise ValueError("RF power out of range.")
        value = dbm & 0xFF
        resp = self._send_command([0x08, 0x0A, value])
        if resp[:2] != b'\x08\x0A':
            raise RuntimeError("Failed to set RF power.")

    def set_analyzer_parameters_v2(self, start_khz, stop_khz, step_khz, dwell_ms, num_points, auto_rf, max_points_per_packet, averages_per_point):
        if dwell_ms < 2 or dwell_ms > 500:
            raise ValueError("Dwell time out of range.")
        if averages_per_point < 1:
            averages_per_point = 1
        elif averages_per_point > 10:
            averages_per_point = 10
        if max_points_per_packet > 50:
            max_points_per_packet = 50
        body = [0x08,0x3C]
        body += list(start_khz.to_bytes(4,'little'))
        body += list(stop_khz.to_bytes(4,'little'))
        body += list(step_khz.to_bytes(4,'little'))
        body += list(dwell_ms.to_bytes(2,'little'))
        body += list(num_points.to_bytes(4,'little'))
        body += [1 if auto_rf else 0]
        body += [max_points_per_packet]
        body += [averages_per_point]
        resp = self._send_command(body)
        if resp[:2] != b'\x08\x3C':
            raise RuntimeError("Failed to set analyzer parameters.")

    def read_analyzer_parameters_v2(self):
        resp = self._send_command([0x07,0x3C])
        if resp[:2] != b'\x07\x3C':
            raise RuntimeError("Unexpected response reading analyzer parameters.")
        return {
            "start_khz": int.from_bytes(resp[2:6],'little'),
            "stop_khz": int.from_bytes(resp[6:10],'little'),
            "step_khz": int.from_bytes(resp[10:14],'little'),
            "dwell_ms": int.from_bytes(resp[14:16],'little'),
            "num_points": int.from_bytes(resp[16:20],'little'),
            "auto_rf": resp[20],
            "max_points_per_packet": resp[21],
            "averages_per_point": resp[22]
        }

    def start_analyzer_v2(self, sweeps=0, max_ms_between_packets=1000, aux_input=0):
        ms_bytes = max_ms_between_packets.to_bytes(2,'little')
        body = [0x08,0x3D,1,sweeps,ms_bytes[0],ms_bytes[1],aux_input]
        resp = self._send_command(body)
        if resp[:2] != b'\x08\x3D':
            raise RuntimeError("Failed to start analyzer.")

    def capture_analyzer_raw(self, duration=4):
        """
        Captures raw bytes from the serial port for `duration` seconds.
        Returns a bytes object.
        """
        import time

        self.ser.timeout = 0.1  # Short timeout for non-blocking reads
        end_time = time.time() + duration
        all_data = bytearray()

        while time.time() < end_time:
            chunk = self.ser.read(1024)
            if chunk:
                all_data.extend(chunk)

        return bytes(all_data)

    def read_analyzer_data_v2(self, verbose=True, dump_raw=False):
        """
        Reads analyzer data packets until the analyzer stopped packet is received.
        Returns a dict: {scan_step: dBm}
        If repeated timeouts occur, returns None.
        """
        all_points = {}
        self.ser.timeout = 2  # 2-second read timeout

        timeout_count = 0

        while True:
            b1 = self.ser.read(1)
            if not b1:
                timeout_count += 1
                if verbose:
                    print("Timeout waiting for packet header.")
                if timeout_count > 2:
                    if verbose:
                        print("Too many consecutive timeouts. Aborting.")
                    return None
                continue
            timeout_count = 0  # reset on any successful read

            if b1 != b'\xAA':
                continue

            b2 = self.ser.read(1)
            if not b2:
                timeout_count += 1
                if verbose:
                    print("Timeout waiting for second header byte.")
                if timeout_count > 2:
                    if verbose:
                        print("Too many consecutive timeouts. Aborting.")
                    return None
                continue
            if b2 != b'\x55':
                continue

            length_bytes = self.ser.read(2)
            if len(length_bytes) < 2:
                if verbose:
                    print("Timeout reading length bytes.")
                continue
            length = (length_bytes[0] << 8) | length_bytes[1]

            body = self.ser.read(length)
            if len(body) < length:
                if verbose:
                    print("Incomplete body.")
                continue

            checksum = self.ser.read(1)
            if len(checksum) < 1:
                if verbose:
                    print("Missing checksum.")
                continue

            if dump_raw:
                print("\n--- Raw Packet ---")
                print(f"Header: aa55")
                print(f"Length: {length}")
                print(f"Body: {body.hex()}")
                print(f"Checksum: {checksum[0]:02X}")

            chk = (0xFF - ((length_bytes[0] + length_bytes[1] + sum(body)) & 0xFF)) & 0xFF
            if checksum[0] != chk:
                if verbose:
                    print("Checksum error.")
                continue

            cmd = body[:2]

            if cmd == b'\x07\x3E':
                if len(body) < 7:
                    if verbose:
                        print("Malformed data packet.")
                    continue
                n_points = body[2]
                first_step = int.from_bytes(body[3:7], 'little')
                data_bytes = body[7:]
                expected_len = n_points * 4
                if len(data_bytes) < expected_len:
                    if verbose:
                        print("Incomplete data points, skipping.")
                    continue
                for i in range(n_points):
                    dBm = struct.unpack('<f', data_bytes[i * 4:(i + 1) * 4])[0]
                    all_points[first_step + i] = dBm
                if verbose:
                    print(f"Received {n_points} points starting at step {first_step}.")

            elif cmd == b'\x07\x3F':
                if verbose:
                    print("Analyzer stopped.")
                break

            else:
                if verbose:
                    print(f"Ignoring unknown packet: {cmd.hex()}")

        return all_points
