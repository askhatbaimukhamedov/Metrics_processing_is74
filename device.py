import asyncio
import logging
import os
import struct
from datetime import datetime

from inquirer_plugins.meter_types import NetDevice
from inquirer_plugins.devices.teplocon_01.headers import *
from inquirer_plugins.utils import check_lock, submit_response, connect, check_response, wrap_response
from is74_utils import now


class Crc16Exception(Exception):
    def __init__(self, message):
        self.message = message


class ResponseParseException(Exception):
    def __init__(self, message):
        self.message = message


class StatException(Exception):
    def __init__(self, code_err):
        if code_err:
            self.code_err = code_err


class IncorrectRequest(Exception):
    def __init__(self, message):
        self.message = message


class IncorrectArchDate(Exception):
    def __init__(self, message):
        self.message = message


class TeploconCommon:
    _reader, _writer = None, None

    def __init__(self, ip, port, boudrate=9600, timeout=DEFAULT_TIMEOUT):
        self.ip = ip
        self.port = int(port)

        self.boudrate = BOUDRATES.get(boudrate, 0x35)
        self.timeout = timeout
        self.is_opened = False

        self._service_name = os.environ.get('SERVICE_NAME', self.__class__.__name__)
        self.log = logging.getLogger(self._service_name)
        self.loop = asyncio.get_event_loop()

    @staticmethod
    def compute_crc(data):
        crc = 0xffff

        for item in data:
            crc = crc ^ item
            for count in range(8):
                if crc & 0x1:
                    mask = 0xa001
                else:
                    mask = 0x00
                crc = ((crc >> 1) & 0x7FFF) ^ mask

        if crc < 0:
            crc -= 256

        return chr(crc & 0xFF).encode('latin-1') + chr((crc >> 8) & 0xFF).encode('latin-1')

    @staticmethod
    def join_cmd(*args):
        cmd = []

        for item in args:
            if isinstance(item, list):
                cmd += item
            elif isinstance(item, str):
                cmd += [ord(symb) for symb in item]
            elif isinstance(item, bytes):
                cmd += [symb for symb in item]
            elif isinstance(item, int):
                cmd += bytes([item])
            else:
                cmd.append(item)

        return cmd

    @staticmethod
    def decode(data):
        buffer = []

        for byte in data:
            buffer.append(byte if bin(byte)[1:].count('1') % 2 else byte & 0x7F)

        return bytes(buffer)

    @staticmethod
    def encode(data):
        buffer = []

        for byte in data:
            buffer.append(byte | 0x80 if bin(byte).count('1') % 2 else byte)

        return bytes(buffer)

    async def form_cmd_async(self, *args):
        buffer = b''

        buffer += bytes(self.join_cmd(*args))
        buffer += bytes(self.compute_crc(buffer))

        return buffer

    async def send_async(self, data):
        if not self._writer.is_closing():
            # self.log.info(f'Send: {data!r}')
            self._writer.write(data)
            await self._writer.drain()
            return await self.receive_async()

        self.log.info('Sending failed')

    async def receive_async(self):
        return await self._reader.read(BUFFER_SIZE)

    async def close_async(self):
        self.log.info('Close the connection')
        self._writer.close()
        self.is_opened = False

        await self._writer.wait_closed()


