import asyncio
import json
import os
import pickle

import aioredis
from async_timeout import timeout
from inquirer_utils import get_report_date, relativedelta, delta
from inquirer_utils.headers import LOCK_TTL, ROUND_CNT, PERIOD, HOUR, DAY, MONTH, CURRENT
from is74_utils import DateTimeEncoder, now, logger

DEVICE_SUBMITTER = os.environ.get('DEVICE_SUBMITTER', 'DeviceSubmitter')
DONT_SUBMIT = bool(os.environ.get('DONT_SUBMIT', False))
MAX_SUBMIT_COUNT = 250

MODEL_NAMES = {
    'карат 306': 'karat_30x',
    'карат 307': 'karat_30x',
    'карат-306': 'karat_30x',
    'карат-307': 'karat_30x',
    'карат-компакт 2-213': 'karat_213',
    'вкт-7': 'vkt_7',
    'эльф-01': 'elf_0x',
    'эльф-02': 'elf_0x',
    'эльф-03': 'elf_0x',
    'эльф-03п': 'elf_0x',
    'эльф-04': 'elf_0x',
    'эльф-04п': 'elf_0x',
    'меркурий 230': 'mercury_2xx',
    'меркурий 234': 'mercury_2xx',
    'спт943': 'spt_943',
    'логика спт 943_1': 'spt_943',
    'тв-7': 'tv_7',

    'си-11': 'si_11_12',
    'си-12': 'si_11_12',
    'си-22': 'si_11_12',
    '928lw': 'karat_928lw',
    'domino is_industry v_1_0': 'domino_is_industry',
    'domino is_industry v_2_0': 'domino_is_industry',
    'domino ws pwr v_2_1': 'domino_ws_pwr',
    'domino pulse v_4_1': 'domino_pulse',
    'domino pulse v_4_2': 'domino_pulse',
}


def check_lock(func):
    async def wrapper(self, *args, **kwargs):
        async with timeout(LOCK_TTL):
            need_unlock = True

            while True:
                if not await self.lock_connect():
                    info = await self.get_lock_info()

                    if info['id'] != id(self):
                        await asyncio.sleep(1)
                        continue

                    need_unlock = False

                try:
                    response = await func(self, *args, **kwargs)
                finally:
                    if need_unlock:
                        await self.unlock_connect()

                return response

    return wrapper


def connect(func):
    async def wrapper(self, *args, **kwargs):
        need_close = True

        if self.is_opened:
            need_close = False
        else:
            if not await self.open():
                raise DeviceException(f'{self.dev_id}: Ошибка при подключении к устройству')

        try:
            response = await func(self, *args, **kwargs)
        finally:
            if need_close:
                await self.close()

        return response

    return wrapper


def wrap_response(func):
    async def wrapper(self, *args, **kwargs):
        response = {}

        data = await func(self, *args, **kwargs)

        if not data:
            return {}

        scheme = await self.get_scheme()

        for metric_item in data:
            await asyncio.sleep(0)

            metric_type = metric_item['metric_type']
            event_time = metric_item['event_time']

            for ss_num, metrics in metric_item['metrics'].items():
                for metric in 'TVMPQG':
                    m1 = f'{metric}1'
                    m2 = f'{metric}2'
                    md = f'{metric}d'

                    if all(x in metrics for x in (m1, m2)) and md not in metrics:
                        metrics[md] = round(metrics[m1] - metrics[m2], ROUND_CNT)

                if PERIOD in metric_type:
                    if 'tраб' not in metrics or 'tост' in metrics:
                        continue

                    t_ost = None
                    t_rab = metrics['tраб']

                    if HOUR in metric_type:
                        t_ost = 1.0 - t_rab
                    elif DAY in metric_type:
                        t_ost = 24.0 - t_rab
                    elif MONTH in metric_type:
                        from_date = get_report_date(event_time - relativedelta(months=1), scheme['report_day'])
                        delta_hours = (event_time - from_date).days * 24
                        t_ost = delta_hours - t_rab

                    if t_ost is not None:
                        metrics['tост'] = round(t_ost, ROUND_CNT)

        if data:
            for field in ('current_time', 'serial', 'subsystems'):
                if field in scheme:
                    response[field] = scheme[field]

            response['data'] = data

        return response

    return wrapper


def check_response(func):
    async def wrapper(self, *args, **kwargs):
        response = await func(self, *args, **kwargs)

        if response and 'serial' in response and hasattr(self, 'serial'):
            if self.serial and str(self.serial).strip() != str(response['serial']).strip():
                raise DeviceException(f'Не совпадают серийные номера на устройстве {response["serial"]} '
                                      f'и в БД {self.serial}')

        return response

    return wrapper


def submit_response(func):
    async def wrapper(self, *args, **kwargs):
        response = await func(self, *args, **kwargs)
        last_date = kwargs.get('last_date')

        if response and last_date:
            for item in response['data']:
                if item['event_time'] > last_date:
                    break

                response['data'].remove(item)

        if not response or not response['data']:
            return

        template = {key: value for key, value in response.items() if key != 'data'}
        data = response['data']

        for idx in range(0, len(data), MAX_SUBMIT_COUNT):
            template['data'] = data[idx: idx + MAX_SUBMIT_COUNT]

            # Для отладки
            if DONT_SUBMIT:
                print('Response:', json.dumps(template, cls=DateTimeEncoder))
            else:
                await self.func(DEVICE_SUBMITTER, 'submit', dev_id=self.dev_id, data=template)

    return wrapper


def repeat_with_exception(repeat_count=1, log_exception=True):
    def decorator(func):
        async def wrapper(self, *args, **kwargs):
            for _ in range(repeat_count):
                try:
                    return await func(self, *args, **kwargs)
                except Exception as e:
                    if log_exception:
                        logger.error(f'{self.dev_id}: {e}')

        return wrapper

    return decorator


def get_model_name(meter_model):
    return MODEL_NAMES.get(meter_model.lower().replace('.', '_'))


def check_next_date(func):
    async def wrapper(self, metric_type, last_date):
        if last_date and CURRENT not in metric_type:
            next_date = last_date + delta(metric_type)

            if MONTH in metric_type:
                scheme = await self.get_scheme()
                report_day = scheme.get('report_day', 31)
                next_date = get_report_date(next_date, report_day)

            if next_date > now():
                return

        return await func(self, metric_type, last_date)

    return wrapper


class WaitResponse:

    def __init__(self, key, expire=90):
        self.__redis = None

        self.key = key
        self._expire = expire

    async def __aenter__(self):
        self.__redis = await aioredis.create_redis('redis://partner-redis/1')

        while not await self.__redis.set(
                self.key, pickle.dumps(None), expire=self._expire, exist=self.__redis.SET_IF_NOT_EXIST):
            await asyncio.sleep(1)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.__redis.delete(self.key)

        self.__redis.close()
        await self.__redis.wait_closed()

    @classmethod
    async def set_response(cls, key, value):
        redis = await aioredis.create_redis('redis://partner-redis/1')

        await redis.set(key, pickle.dumps({'response': value}), exist=redis.SET_IF_EXIST)

        redis.close()
        await redis.wait_closed()

    async def get_response(self, _timeout=60):
        async with timeout(_timeout):
            while True:
                await asyncio.sleep(1)

                resp = await self.__redis.get(self.key)

                if not resp:
                    continue

                resp = pickle.loads(resp)

                if resp:
                    return resp.get('response')


class NotAllParamsSetException(Exception):
    pass


class DeviceException(Exception):
    pass


class PluginException(Exception):
    pass
