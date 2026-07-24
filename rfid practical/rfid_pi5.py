# -*- coding: utf-8 -*-
"""
All-in-One RC522 RFID Library for Raspberry Pi 5
Includes low-level SPI driver and student-friendly SimpleRC522 wrapper.
"""

import time
import logging

try:
    import gpiod
    import spidev
    try:
        from gpiod.line import Direction, Value
        GPIOD_V2 = True
    except ImportError:
        GPIOD_V2 = False
except ImportError:
    gpiod = None
    spidev = None

# --- Constants ---

class RC522Registers:
    COMMAND_REG = 0x01
    COM_IRQ_REG = 0x04
    DIV_IRQ_REG = 0x05
    ERROR_REG = 0x06
    STATUS2_REG = 0x08
    FIFO_DATA_REG = 0x09
    FIFO_LEVEL_REG = 0x0A
    CONTROL_REG = 0x0C
    BIT_FRAMING_REG = 0x0D
    TX_CONTROL_REG = 0x14
    CRC_RESULT_REG_MSB = 0x21
    CRC_RESULT_REG_LSB = 0x22
    VERSION_REG = 0x37
    T_MODE_REG = 0x2A
    T_PRESCALER_REG = 0x2B
    T_RELOAD_REG_H = 0x2C
    T_RELOAD_REG_L = 0x2D
    MODE_REG = 0x11
    TX_AUTO_REG = 0x15

class RC522Commands:
    IDLE = 0x00
    CALC_CRC = 0x03
    TRANSCEIVE = 0x0C
    MF_AUTHENT = 0x0E
    SOFT_RESET = 0x0F

class MifareCommands:
    REQUEST_A = 0x26
    ANTICOLL_1 = 0x93
    SELECT_1 = 0x93
    WRITE = 0xA0
    READ = 0x30
    AUTH_A = 0x60

class StatusCodes:
    OK = 0
    ERROR = 1
    TIMEOUT = 3
    AUTH_ERROR = 5


# --- Core Hardware SPI Class ---

