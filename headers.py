from inquirer_utils.headers import *

SETTINGS = 'settings'
CURRENT = 'current'
STAT_TIME = 'stat and time'
ADDITIONAL = 'additional'

PERIOD_ADDITIONAL = f'{PERIOD}_{ADDITIONAL}'
INTEGRAL_ADDITIONAL = f'{INTEGRAL}_{ADDITIONAL}'

# Коды команд
CMD_READ_SETTINGS = 0x01    # Чтение настроек
CMD_READ_STAT_TIME = 0x02   # Чтение статуса и времени работы
CMD_READ_CUR_PARAMS = 0x10  # Чтение текущих параметров
CMD_READ_ADD_PARAMS = 0x20  # Чтение дополнительных параметров
CMD_READ_HOUR_ARCH = 0x30   # Чтение почасового архива
CMD_SCAN_HOUR_ARCH = 0x31   # Сканирование почасового архива
CMD_READ_DAY_ARCH = 0x40    # Чтение посуточного архива
CMD_SCAN_DAY_ARCH = 0x41    # Сканирование посуточного архива
CMD_READ_MONTH_ARCH = 0x50  # Чтение помесячного архива
CMD_SCAN_MONTH_ARCH = 0x51  # Сканирование помесячного архива

# Общие метрики
CUR_YEAR = 'year'    # Текущий год
CUR_MONTH = 'month'  # Текущий месяц
CUR_DAY = 'day'      # Текущий день
CUR_HOUR = 'hour'    # Текущий час
CUR_MIN = 'min'      # Текущая минута
BLOCK_MON = 'Blocking month'        # Месяц блокирования ТВ зв неуплату
BLOCK_YEAR = 'Blocking year'        # Год блокирования ТВ за нуплату
COM_WORK = 'tраб'   # Общее время работы, мин (до 10000000)
STAT_8 = 'Diagnostic code 8'        # Код диагностики 8
STAT_16 = 'Diagnostic code 16'      # Код диагностики 16

# Настройки прибора
VERS = 'version'     # Версия программы ТВ (X.XX)
SERNUM = 'serial'    # Заводской номер (000001 - 999999)
C_DEL = 'C delta'    # Цена импульса ПР
DCONT = 'Reporting day'    # Отчетный день для печати
CONF = 'Config'            # Байт конфигурации
C_LVL = 'C level P'        # Предел датчика давления в пр. и обр
CONF_YEAR = 'Config year'    # Год последней настройки конфигурации
CONF_MONTH = 'Config month'  # Месяц последней настройки конфигурации
CONF_DAY = 'Config day'      # День последней настройки конфигурации
CONF_HOUR = 'Config hour'    # Час последней настройки конфигурации
CONF_MIN = 'Config min'      # Минута последней настройки конфигурации

# Текущие параметры
REC_Q = 'Qd'      # Полученное тепло *100, ГДж (до 4000000000)
REC_M1 = 'M1'    # Полученная масса *100, т (до 4000000000)
LEFT_M2 = 'M2'   # Ушедшая масса *100, т (до 4000000000)
DIR_G1 = 'G1'    # Массовый расход в прямом, (до 9999.9999 т/ч)
REV_G2 = 'G2'   # Массовый расход в обратном, (до 9999.9999 т/ч)
DIR_T1 = 'T1'    # Температура в прямом, (0.00 - 200.00 град )
REV_T2 = 'T2'   # Температура в обратном, (0.00 - 200.00 град )
DIR_P1 = 'P1'    # Давление в прямом, (0.000 - 2.500 MПа)
REV_P2 = 'P2'   # Давление в обратном, (0.000 - 2.500 MПа)
THER_Q = 'Od'    # Тепловая мощность, (до 999.99999 ГДж/ч)

# Дополнительные параметры
COM_T_WORK = 'tраб'    # Общее время работы, мин
ACP_BEG = 'Code ACP beg'    # Код АЦП начала диапазона, (ХХХХХ.Х)
ACP_WIDE = 'Code ACP wide'  # Код АЦП ширины диапазона, (ХХХХХ.Х)
W220_ON = 'Light 220B On'       # Код АЦП при 220в и включенной подсветке, (000-999)
W220_OFF = 'Light 220B Off'     # Код АЦП при 220в и выключенной подсветке,(000-999)
FR_DAWL = 'fR Dawl'             # Значение вх. сопр. каналов давления, (160 – 250 Ом)
NET_NUM = 'Net number'    # Номер в локальной сети (от 0 до 250)
NET_SPEED = 'Net speed'    # Скорость в сети (600;1200;2400;4800;9600;19200 бит/с)
MOD_INIT = 'Modem init'    # (0 или 1) - выдавать или нет АТ-строку при включении

# Архивы
STAT_L = 'Stat_l'   # Код диагностики low
STAT_H = 'Stat_h'   # Код диагностики high
NUM_MIN_W = 'tраб'    # Количество минут времени работы
ACCUM_M1 = 'M1'   # Накопленная масса G1*100
ACCUM_M2 = 'M2'   # Накопленная масса G2*100
ACCUM_Q = 'Qd'   # Накопленное тепло GQ*100
WN_ARC = 'wN_arc'   # целая часть и признак записи

