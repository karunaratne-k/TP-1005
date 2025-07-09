import serial
import struct

class TPIController:
    def __init__(self, port, timeout=2):
        self.ser = serial.Serial(
            port,
            baudrate=3000000,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            rtscts=True,
            timeout=timeout
        )
        self.enable_user_control()

    def close(self):
        self.ser.close()

    def _build_packet(self, body_bytes):
        body_len = len(body_bytes)
        header = bytearray([
            0xAA, 0x55,
            (body_len >> 8) & 0xFF,
            body_len & 0xFF
        ])
        checksum_base = header[2] + header[3] + sum(body_bytes)
        checksum = (0xFF - (checksum_base & 0xFF)) & 0xFF
        return header + bytearray(body_bytes) + bytes([checksum])

    def _read_response(self):
        while True:
            b1 = self.ser.read(1)
            if b1 == b'\xAA':
                b2 = self.ser.read(1)
                if b2 == b'\x55':
                    break
        length_bytes = self.ser.read(2)
        length = (length_bytes[0] << 8) | length_bytes[1]
        body = self.ser.read(length)
        checksum = self.ser.read(1)
        checksum_base = length_bytes[0] + length_bytes[1] + sum(body)
        expected_checksum = (0xFF - (checksum_base & 0xFF)) & 0xFF
        if checksum[0] != expected_checksum:
            raise ValueError("Checksum mismatch!")
        return body

    def _send_command(self, body_bytes):
        pkt = self._build_packet(body_bytes)
        self.ser.write(pkt)
        return self._read_response()

    def enable_user_control(self):
        """
        Enables user control mode.
        If already enabled, does nothing.
        Verifies success.
        """
        # Check if already in user mode
        try:
            resp = self._send_command([0x07, 0x02])  # Read Model Number
            if resp[0:2] == b'\x07\x02':
                # Already enabled
                return
            elif resp[0:2] == b'\x07\xFF' and resp[2] == 0x01:
                # User control not enabled, proceed
                pass
            else:
                raise RuntimeError(f"Unexpected response while verifying user control: {resp.hex()}")
        except Exception as e:
            # If any communication error, assume not enabled and attempt to enable
            pass

        # Send enable user control command
        resp = self._send_command([0x08, 0x01])
        if resp[:2] != b'\x08\x01':
            raise RuntimeError("Failed to enable user control (unexpected response)")

        # Confirm by reading model number again
        resp = self._send_command([0x07, 0x02])
        if resp[0:2] != b'\x07\x02':
            raise RuntimeError("Failed to verify user control was enabled")

    def read_model_number(self):
        resp = self._send_command([0x07, 0x02])
        return bytes(resp[2:]).decode('ascii').strip()

    def read_serial_number(self):
        resp = self._send_command([0x07, 0x03])
        return bytes(resp[2:]).decode('ascii').strip()

    def read_firmware_version(self):
        resp = self._send_command([0x07, 0x05])
        return bytes(resp[2:]).decode('ascii').strip()

    def read_frequency(self):
        resp = self._send_command([0x07, 0x09])
        freq = int.from_bytes(resp[2:6], byteorder='little')
        return freq  # in kHz

    def set_frequency(self, freq_khz):
        freq_bytes = freq_khz.to_bytes(4, 'little')
        resp = self._send_command([0x08, 0x09] + list(freq_bytes))
        if resp[:2] != b'\x08\x09':
            raise RuntimeError("Failed to set frequency")

    def read_rf_output_state(self):
        resp = self._send_command([0x07, 0x0B])
        return bool(resp[2])

    def set_rf_output(self, on: bool):
        val = 1 if on else 0
        resp = self._send_command([0x08, 0x0B, val])
        if resp[:2] != b'\x08\x0B':
            raise RuntimeError("Failed to set RF output state")

    def read_adc_conversion_averaging(self):
        """
        Reads the number of ADC conversions averaged per measurement.
        Returns integer 1–8.
        """
        resp = self._send_command([0x07, 0x41])
        if resp[:2] != b'\x07\x41':
            raise RuntimeError(f"Unexpected response: {resp.hex()}")
        return resp[2]

    def set_adc_conversion_averaging(self, n):
        """
        Sets the number of ADC conversions to average (1–8).
        n=0 will set 1; n>8 will set 8.
        """
        if n < 0:
            n = 1
        elif n > 8:
            n = 8
        resp = self._send_command([0x08, 0x41, n])
        if resp[:2] != b'\x08\x41':
            raise RuntimeError(f"Failed to set ADC conversion averaging: {resp.hex()}")

    def set_rf_power(self, dbm: int):
        """
        Sets the RF output power in dBm (-90 to +10, depending on unit).
        """
        if dbm < -90 or dbm > +10:
            raise ValueError("RF power out of range (-90 to +10 dBm)")
        value = dbm & 0xFF  # encode as signed byte
        resp = self._send_command([0x08, 0x0A, value])
        if resp[:2] != b'\x08\x0A':
            raise RuntimeError(f"Failed to set RF power: {resp.hex()}")

    def set_analyzer_parameters_v2(
            self,
            start_khz,
            stop_khz,
            step_khz,
            dwell_ms,
            num_points,
            auto_rf,
            max_points_per_packet,
            averages_per_point
    ):
        """
        Sets the analyzer parameters using the 0x08,0x3C command.
        """
        # Sanity checks
        if dwell_ms < 2 or dwell_ms > 500:
            raise ValueError("Dwell time must be 2–500 ms.")
        if averages_per_point < 0:
            averages_per_point = 1
        elif averages_per_point > 10:
            averages_per_point = 10
        if max_points_per_packet > 50:
            max_points_per_packet = 50

        body = [0x08, 0x3C]
        body += list(start_khz.to_bytes(4, 'little'))
        body += list(stop_khz.to_bytes(4, 'little'))
        body += list(step_khz.to_bytes(4, 'little'))
        body += list(dwell_ms.to_bytes(2, 'little'))
        body += list(num_points.to_bytes(4, 'little'))
        body += [1 if auto_rf else 0]
        body += [max_points_per_packet]
        body += [averages_per_point]

        resp = self._send_command(body)
        if resp[:2] != b'\x08\x3C':
            raise RuntimeError(f"Failed to set analyzer parameters: {resp.hex()}")

    def read_analyzer_parameters_v2(self):
        """
        Reads the analyzer parameters using the 0x07,0x3C command.
        Returns a dict of all parameters.
        """
        resp = self._send_command([0x07, 0x3C])
        if resp[:2] != b'\x07\x3C':
            raise RuntimeError(f"Unexpected response: {resp.hex()}")

        start_khz = int.from_bytes(resp[2:6], 'little')
        stop_khz = int.from_bytes(resp[6:10], 'little')
        step_khz = int.from_bytes(resp[10:14], 'little')
        dwell_ms = int.from_bytes(resp[14:16], 'little')
        num_points = int.from_bytes(resp[16:20], 'little')
        auto_rf = resp[20]
        max_pts = resp[21]
        averages = resp[22]

        return {
            "start_khz": start_khz,
            "stop_khz": stop_khz,
            "step_khz": step_khz,
            "dwell_ms": dwell_ms,
            "num_points": num_points,
            "auto_rf": auto_rf,
            "max_points_per_packet": max_pts,
            "averages_per_point": averages
        }

    def start_analyzer_v2(
            self,
            sweeps=0,
            max_ms_between_packets=1000,
            aux_input=0
    ):
        """
        Controls the analyzer to start or stop.
        sweeps: 0=single sweep, 1=continuous
        max_ms_between_packets: 16-bit unsigned int
        aux_input: 0=normal, 1=arm via aux input
        """
        ms_bytes = max_ms_between_packets.to_bytes(2, 'little')
        body = [
            0x08, 0x3D,
            1,  # Start
            sweeps,
            ms_bytes[0],
            ms_bytes[1],
            aux_input
        ]
        resp = self._send_command(body)
        if resp[:2] != b'\x08\x3D':
            raise RuntimeError(f"Failed to start analyzer: {resp.hex()}")

    def read_analyzer_data_v2(self, verbose=True, dump_raw=False):
        """
        Reads analyzer data packets until the analyzer stopped packet is received.
        Returns a dict: {scan_step: dBm}
        """
        all_points = {}
        self.ser.timeout = 2  # Set a 2-second timeout for all reads

        while True:
            # Search for header
            b1 = self.ser.read(1)
            if not b1:
                if verbose:
                    print("Timeout waiting for packet start.")
                continue
            if b1 != b'\xAA':
                continue

            b2 = self.ser.read(1)
            if not b2:
                if verbose:
                    print("Timeout waiting for second header byte.")
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
                    print("Timeout or incomplete body, skipping packet.")
                continue

            checksum = self.ser.read(1)
            if len(checksum) < 1:
                if verbose:
                    print("Timeout reading checksum, skipping packet.")
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
                    print("Checksum error, skipping packet.")
                continue

            cmd = body[:2]

            if cmd == b'\x07\x3E':
                if len(body) < 7:
                    if verbose:
                        print("Malformed data packet, too short.")
                    continue
                n_points = body[2]
                first_step = int.from_bytes(body[3:7], 'little')
                data_bytes = body[7:]
                expected_len = n_points * 4
                if len(data_bytes) < expected_len:
                    if verbose:
                        print("Incomplete data points, skipping packet.")
                    continue
                for i in range(n_points):
                    val_bytes = data_bytes[i * 4:(i + 1) * 4]
                    dBm = struct.unpack('<f', val_bytes)[0]
                    all_points[first_step + i] = dBm
                if verbose:
                    print(f"Received packet with {n_points} points starting at step {first_step}.")

            elif cmd == b'\x07\x3F':
                if verbose:
                    print("Analyzer stopped.")
                break

            else:
                if verbose:
                    print(f"Ignoring unexpected packet: {cmd.hex()}")

        return all_points

    def start_analyzer(self):
        resp = self._send_command([0x08, 0x38, 0x01])
        print("Raw Start Analyzer Response:", resp)
        if resp[:2] != b'\x08\x38':
            raise RuntimeError(f"Unexpected start analyzer response: {resp.hex()}")

    def stop_analyzer(self):
        resp = self._send_command([0x08, 0x38, 0x00])
        if resp[:2] != b'\x08\x38':
            raise RuntimeError("Failed to stop analyzer")

    def read_analyzer_data(self):
        resp = self._send_command([0x07, 0x39])
        if resp[0:2] != b'\x07\x39':
            raise RuntimeError("Unexpected analyzer data response")

        data_bytes = resp[2:]
        num_points = len(data_bytes) // 4
        data = [struct.unpack('<f', data_bytes[i * 4:i * 4 + 4])[0]
                for i in range(num_points)]
        return data

    def wait_for_analyzer_stop(self, timeout=10):
        """
        Waits for the analyzer stopped notification (0x07,0x3A).
        """
        import time
        start = time.time()
        while True:
            if time.time() - start > timeout:
                raise TimeoutError("Analyzer did not signal stop")
            b1 = self.ser.read(1)
            if not b1:
                continue
            if b1 == b'\xAA':
                b2 = self.ser.read(1)
                if b2 != b'\x55':
                    continue
                length_bytes = self.ser.read(2)
                length = (length_bytes[0] << 8) | length_bytes[1]
                body = self.ser.read(length)
                checksum = self.ser.read(1)
                checksum_base = length_bytes[0] + length_bytes[1] + sum(body)
                expected = (0xFF - (checksum_base & 0xFF)) & 0xFF
                if checksum[0] != expected:
                    continue
                if body[0:2] == b'\x07\x3A':
                    return


    # You can keep adding methods using the pattern above

