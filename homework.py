import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from exceptions import YandexApiError, CheckResponseError

load_dotenv()
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)


def check_tokens():
    """Функция проверяет доступность переменных окружения."""
    env_var = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    return all(env_var)


def send_message(bot, message):
    """Функция отправляет сообщение в Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение отправлено')
    except Exception as error:
        logger.error('Ошибка при отправке сообщения')
        raise SystemError(f'Ошибка при отправке сообщения {error}')


def get_api_answer(timestamp):
    """Функция делает запрос к эндпоинту API-сервиса."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        status = response.status_code
        if status != HTTPStatus.OK:
            message = f'Недоступность эндпоинта. Код ответа API: {status}'
            logger.error(message)
            raise Exception(message)
        return response.json()
    except Exception as error:
        message = f'Ошибка обращения к API: {error}'
        logger.error(message, exc_info=True)
        raise YandexApiError(message)


def check_response(response):
    """Функция проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        logger.error('Ошибка типа данных dict')
        raise TypeError('Ошибка типа данных dict')
    if 'homeworks' not in response:
        logger.error('API не содержит ключа homeworks')
        raise KeyError('API не содержит ключа homeworks')
    homework = response.get('homeworks')
    if not isinstance(homework, list):
        logger.error('Ошибка типа данных list')
        raise TypeError('Ошибка типа данных list')
    if not homework:
        message = 'Список домашек пуст'
        logger.error(message)
        raise CheckResponseError(message)
    return homework


def parse_status(homework):
    """Функция извлекает статус домашки."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_name is not None and homework_status is not None:
        if homework_status in HOMEWORK_VERDICTS:
            verdict = HOMEWORK_VERDICTS.get(homework_status)
            return (f'Изменился статус проверки работы "{homework_name}".'
                    f' {verdict}'
                    )
        else:
            logger.error('Неизвестный статус')
            raise SystemError('Неизвестный статус')
    else:
        raise KeyError('Нет обязательных ключей в словаре')


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствует обязательная переменная окружения')
        raise Exception('Отсутствует обязательная переменная окружения')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homework_list = check_response(response)
            homework = homework_list[0]
            message = parse_status(homework)
            if last_message != message:
                send_message(bot, message)
                last_message = message

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if last_message != message:
                send_message(bot, message)
                last_message = message

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
