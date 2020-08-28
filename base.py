import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from enum import Enum
from types import DynamicClassAttribute

import aioredis
from inquirer_utils.headers import CACHE_TTL, DEFAULT_SUBSYSTEMS
from is74_utils import now
from motor.motor_asyncio import AsyncIOMotorClient

from inquirer_plugins.utils import DeviceException
from inquirer_plugins.utils import check_lock, connect

DEFAULT_RETRIES = 5
DEFAULT_TIMEOUT = 10
DEFAULT_SLEEP_TIME = 1
DEFAULT_BYTE_ORDER = 'big'

DEVICE_SUBMITTER = os.environ.get('DEVICE_SUBMITTER', 'DeviceSubmitter')

MONGO_DB = 'partner'
MONGO_LOGIN = os.environ.get('MONGO_LOGIN')
MONGO_PASSWORD = os.environ.get('MONGO_PASSWORD')
MONGO_HOST = os.environ.get('MONGO_HOST', 'mongo-iot-mongodb.iot.svc.k8s')
MONGO_URL = f'mongodb://{MONGO_LOGIN}:{MONGO_PASSWORD}@{MONGO_HOST}:27017/{MONGO_DB}'

DEVICE_NET_TYPE = 0
DEVICE_LORA_TYPE = 1
DEVICE_RADIO_TYPE = 2
DEVICE_LERS_TYPE = 3
DEVICE_IMPULSE_TYPE = 4
DEVICE_RESISTANCE_TYPE = 5

log_level = os.environ.get('LOG_LEVEL', logging.INFO)
stream_handler = logging.StreamHandler(sys.stdout)

try:
    log_level = int(log_level)
except (TypeError, ValueError):
    log_level = log_level


class DeviceEnum(Enum):

    def __new__(cls, *args):
        args_len = len(args)

        if args_len == 1:
            if isinstance(args[0], int):
                value = args[0]
                ext = None
            else:
                value = len(cls.__members__)
                ext = args[0]
        elif args_len == 2:
            value = args[0]
            ext = args[1]
        else:
            raise AttributeError('Неверное количество параметров, может быть один или два параметра')

        obj = object.__new__(cls)

        obj._value_ = value
        obj._ext_ = ext

        return obj

    @classmethod
    def _missing_(cls, value):
        try:
            return cls._member_map_[value]
        except KeyError as e:
            raise ValueError(f'{value} is not a valid {cls.__name__}') from e

    @DynamicClassAttribute
    def ext(self):
        return self._ext_

    @DynamicClassAttribute
    def low_name(self):
        return self.name.lower()


class BaseProtocol:

    def __init__(self, dev_id=None):
        self.dev_id = dev_id


class Base:
    CALLBACKS = [
        'check_device',
    ]

    def __init__(self, dev_id, func=None, proc=None, **kwargs):
        self._kwargs = kwargs

        self.dev_id = str(dev_id)
        self.lock_key = self.dev_id

        self.func = func
        self.proc = proc

        self.loop = asyncio.get_event_loop()

    async def __aenter__(self):
        self.cache = await aioredis.create_redis('redis://partner-redis/0')

        await self._async_init(**self._kwargs)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.func = None
        self.proc = None

        self.cache.close()
        await self.cache.wait_closed()

    async def _async_init(self, **kwargs):
        ...

    @staticmethod
    def __get_callbacks(cls):
        callbacks = []

        for base in [base for base in cls.__bases__]:
            try:
                callbacks += cls.__get_callbacks(base)
            except AttributeError:
                pass

        return callbacks + getattr(cls, 'CALLBACKS', [])

    @property
    def callbacks(self):
        return self.__get_callbacks(self.__class__)

    async def lock_connect(self):
        info = json.dumps({
            'id': id(self),
            'dev_id': self.dev_id,
        })

        return await self.cache.set(f'locks:{self.lock_key}', info, expire=CACHE_TTL, exist=self.cache.SET_IF_NOT_EXIST)

    async def unlock_connect(self):
        await self.cache.delete(f'locks:{self.lock_key}')

    async def get_lock_info(self):
        info = await self.cache.get(f'locks:{self.lock_key}')

        return json.loads(info) if info else None

    async def check_device(self):
        raise DeviceException('Для этой модели проверка не реализована')

    @staticmethod
    async def get_devices_query():
        raise NotImplementedError()

    @staticmethod
    async def parse_devices(raw_devices):
        raise NotImplementedError()


class BaseDevice(Base):
    CALLBACKS = [
        'get_current',

        'process_metrics',
        'reload_metrics',

        'process_period_current',
        'process_period_hour',
        'process_period_day',
        'process_period_month',
        'process_integral_current',
        'process_integral_hour',
        'process_integral_day',
        'process_integral_month',
    ]

    CALC_METRICS = []

    __mdb_connection = AsyncIOMotorClient(MONGO_URL)
    __mdb = __mdb_connection[MONGO_DB]

    def __init__(self, dev_id, **kwargs):
        super().__init__(dev_id, **kwargs)

        self._scheme = {}
        self.is_opened = False

    @staticmethod
    async def _get_scheme():
        return {
            'subsystems': DEFAULT_SUBSYSTEMS
        }

    async def get_scheme(self):
        if not self._scheme:
            self._scheme = await self._get_scheme()

        return self._scheme

    @property
    async def mdb_config(self):
        return await self.__mdb['configs'].find_one({'dev_id': self.dev_id}) or {}

    async def set_mdb_config(self, config: dict):
        if 'dev_id' in config:
            del config['dev_id']

        await self.__mdb['configs'].update_one(
            {'dev_id': self.dev_id},
            {
                '$set': config,
                '$setOnInsert': {'dev_id': self.dev_id}
            },
            upsert=True
        )

    @staticmethod
    async def open():
        return True

    @staticmethod
    async def close():
        ...

    async def get_current(self):
        raise DeviceException('Для этой модели получение мгновенных метрик не реализовано')

    @staticmethod
    async def get_config():
        return {
            'data_availability': []
        }

    @check_lock
    @connect
    async def process_metrics(self, last_dates: [dict, datetime] = None):
        config = await self.get_config()

        for metric_type, use_last_date in config['data_availability']:
            params = {}

            if use_last_date:
                if isinstance(last_dates, datetime):
                    last_date = last_dates
                elif isinstance(last_dates, dict):
                    last_date = last_dates.get(metric_type)
                else:
                    last_date = None

                params = {
                    'last_date': last_date
                }

            func_name = f'process_{metric_type}'

            try:
                await getattr(self, func_name)(**params)
            except AttributeError:
                raise DeviceException(f'{now()}: {self.dev_id}: функция {func_name} не найдена')

    @check_lock
    async def reload_metrics(self, clear_metrics=0, clear_conf=0):
        if clear_metrics:
            await self.func(DEVICE_SUBMITTER, 'clear', dev_id=self.dev_id, need_clear_conf=clear_conf)

        await self.process_metrics(last_dates=None)

    @staticmethod
    async def get_devices_query():
        raise NotImplementedError()

    @staticmethod
    async def parse_devices(raw_devices):
        raise NotImplementedError()


class BaseRadio(Base):
    CALLBACKS = [
        'parse_event',
    ]

    async def parse_event(self, event):
        pass

    @staticmethod
    async def get_devices_query():
        raise NotImplementedError()

    @staticmethod
    async def parse_devices(raw_devices):
        raise NotImplementedError()
