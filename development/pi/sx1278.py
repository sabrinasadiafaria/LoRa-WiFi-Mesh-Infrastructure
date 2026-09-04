"""
Minimal SX1278 / RA-02 LoRa driver for a Raspberry Pi over SPI.

Deliberately small and register-explicit so the PHY matches the ESP32 nodes
EXACTLY. The nodes run the Sandeep Mistry LoRa library; this mirrors its
begin() sequence register for register:

    433 MHz | SF7 | BW 125 kHz | CR 4/5 | explicit header | CRC on
    sync word 0x2A | preamble 8 | PA_BOOST 17 dBm

If any of those disagree with development/phase 4/*.md the Pi will hear
nothing, so they are all named constants here and cross-checked in the
README.

Wiring (Pi SPI0, BCM numbering):
    SX1278        Pi
    -----         --
    VCC     ->    3V3   (pin 1 or 17)   -- never 5V
    GND     ->    GND
    SCK     ->    GPIO11 / SCLK  (pin 23)
    MISO    ->    GPIO9  / MISO  (pin 21)
    MOSI    ->    GPIO10 / MOSI  (pin 19)
    NSS     ->    GPIO8  / CE0   (pin 24)
    RESET   ->    GPIO25         (pin 22)   -- RST_PIN below
    DIO0    ->    (not required - we poll the IRQ register)

Depends on: spidev, gpiozero (RST pulse only).
"""

import time
import spidev

try:
    from gpiozero import OutputDevice
    _HAVE_GPIO = True
except Exception:                      # allows import on a dev machine
    _HAVE_GPIO = False

# ---- pins / bus --------------------------------------------------------------
SPI_BUS = 0
SPI_DEV = 0                            # CE0
SPI_HZ = 5_000_000
RST_PIN = 25                          # BCM

# ---- PHY - MUST match the ESP32 nodes --------------------------------------
FREQ_HZ = 433_000_000
SF = 7
BW_HZ = 125_000
CR_DENOM = 5                          # 4/5
TX_POWER_DBM = 17
SYNC_WORD = 0x2A
PREAMBLE = 8

# ---- registers ------------------------------------------------------------
REG_FIFO = 0x00
REG_OP_MODE = 0x01
REG_FRF_MSB = 0x06
REG_FRF_MID = 0x07
REG_FRF_LSB = 0x08
REG_PA_CONFIG = 0x09
REG_LNA = 0x0C
REG_FIFO_ADDR_PTR = 0x0D
REG_FIFO_TX_BASE_ADDR = 0x0E
REG_FIFO_RX_BASE_ADDR = 0x0F
REG_FIFO_RX_CURRENT_ADDR = 0x10
REG_IRQ_FLAGS = 0x12
REG_RX_NB_BYTES = 0x13
REG_PKT_SNR_VALUE = 0x19
REG_PKT_RSSI_VALUE = 0x1A
REG_MODEM_CONFIG_1 = 0x1D
REG_MODEM_CONFIG_2 = 0x1E
REG_PREAMBLE_MSB = 0x20
REG_PREAMBLE_LSB = 0x21
REG_PAYLOAD_LENGTH = 0x22
REG_MODEM_CONFIG_3 = 0x26
REG_DETECTION_OPTIMIZE = 0x31
REG_DETECTION_THRESHOLD = 0x37
REG_SYNC_WORD = 0x39
REG_DIO_MAPPING_1 = 0x40
REG_VERSION = 0x42
REG_PA_DAC = 0x4D

MODE_LONG_RANGE = 0x80
MODE_SLEEP = 0x00
MODE_STDBY = 0x01
MODE_TX = 0x03
MODE_RX_CONTINUOUS = 0x05

IRQ_TX_DONE = 0x08
IRQ_RX_DONE = 0x40
IRQ_PAYLOAD_CRC_ERROR = 0x20

PA_BOOST = 0x80