# Структура метрик
COMMON_DATA_STRUCT = {

    SETTINGS: [
        VERS, SERNUM, C_DEL, DCONT,
        CONF, C_LVL, CUR_MIN, CUR_HOUR,
        CUR_DAY, CUR_MONTH, CUR_YEAR,
    ],

    STAT_TIME: [
        CUR_MIN, CUR_HOUR, CUR_DAY, CUR_MONTH,
        CUR_YEAR, BLOCK_MON, BLOCK_YEAR,
        COM_T_WORK, STAT_8, STAT_16,
    ],

    PERIOD_ADDITIONAL: [
        ACP_BEG, ACP_WIDE, W220_ON, W220_OFF,
        FR_DAWL, NET_NUM, NET_SPEED, MOD_INIT,
    ],

    INTEGRAL_ADDITIONAL: [
        COM_T_WORK, REC_Q,
        REC_M1, LEFT_M2,
    ],

    PERIOD_CURRENT: [
        DIR_G1, REV_G2, DIR_T1, REV_T2,
        DIR_P1, REV_P2, THER_Q,
    ],

    INTEGRAL_CURRENT: [
        COM_T_WORK, REC_Q, REC_M1,
        LEFT_M2, STAT_8, STAT_16,
    ],

    INTEGRAL_MONTH: [
        STAT_L, STAT_H, NUM_MIN_W, DIR_T1,
        REV_T2, DIR_P1, REV_P2, ACCUM_M1,
        ACCUM_M2, ACCUM_Q, WN_ARC,
    ],

    INTEGRAL_DAY: [
        STAT_L, STAT_H, NUM_MIN_W, DIR_T1,
        REV_T2, DIR_P1, REV_P2, ACCUM_M1,
        ACCUM_M2, ACCUM_Q, WN_ARC,
    ],

    INTEGRAL_HOUR: [
        STAT_L, STAT_H, NUM_MIN_W, DIR_T1,
        REV_T2, DIR_P1, REV_P2, ACCUM_M1,
        ACCUM_M2, ACCUM_Q, WN_ARC,
    ]
}

# Маски битов в байте состояния stat_l
MSK_220 = 0x01      # Сеть 220 В выключилась
MSK_T1 = 0x02       # t1 вне доступка
MSK_T2 = 0x04       # t2 вне доступка
MSK_P1 = 0x08       # P1 вне доступка
MSK_P2 = 0x10       # P2 вне доступка
MSK_T_REV = 0x20    # t1 < t2 обратный перепад температур
MSK_CLK = 0x40      # Было изменение конфигурации
MSK_ST16 = 0x80     # Байт stat_h отличен от 0

# Маски битов в байте состояния stat_h
MSK_TECH8 = 0x01    # Технологический 8 (резервный)
MSK_TECH9 = 0x02    # Технологический 9 (сбой КС ОЗУ таймера)
MSK_TECH10 = 0x04   # Технологический 10 (сбой Flash яч а5)
MSK_TECH11 = 0x08   # Технологический 11 (сбой по шине IIC)
MSK_TECH12 = 0x10   # Технологический 12 (сбой при чтении накопл. парам. при включении ТВ в сеть)
MSK_TECH13 = 0x20   # Технологический 13 (сбой при записи почасового архива)
MSK_TECH14 = 0x40   # Технологический 14 (сбой Flash калибр. ФЦП и 220, R)
MSK_TECH15 = 0x80   # Технологический 15 (наложение архивов)

# Словарь расшифровок масок (код диагностики)
MASKS_ERRORS = {
    MSK_220: 'Сеть 220 В выключилась',
    MSK_T1: 't1 вне достука',
    MSK_T2: 't2 вне достука',
    MSK_P1: 'P1 вне достука',
    MSK_P2: 't2 вне достука',
    MSK_T_REV: 't1 < t2 обратный перепад температур',
    MSK_CLK: 'Было изменение конфигурации',
    MSK_ST16: 'Байт stat_h отличен от 0',
    
    MSK_TECH8: 'Технологический 8 (резервный)',
    MSK_TECH9: 'Технологический 9 (сбой КС ОЗУ таймера)',
    MSK_TECH10: 'Технологический 10 (сбой Flash яч а5)',
    MSK_TECH11: 'Технологический 11 (сбой по шине IIC)',
    MSK_TECH12: 'Технологический 12 (сбой при чтении накопл. парам. при включении ТВ в сеть)',
    MSK_TECH13: 'Технологический 13 (сбой при записи почасового архива)',
    MSK_TECH14: 'Технологический 14 (сбой Flash калибр. ФЦП и 220, R)',
    MSK_TECH15: 'Технологический 15 (наложение архивов)',
}

# Константы
ARCH_LEN = 24           # Длина архивной записи 24
NUM_H_D = 42            # 1008/24 число дней часового архива
NUM_HOUR_MAX = 1008     # Число записей почасового архива
NUM_DAY_MAX = 300       # Число записей поуточного архива
NUM_MONT_MAX = 50       # Число записей помесячного архива
STRUCT_ARCH = '2b3H2b3L1H'  # Структура архивной записи
BUFFER_SIZE = 1024    

# Паузы разделяющие пакеты и таймауты
LONG_RESPONSE_TIMEOUT = 0.25
DEFAULT_TIMEOUT = 0.20

# Скорость канала
BOUDRATES = {
    600: 0x31,
    1200: 0x32,
    2400: 0x33,
    4800: 0x34,
    9600: 0x35,
    19200: 0x36
}