class RC522SPILibrary:
    """Pi 5 compatible RC522 SPI hardware driver."""

    def __init__(self, spi_bus=0, spi_device=0, rst_pin=22, debug=False):
        self.logger = logging.getLogger(__name__)
        if debug:
            self.logger.setLevel(logging.DEBUG)

        if not spidev or not gpiod:
            raise RuntimeError("Required hardware libraries 'spidev' and 'gpiod' are missing.")

        self.spi = spidev.SpiDev()
        self.spi.open(spi_bus, spi_device)
        self.spi.max_speed_hz = 1000000
        self.spi.mode = 0
        self.rst_pin = rst_pin

        # Auto-detect valid GPIO chip on Pi 5
        self.chip_path = None
        for candidate in ['/dev/gpiochip4', '/dev/gpiochip0', 'gpiochip4', 'gpiochip0']:
            try:
                with gpiod.Chip(candidate):
                    self.chip_path = candidate
                    break
            except Exception:
                continue

        if not self.chip_path:
            raise RuntimeError("Could not find a valid GPIO chip on this system.")

        if GPIOD_V2:
            self.rst_request = gpiod.request_lines(
                self.chip_path,
                consumer="RC522_RST",
                config={self.rst_pin: gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.ACTIVE)}
            )
        else:
            self.gpio_chip = gpiod.Chip(self.chip_path)
            self.rst_line = self.gpio_chip.get_line(self.rst_pin)
            self.rst_line.request(consumer="RC522_RST", type=gpiod.LINE_REQ_DIR_OUT)

        self._initialized = False
        self.initialize()

    def _set_rst_value(self, val: int):
        if GPIOD_V2:
            self.rst_request.set_value(self.rst_pin, Value.ACTIVE if val == 1 else Value.INACTIVE)
        else:
            self.rst_line.set_value(val)

    def _write_register(self, reg, value):
        self.spi.xfer2([reg << 1 & 0x7E, value])

    def _read_register(self, reg):
        return self.spi.xfer2([(reg << 1 & 0x7E) | 0x80, 0])[1]

    def _set_bit_mask(self, reg, mask):
        self._write_register(reg, self._read_register(reg) | mask)

    def _clear_bit_mask(self, reg, mask):
        self._write_register(reg, self._read_register(reg) & (~mask))

    def _reset(self):
        self._set_rst_value(0)
        time.sleep(0.05)
        self._set_rst_value(1)
        time.sleep(0.05)

    def initialize(self):
        self._reset()
        self._write_register(RC522Registers.COMMAND_REG, RC522Commands.SOFT_RESET)
        time.sleep(0.05)
        self._write_register(RC522Registers.T_MODE_REG, 0x8D)
        self._write_register(RC522Registers.T_PRESCALER_REG, 0x3E)
        self._write_register(RC522Registers.T_RELOAD_REG_L, 30)
        self._write_register(RC522Registers.T_RELOAD_REG_H, 0)
        self._write_register(RC522Registers.TX_AUTO_REG, 0x40)
        self._write_register(RC522Registers.MODE_REG, 0x3D)
        self.antenna_on()
        self._initialized = True

    def antenna_on(self):
        if not (self._read_register(RC522Registers.TX_CONTROL_REG) & 0x03):
            self._set_bit_mask(RC522Registers.TX_CONTROL_REG, 0x03)

    def calculate_crc(self, data):
        self._clear_bit_mask(RC522Registers.DIV_IRQ_REG, 0x04)
        self._set_bit_mask(RC522Registers.FIFO_LEVEL_REG, 0x80)
        for b in data:
            self._write_register(RC522Registers.FIFO_DATA_REG, b)
        self._write_register(RC522Registers.COMMAND_REG, RC522Commands.CALC_CRC)
        
        i = 0xFF
        while True:
            n = self._read_register(RC522Registers.DIV_IRQ_REG)
            i -= 1
            if not ((i != 0) and not (n & 0x04)):
                break
        return [self._read_register(RC522Registers.CRC_RESULT_REG_LSB), self._read_register(RC522Registers.CRC_RESULT_REG_MSB)]

    def cleanup(self):
        if self._initialized:
            self._reset()
        if GPIOD_V2:
            if hasattr(self, 'rst_request') and self.rst_request:
                self.rst_request.release()
        else:
            if hasattr(self, 'rst_line') and self.rst_line:
                self.rst_line.release()
            if hasattr(self, 'gpio_chip') and self.gpio_chip:
                self.gpio_chip.close()
        self.spi.close()

    def _communicate_with_card(self, command, send_data, timeout=0.1):
        wait_irq = 0x30
        self._write_register(RC522Registers.COMMAND_REG, RC522Commands.IDLE)
        self._write_register(RC522Registers.COM_IRQ_REG, 0x7F)
        self._set_bit_mask(RC522Registers.FIFO_LEVEL_REG, 0x80)

        for byte in send_data:
            self._write_register(RC522Registers.FIFO_DATA_REG, byte)

        self._write_register(RC522Registers.COMMAND_REG, command)
        
        if command == RC522Commands.TRANSCEIVE:
            self._set_bit_mask(RC522Registers.BIT_FRAMING_REG, 0x80)

        start_time = time.time()
        while time.time() - start_time < timeout:
            n = self._read_register(RC522Registers.COM_IRQ_REG)
            if n & wait_irq:
                break
        
        self._clear_bit_mask(RC522Registers.BIT_FRAMING_REG, 0x80)

        if time.time() - start_time >= timeout:
            return StatusCodes.TIMEOUT, [], 0

        if self._read_register(RC522Registers.ERROR_REG) & 0x1B:
            return StatusCodes.ERROR, [], 0
            
        status = StatusCodes.OK
        back_data = []
        back_len = 0

        if n & 0x01:
            status = StatusCodes.ERROR

        if command == RC522Commands.TRANSCEIVE:
            fifo_size = self._read_register(RC522Registers.FIFO_LEVEL_REG)
            last_bits = self._read_register(RC522Registers.CONTROL_REG) & 0x07
            back_len = (fifo_size - 1) * 8 + last_bits if last_bits != 0 else fifo_size * 8
            if fifo_size == 0: fifo_size = 1
            if fifo_size > 16: fifo_size = 16

            for _ in range(fifo_size):
                back_data.append(self._read_register(RC522Registers.FIFO_DATA_REG))

        return status, back_data, back_len

    def request(self):
        self._write_register(RC522Registers.BIT_FRAMING_REG, 0x07)
        status, back_data, _ = self._communicate_with_card(RC522Commands.TRANSCEIVE, [MifareCommands.REQUEST_A])
        if status != StatusCodes.OK or len(back_data) != 2:
            return StatusCodes.ERROR, None
        return status, back_data

    def anticoll(self):
        self._write_register(RC522Registers.BIT_FRAMING_REG, 0x00)
        status, back_data, _ = self._communicate_with_card(RC522Commands.TRANSCEIVE, [MifareCommands.ANTICOLL_1, 0x20])
        if status == StatusCodes.OK and len(back_data) == 5:
            checksum = 0
            for i in range(4):
                checksum ^= back_data[i]
            if checksum != back_data[4]:
                return StatusCodes.ERROR, None
            return StatusCodes.OK, back_data[:4]
        return StatusCodes.ERROR, None

    def select_tag(self, uid):
        buf = [MifareCommands.SELECT_1, 0x70] + uid[:4]
        checksum = 0
        for i in range(4):
            checksum ^= uid[i]
        buf.append(checksum)
        buf += self.calculate_crc(buf)
        status, _, back_len = self._communicate_with_card(RC522Commands.TRANSCEIVE, buf)
        return StatusCodes.OK if (status == StatusCodes.OK and back_len == 0x18) else StatusCodes.ERROR

    def authenticate(self, auth_mode, block_addr, key, uid):
        buf = [auth_mode, block_addr] + key + uid[:4]
        status, _, _ = self._communicate_with_card(RC522Commands.MF_AUTHENT, buf)
        if status != StatusCodes.OK or not (self._read_register(RC522Registers.STATUS2_REG) & 0x08):
            return StatusCodes.AUTH_ERROR
        return StatusCodes.OK

    def stop_crypto(self):
        self._clear_bit_mask(RC522Registers.STATUS2_REG, 0x08)

    def write_block(self, block_addr, data_16_bytes):
        buf = [MifareCommands.WRITE, block_addr]
        buf += self.calculate_crc(buf)
        status, back_data, back_len = self._communicate_with_card(RC522Commands.TRANSCEIVE, buf)
        if status != StatusCodes.OK or back_len != 4 or (back_data[0] & 0x0F) != 0x0A:
            return StatusCodes.ERROR

        buf = list(data_16_bytes[:16])
        buf += self.calculate_crc(buf)
        status, back_data, back_len = self._communicate_with_card(RC522Commands.TRANSCEIVE, buf)
        if status != StatusCodes.OK or back_len != 4 or (back_data[0] & 0x0F) != 0x0A:
            return StatusCodes.ERROR
        return StatusCodes.OK

    def read_block(self, block_addr):
        buf = [MifareCommands.READ, block_addr]
        buf += self.calculate_crc(buf)
        status, back_data, _ = self._communicate_with_card(RC522Commands.TRANSCEIVE, buf)
        if status == StatusCodes.OK and len(back_data) == 16:
            return StatusCodes.OK, back_data
        return StatusCodes.ERROR, []