class SX1278:
    def __init__(self):
        self.spi = spidev.SpiDev()
        self.spi.open(SPI_BUS, SPI_DEV)
        self.spi.max_speed_hz = SPI_HZ
        self.spi.mode = 0
        self._rst = self._claim_rst_pin() if _HAVE_GPIO else None

    @staticmethod
    def _claim_rst_pin():
        # gpiozero raises here if GPIO25 is already held by another process -
        # almost always a PREVIOUS run of this script still alive (main.py did
        # not exit cleanly: killed with -9, a crashed thread, a second
        # terminal, or the systemd service still running). gpiozero's own
        # atexit hook releases the pin on a clean exit, so a "still claimed"
        # pin means something is still running, not that the wiring is wrong.
        try:
            return OutputDevice(RST_PIN, active_high=False, initial_value=False)
        except Exception as e:
            raise RuntimeError(
                f"Could not claim GPIO{RST_PIN} (SX1278 RST): {e}\n\n"
                f"This almost always means another process still has it open.\n"
                f"  1) ps aux | grep main.py            # find it\n"
                f"  2) kill <pid>            (or: sudo pkill -f main.py)\n"
                f"  3) systemctl is-active sar-pi        # a service instance running too?\n"
                f"     sudo systemctl stop sar-pi\n"
                f"If nothing is running and this still happens after a reboot, "
                f"something else has claimed GPIO{RST_PIN} - move RST to a spare "
                f"GPIO (edit RST_PIN here) rather than fighting it."
            ) from e

    # ---- low level ------------------------------------------------------
    def _read(self, addr):
        return self.spi.xfer2([addr & 0x7F, 0x00])[1]

    def _write(self, addr, val):
        self.spi.xfer2([addr | 0x80, val & 0xFF])

    def _reset(self):
        if self._rst is None:
            return
        self._rst.on()          # active_high=False -> drives pin LOW
        time.sleep(0.01)
        self._rst.off()         # release -> HIGH
        time.sleep(0.01)

    # ---- setup --------------------------------------------------------
    def begin(self):
        self._reset()
        ver = self._read(REG_VERSION)
        if ver != 0x12:
            raise RuntimeError(
                f"SX1278 not found (REG_VERSION=0x{ver:02X}, expected 0x12). "
                "Check wiring and that the module is powered from 3V3.")

        self.sleep()
        self._write(REG_OP_MODE, MODE_LONG_RANGE | MODE_SLEEP)

        # frequency
        frf = int(FREQ_HZ / 61.03515625)
        self._write(REG_FRF_MSB, (frf >> 16) & 0xFF)
        self._write(REG_FRF_MID, (frf >> 8) & 0xFF)
        self._write(REG_FRF_LSB, frf & 0xFF)

        # FIFO base addresses
        self._write(REG_FIFO_TX_BASE_ADDR, 0)
        self._write(REG_FIFO_RX_BASE_ADDR, 0)

        # LNA boost
        self._write(REG_LNA, self._read(REG_LNA) | 0x03)

        # auto AGC
        self._write(REG_MODEM_CONFIG_3, 0x04)

        # PA_BOOST, 17 dBm
        self._write(REG_PA_CONFIG, PA_BOOST | (TX_POWER_DBM - 2))
        self._write(REG_PA_DAC, 0x84)

        self._set_bandwidth(BW_HZ)
        self._set_coding_rate(CR_DENOM)
        self._set_spreading_factor(SF)
        self._set_explicit_header()
        self._enable_crc()
        self._write(REG_SYNC_WORD, SYNC_WORD)
        self._write(REG_PREAMBLE_MSB, (PREAMBLE >> 8) & 0xFF)
        self._write(REG_PREAMBLE_LSB, PREAMBLE & 0xFF)

        self.standby()

    def _set_bandwidth(self, bw):
        idx = {7800: 0, 10400: 1, 15600: 2, 20800: 3, 31250: 4,
               41700: 5, 62500: 6, 125000: 7, 250000: 8, 500000: 9}[bw]
        v = self._read(REG_MODEM_CONFIG_1)
        self._write(REG_MODEM_CONFIG_1, (v & 0x0F) | (idx << 4))

    def _set_coding_rate(self, denom):
        cr = denom - 4                       # 5 -> 1
        v = self._read(REG_MODEM_CONFIG_1)
        self._write(REG_MODEM_CONFIG_1, (v & 0xF1) | (cr << 1))

    def _set_spreading_factor(self, sf):
        if sf == 6:
            self._write(REG_DETECTION_OPTIMIZE, 0xC5)
            self._write(REG_DETECTION_THRESHOLD, 0x0C)
        else:
            self._write(REG_DETECTION_OPTIMIZE, 0xC3)
            self._write(REG_DETECTION_THRESHOLD, 0x0A)
        v = self._read(REG_MODEM_CONFIG_2)
        self._write(REG_MODEM_CONFIG_2, (v & 0x0F) | ((sf << 4) & 0xF0))
        # low data rate optimize: on when symbol time > 16 ms
        sym_ms = (1 << sf) / (BW_HZ / 1000.0)
        v3 = self._read(REG_MODEM_CONFIG_3)
        v3 = (v3 | 0x08) if sym_ms > 16 else (v3 & ~0x08)
        self._write(REG_MODEM_CONFIG_3, v3)

    def _set_explicit_header(self):
        v = self._read(REG_MODEM_CONFIG_1)
        self._write(REG_MODEM_CONFIG_1, v & 0xFE)     # bit0 = 0

    def _enable_crc(self):
        v = self._read(REG_MODEM_CONFIG_2)
        self._write(REG_MODEM_CONFIG_2, v | 0x04)     # bit2 = 1

    # ---- modes -------------------------------------------------------
    def sleep(self):
        self._write(REG_OP_MODE, MODE_LONG_RANGE | MODE_SLEEP)

    def standby(self):
        self._write(REG_OP_MODE, MODE_LONG_RANGE | MODE_STDBY)

    def receive(self):
        self._write(REG_DIO_MAPPING_1, 0x00)
        self._write(REG_FIFO_ADDR_PTR, 0)
        self._write(REG_OP_MODE, MODE_LONG_RANGE | MODE_RX_CONTINUOUS)

    # ---- tx ---------------------------------------------------------
    def send(self, data: bytes, timeout=2.0):
        """Blocking transmit. Returns True on TX_DONE, False on timeout."""
        self.standby()
        self._write(REG_DIO_MAPPING_1, 0x40)
        self._write(REG_FIFO_ADDR_PTR, 0)
        for b in data:
            self._write(REG_FIFO, b)
        self._write(REG_PAYLOAD_LENGTH, len(data))
        self._write(REG_OP_MODE, MODE_LONG_RANGE | MODE_TX)

        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._read(REG_IRQ_FLAGS) & IRQ_TX_DONE:
                self._write(REG_IRQ_FLAGS, IRQ_TX_DONE)
                self.receive()
                return True
            time.sleep(0.002)
        self.receive()
        return False

    # ---- rx ---------------------------------------------------------
    def poll(self):
        """Non-blocking. Returns (payload_bytes, rssi_dbm, snr_db) or None."""
        flags = self._read(REG_IRQ_FLAGS)
        if not (flags & IRQ_RX_DONE):
            return None
        self._write(REG_IRQ_FLAGS, 0xFF)               # clear all
        if flags & IRQ_PAYLOAD_CRC_ERROR:
            return None                               # library CRC rejected it

        n = self._read(REG_RX_NB_BYTES)
        cur = self._read(REG_FIFO_RX_CURRENT_ADDR)
        self._write(REG_FIFO_ADDR_PTR, cur)
        data = bytes(self._read(REG_FIFO) for _ in range(n))

        raw_snr = self._read(REG_PKT_SNR_VALUE)
        snr = (raw_snr - 256 if raw_snr > 127 else raw_snr) / 4.0
        raw_rssi = self._read(REG_PKT_RSSI_VALUE)
        rssi = -164 + raw_rssi                        # 433 MHz -> LF port
        if snr < 0:
            rssi += snr
        return data, int(rssi), round(snr, 1)

    def close(self):
        try:
            self.sleep()
            self.spi.close()
        except Exception:
            pass
        # Release GPIO25 explicitly. gpiozero also does this via its own
        # atexit hook on a clean interpreter exit, but main.py can be asked
        # to shut down and start a fresh SX1278() again in the same process
        # (tests, --fake-radio switching) - only an explicit .close() here
        # guarantees the pin is free before that happens.
        if self._rst is not None:
            try:
                self._rst.close()
            except Exception:
                pass
            self._rst = None