class Device(NetDevice, TeploconCommon):

    def __init__(self, **kwargs):

        super().__init__(**kwargs)

        self.settings_keys = [
            'version', 'serial', 'min',
            'hour', 'day', 'month', 'year'
        ]

        self.int_current_keys = [
            'tраб', 'Qd', 'M1', 'M2'
        ]

        self.per_current_keys = [
            'G1', 'G2', 'T1', 'T2',
            'P1', 'P2', 'Qd'
        ]

        self.int_archive_keys = [
            'tраб', 'T1', 'T2', 'P1', 'P2',
            'M1', 'M2', 'Qd', 'wN_arc'
        ]

        self.funcs_and_commands_table = {

            'read_settings': [self._parse_settings, CMD_READ_SETTINGS],
            'read_stat_time': [self._parse_stat_time, CMD_READ_STAT_TIME],

            'read_current': [self._parse_current, CMD_READ_CUR_PARAMS],
            'read_additional': [self._parse_additional, CMD_READ_ADD_PARAMS],

            'read_arch_month': [self._parse_month, CMD_READ_MONTH_ARCH],
            'read_arch_day': [self._parse_day, CMD_READ_DAY_ARCH],
            'read_arch_hour': [self._parse_hour, CMD_READ_HOUR_ARCH],

            'scan_arch_month': [self._parse_month, CMD_SCAN_MONTH_ARCH],
            'scan_arch_day': [self._parse_day, CMD_SCAN_DAY_ARCH],
            'scan_arch_hour': [self._parse_hour, CMD_SCAN_HOUR_ARCH],
        }

    async def open(self):
        self._reader, self._writer = await asyncio.open_connection(self.ip, self.port)
        self.is_opened = True

        return self.is_opened

    async def _get_scheme(self):
        settings = await self.read_metrics(0, type_metrics='read_settings')
        return {
            'current_time': datetime(settings['year'], settings['month'],
                                     settings['day'], settings['hour'], settings['min']),
            'serial': settings['serial'],
            'subsystems': DEFAULT_SUBSYSTEMS
        }

    async def get_scheme(self):
        if not self._scheme:
            self._scheme = await self._get_scheme()

        return self._scheme

    async def get_config(self):
        return {
            'data_availability': [
                (PERIOD_CURRENT, False),
                (INTEGRAL_CURRENT, False),
                (INTEGRAL_MONTH, True),
                (INTEGRAL_DAY, True),
                (INTEGRAL_HOUR, True),
            ],
        }

    async def check_device(self):
        scheme = await self.get_scheme()

        response = [
            f'{self.ip}:{self.port}/{self.dev_num}',
            str(scheme['current_time']),
            str(scheme['serial']),
        ]

        return '; '.join(response)

    @staticmethod
    def get_narc(last_date):
        if last_date is None:
            return 0
        return ((last_date.year - 2000) * 12 + last_date.month - 1) % 50

    def eval_num_page(self, last_num_page):
        now_num_page = self.get_narc(now())

        if now_num_page - last_num_page < 0:
            raise IncorrectArchDate('eval_num_page: Incorrect las_date')

        return now_num_page - last_num_page

    async def read_metrics(self, *args, type_metrics=None):
        if not type_metrics:
            raise IncorrectRequest('read_metrics: Variable type_metrics is None')

        raw = await self.form_cmd_async(self.dev_num, self.funcs_and_commands_table[type_metrics][1], list(args))
        response = await self.send_async(raw)

        return self._parse_metrics(type_metrics, response, args)

    def _parse_metrics(self, func, raw, args):
        if not raw:
            raise ResponseParseException('_parse_metrics: Empty string')

        if self.compute_crc(raw[:-2]) != raw[-2:]:
            raise Crc16Exception('_parse_metrics: Checksum is incorrect')

        return self.funcs_and_commands_table[func][0](raw[3:-2], args)

    @staticmethod
    def _parse_settings(raw, args):
        response = {}

        for key, value in zip(COMMON_DATA_STRUCT[SETTINGS], struct.unpack('<3f15b', raw)):
            if key == SERNUM:
                response[key] = str(round(value))

            elif key == CUR_YEAR:
                response[key] = value + 2000

            elif type(value) is float:
                response[key] = round(value, 3)

            else:
                response[key] = value

        return response

    @staticmethod
    def _parse_stat_time(raw, args):
        return {
            key: value for key, value in zip(COMMON_DATA_STRUCT[STAT_TIME], struct.unpack('<7b1L2b', raw))
        }

    @staticmethod
    def _parse_current(raw, args):
        current_params = struct.unpack('<4L2b7f', raw)
        integral_data, period_data = current_params[:6], current_params[6:]

        result_period = {key: value for key, value in zip(COMMON_DATA_STRUCT[PERIOD_CURRENT], period_data)}
        result_integral = {key: value for key, value in zip(COMMON_DATA_STRUCT[INTEGRAL_CURRENT], integral_data)}

        return [
            result_period,
            result_integral
        ]

    @staticmethod
    def _parse_additional(raw, args):
        additional_param = struct.unpack('<4L2f2H1f1b1H18b', raw)
        integral_data, period_data = additional_param[:16], additional_param[16:]

        result_period = {key: value for key, value in zip(COMMON_DATA_STRUCT[PERIOD_ADDITIONAL], period_data)}
        result_integral = {key: value for key, value in zip(COMMON_DATA_STRUCT[INTEGRAL_ADDITIONAL], integral_data)}

        return [
            result_period,
            result_integral
        ]

    @staticmethod
    def _parse_month(raw, args):
        arch_month = struct.unpack(f'<{STRUCT_ARCH * args[3]}', raw)
        data_pack = COMMON_DATA_STRUCT[INTEGRAL_MONTH]
        len_pack = len(data_pack)
        responses_list = []

        for i in range(0, len(arch_month), len_pack):
            responses_list.append({key: value for key, value in zip(data_pack, arch_month[i: i + len_pack])})

        return responses_list

    @staticmethod
    def _parse_day(raw, args):
        arch_day = struct.unpack(f'<{STRUCT_ARCH * args[3]}', raw)
        data_pack = COMMON_DATA_STRUCT[INTEGRAL_DAY]
        len_pack = len(data_pack)
        responses_list = []

        for i in range(0, len(arch_day), len_pack):
            responses_list.append({key: value for key, value in zip(data_pack, arch_day[i: i + len_pack])})

        return responses_list

    @staticmethod
    def _parse_hour(raw, args):
        arch_hour = struct.unpack(f'<{STRUCT_ARCH * args[3]}', raw)
        data_pack = COMMON_DATA_STRUCT[INTEGRAL_HOUR]
        len_pack = len(data_pack)
        responses_list = []

        for i in range(0, len(arch_hour), len_pack):
            responses_list.append({key: value for key, value in zip(data_pack, arch_hour[i: i + len_pack])})

        return responses_list

    @check_lock
    @connect
    @submit_response
    @check_response
    @wrap_response
    async def process_integral_current(self):
        """
        Запрос интегральных текущих показаний
        """
        int_current = await self.read_metrics(0, type_metrics='read_current')

        response = {
            'metric_type': INTEGRAL_CURRENT, 'event_time': now(),
            'metrics': {'1': {key: int_current[1].get(key) for key in self.int_current_keys}}
        }

        return [response]

    @check_lock
    @connect
    @submit_response
    @check_response
    @wrap_response
    async def process_period_current(self):
        """
        Запрос переодических текущих показаний
        """
        per_current = await self.read_metrics(0, type_metrics='read_current')

        response = {
            'metric_type': PERIOD_CURRENT,
            'event_time': now(),
            'metrics': {'1': {key: per_current[0].get(key) for key in self.per_current_keys}}
        }

        return [response]

    @check_lock
    @connect
    @submit_response
    @check_response
    @wrap_response
    async def process_integral_month(self, last_date):
        """
        Запрос интегральных показаний за месяц
        """

        narc = self.get_narc(last_date)
        num_page = self.eval_num_page(narc)

        total_reponse = []

        for i in range(num_page // 10):
            int_months = await self.read_metrics(3, narc & 255, narc >> 8, 10, type_metrics='read_arch_month')
            narc += 10

            for int_month in int_months:
                tmp_response = {'metric_type': INTEGRAL_MONTH, 'event_time': now(), 'metrics': {}}
                tmp_response['metrics']['1'] = {key: int_month.get(key) for key in self.int_archive_keys}

                if tmp_response['metrics']['1']['wN_arc'] != 0:
                    total_reponse.append(tmp_response)

        remainder = num_page % 10

        if remainder:
            int_months = await self.read_metrics(3, narc & 255, narc >> 8, remainder, type_metrics='read_arch_month')

            for int_month in int_months:
                tmp_response = {'metric_type': INTEGRAL_MONTH, 'event_time': now(), 'metrics': {}}
                tmp_response['metrics']['1'] = {key: int_month.get(key) for key in self.int_archive_keys}

                if tmp_response['metrics']['1']['wN_arc'] != 0:
                    total_reponse.append(tmp_response)

        return total_reponse

    @check_lock
    @connect
    @submit_response
    @check_response
    @wrap_response
    async def process_integral_day(self, last_date):
        """
        Запрос интегральных показаний за сутки
        """
        int_days = await self.read_metrics(3, 0, 1, 2, type_metrics='read_arch_day')
        response = {'metric_type': INTEGRAL_DAY, 'event_time': now(), 'metrics': {}}

        for i, int_day in enumerate(int_days):
            response['metrics'][str(i + 1)] = {key: int_day.get(key) for key in self.int_archive_keys}

        return [response]

    @check_lock
    @connect
    @submit_response
    @check_response
    @wrap_response
    async def process_integral_hour(self, last_date):
        """
        Запрос интегральных показаний за час
        """
        int_hours = await self.read_metrics(3, 0, 1, 3, type_metrics='read_arch_hour')
        response = {'metric_type': INTEGRAL_HOUR, 'event_time': now(), 'metrics': {}}

        for i, int_hour in enumerate(int_hours):
            response['metrics'][str(i + 1)] = {key: int_hour.get(key) for key in self.int_archive_keys}

        return [response]

def main():
    # Inital
    ip_address = '10.8.1.58'  # '10.8.1.26'
    device_addr = 1
    port = 4001
    boudrate = 19200

    device = Teplocon(ip_address, port, boudrate)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(device.connect_async())

    # Запрашиваем данные
    print('integral current:', loop.run_until_complete(device.get_integral_current(device_addr=device_addr)))
    print('period current:', loop.run_until_complete(device.get_period_current(device_addr=device_addr)))

    print('integral month:', loop.run_until_complete(device.get_integral_month(device_addr=device_addr, n_arc=2)))
    print('integral day:', loop.run_until_complete(device.get_integral_day(device_addr=device_addr, n_arc=1)))
    print('integral hour:', loop.run_until_complete(device.get_integral_hour(device_addr=device_addr, n_arc=3)))

    # Удобный вывод данных
    # arch = loop.run_until_complete(device.get_integral_month(device_addr=device_addr, n_arc=4))
    # for value in arch:
    #     print(value)
    # print('Integral month:', loop.run_until_complete(
    #     device.read_metrics(3, 0, 1, 2, type_metrics='read_arch_month', count_addr=device_addr)))

    # Читаем служебную информацию + дату, время
    # print('Settings:',
    #       loop.run_until_complete(device.read_metrics(0, type_metrics='read_settings', count_addr=device_addr)))
    # print('Status and time:',
    #       loop.run_until_complete(device.read_metrics(0, type_metrics='read_stat_time', count_addr=device_addr)))
    # print('Current data:',
    #       loop.run_until_complete(device.read_metrics(0, type_metrics='read_current', count_addr=device_addr)))
    # print('Additional data:',
    #       loop.run_until_complete(device.read_metrics(0, type_metrics='read_additional', count_addr=device_addr)))

    # Читаем архивы
    # print('Integral day:', loop.run_until_complete(
    #     device.read_metrics(3, 0, 1, 1, type_metrics='read_arch_day', count_addr=device_addr)))
    # print('Integral hour:', loop.run_until_complete(
    #     device.read_metrics(3, 0, 1, 3, type_metrics='read_arch_hour', count_addr=device_addr)))

    # Сканируем архивы
    # print('Intgral month scan:', loop.run_until_complete(
    #     device.read_metrics(3, 0, 1, 1, type_metrics='scan_arch_month', count_addr=device_addr)))
    # loop.run_until_complete(
    #     device.read_metrics(type_metrics='scan_arch_day', count_addr=device_addr, num=3, lo=0, hi=1, narc=2))
    # loop.run_until_complete(
    #     device.read_metrics(type_metrics='scan_arch_hour', count_addr=device_addr, num=3, lo=0, hi=1, narc=2))

    loop.run_until_complete(device.close_async())


if __name__ == '__main__':
    main()
