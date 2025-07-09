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
        resp = self._send_command([0x08, 0x01])
        if resp[:2] != b'\x08\x01':
            raise RuntimeError("Failed to enable user control")

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

    def set_analyzer_parameters(
            self,
            start_freq_khz,
            stop_freq_khz,
            num_points,
            dwell_per_point_ms,
            mode=0,  # 0=Forward, 1=Reflected, 2=RF vs time
            auto_rf=True,
            continuous=False,
            rf_level_dbm=0.0
    ):
        """
        Configures the analyzer.
        """
        # Compose packet per Section 2.52 (23 bytes total)
        start_freq_bytes = start_freq_khz.to_bytes(4, 'little')
        stop_freq_bytes = stop_freq_khz.to_bytes(4, 'little')
        dwell_bytes = dwell_per_point_ms.to_bytes(4, 'little')
        rf_level_bytes = bytearray(struct.pack('<f', rf_level_dbm))
        body = [
                   0x08, 0x37
               ] + list(start_freq_bytes) \
               + list(stop_freq_bytes) \
               + [num_points] \
               + list(dwell_bytes) \
               + [mode] \
               + [1 if auto_rf else 0] \
               + [1 if continuous else 0] \
               + list(rf_level_bytes) \
               + [0]  # reserved

        resp = self._send_command(body)
        if resp[:2] != b'\x08\x37':
            raise RuntimeError("Failed to set analyzer parameters")

    def read_analyzer_parameters(self):
        resp = self._send_command([0x07, 0x38])
        print("Raw Analyzer Parameters Response:", resp)
        if resp[0:2] != b'\x07\x38':
            raise RuntimeError(f"Unexpected response header: {resp[0:2].hex()}")
        start_freq = int.from_bytes(resp[2:6], 'little')
        stop_freq = int.from_bytes(resp[6:10], 'little')
        num_points = resp[10]
        dwell_ms = int.from_bytes(resp[11:15], 'little')
        mode = resp[15]
        auto_rf = bool(resp[16])
        continuous = bool(resp[17])
        rf_level = struct.unpack('<f', resp[18:22])[0]
        return {
            "start_kHz": start_freq,
            "stop_kHz": stop_freq,
            "num_points": num_points,
            "dwell_ms": dwell_ms,
            "mode": mode,
            "auto_rf": auto_rf,
            "continuous": continuous,
            "rf_level_dBm": rf_level
        }

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