# --- Student Wrapper Class ---

class SimpleRC522:
    """
    A student-friendly wrapper providing simple read() and write(text) string operations.
    """
    def __init__(self, rst_pin: int = 22, start_block: int = 1):
        self.reader = RC522SPILibrary(rst_pin=rst_pin)
        self.start_block = start_block
        self.default_key = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]

    def write(self, text: str) -> bool:
        """Writes up to 16 bytes of text to the RFID card."""
        data_bytes = text.encode('utf-8')
        data_bytes = data_bytes.ljust(16, b'\x00') if len(data_bytes) < 16 else data_bytes[:16]

        try:
            start_time = time.time()
            while time.time() - start_time < 15:  # 15s timeout
                status, _ = self.reader.request()
                if status == StatusCodes.OK:
                    status, uid = self.reader.anticoll()
                    if status == StatusCodes.OK and uid:
                        if self.reader.select_tag(uid) == StatusCodes.OK:
                            if self.reader.authenticate(MifareCommands.AUTH_A, self.start_block, self.default_key, uid) == StatusCodes.OK:
                                write_status = self.reader.write_block(self.start_block, list(data_bytes))
                                self.reader.stop_crypto()
                                return write_status == StatusCodes.OK
                time.sleep(0.1)
            return False
        finally:
            self.reader.cleanup()

    def read(self) -> tuple[list[int] | None, str | None]:
        """Reads stored string and UID from the card."""
        try:
            start_time = time.time()
            while time.time() - start_time < 15:
                status, _ = self.reader.request()
                if status == StatusCodes.OK:
                    status, uid = self.reader.anticoll()
                    if status == StatusCodes.OK and uid:
                        if self.reader.select_tag(uid) == StatusCodes.OK:
                            if self.reader.authenticate(MifareCommands.AUTH_A, self.start_block, self.default_key, uid) == StatusCodes.OK:
                                status, data = self.reader.read_block(self.start_block)
                                self.reader.stop_crypto()
                                if status == StatusCodes.OK:
                                    text = bytes(data).decode('utf-8', errors='ignore').rstrip('\x00')
                                    return uid, text
                time.sleep(0.1)
            return None, None
        finally:
            self.reader.cleanup()