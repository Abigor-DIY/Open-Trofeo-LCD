#!/usr/bin/env python3
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import usb.core
import usb.util


DEFAULT_VENDOR_ID = 0x0416
DEFAULT_PRODUCT_ID = 0x5408

DEFAULT_INTERFACE_NUMBER = 0
DEFAULT_EP_IN = 0x81
DEFAULT_EP_OUT = 0x09
DEFAULT_TIMEOUT_MS = 1000


class TransportError(Exception):
    pass


@dataclass
class DeviceInfo:
    vendor_id: int
    product_id: int
    bus: Optional[int]
    address: Optional[int]
    manufacturer: Optional[str]
    product: Optional[str]
    serial_number: Optional[str]


class TrofeoTransport:
    def __init__(
        self,
        vendor_id: int = DEFAULT_VENDOR_ID,
        product_id: int = DEFAULT_PRODUCT_ID,
        interface_number: int = DEFAULT_INTERFACE_NUMBER,
        ep_in: int = DEFAULT_EP_IN,
        ep_out: int = DEFAULT_EP_OUT,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> None:
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.interface_number = interface_number
        self.ep_in = ep_in
        self.ep_out = ep_out
        self.timeout_ms = timeout_ms

        self.dev: Optional[usb.core.Device] = None
        self._claimed = False
        self._reattach_kernel = False

    def open(self) -> DeviceInfo:
        dev = usb.core.find(idVendor=self.vendor_id, idProduct=self.product_id)
        if dev is None:
            raise TransportError(
                f"Nie znaleziono urządzenia {self.vendor_id:04x}:{self.product_id:04x}"
            )

        self.dev = dev

        try:
            dev.set_configuration()
        except usb.core.USBError:
            pass

        try:
            _ = dev.get_active_configuration()
        except usb.core.USBError as e:
            raise TransportError(f"Nie udało się pobrać aktywnej konfiguracji: {e}") from e

        try:
            if dev.is_kernel_driver_active(self.interface_number):
                dev.detach_kernel_driver(self.interface_number)
                self._reattach_kernel = True
        except (NotImplementedError, usb.core.USBError):
            pass

        try:
            usb.util.claim_interface(dev, self.interface_number)
            self._claimed = True
        except usb.core.USBError as e:
            raise TransportError(
                f"Nie udało się przejąć interfejsu {self.interface_number}: {e}"
            ) from e

        return DeviceInfo(
            vendor_id=self.vendor_id,
            product_id=self.product_id,
            bus=getattr(dev, "bus", None),
            address=getattr(dev, "address", None),
            manufacturer=self._safe_get_string(dev, dev.iManufacturer),
            product=self._safe_get_string(dev, dev.iProduct),
            serial_number=self._safe_get_string(dev, dev.iSerialNumber),
        )

    def close(self) -> None:
        if self.dev is None:
            return

        try:
            if self._claimed:
                usb.util.release_interface(self.dev, self.interface_number)
        except usb.core.USBError:
            pass

        try:
            if self._reattach_kernel:
                self.dev.attach_kernel_driver(self.interface_number)
        except (NotImplementedError, usb.core.USBError):
            pass

        try:
            usb.util.dispose_resources(self.dev)
        except Exception:
            pass

        self.dev = None
        self._claimed = False
        self._reattach_kernel = False

    def write(self, payload: bytes, timeout_ms: Optional[int] = None) -> int:
        if self.dev is None:
            raise TransportError("Urządzenie nie jest otwarte")

        timeout = self.timeout_ms if timeout_ms is None else timeout_ms

        try:
            written = self.dev.write(self.ep_out, payload, timeout=timeout)
            return int(written)
        except usb.core.USBError as e:
            raise TransportError(f"Bulk write EP 0x{self.ep_out:02x} nie powiódł się: {e}") from e

    def read(self, size: int = 512, timeout_ms: Optional[int] = None) -> bytes:
        if self.dev is None:
            raise TransportError("Urządzenie nie jest otwarte")

        timeout = self.timeout_ms if timeout_ms is None else timeout_ms

        try:
            data = self.dev.read(self.ep_in, size, timeout=timeout)
            return bytes(data)
        except usb.core.USBTimeoutError:
            return b""
        except usb.core.USBError as e:
            raise TransportError(f"Bulk read EP 0x{self.ep_in:02x} nie powiódł się: {e}") from e

    def transact(
        self,
        payload: bytes,
        read_size: int = 512,
        write_timeout_ms: Optional[int] = None,
        read_timeout_ms: Optional[int] = None,
        settle_ms: int = 20,
    ) -> bytes:
        self.write(payload, timeout_ms=write_timeout_ms)
        if settle_ms > 0:
            time.sleep(settle_ms / 1000.0)
        return self.read(size=read_size, timeout_ms=read_timeout_ms)

    @staticmethod
    def _safe_get_string(dev: usb.core.Device, index: int) -> Optional[str]:
        if not index:
            return None
        try:
            return usb.util.get_string(dev, index)
        except usb.core.USBError:
            return None
