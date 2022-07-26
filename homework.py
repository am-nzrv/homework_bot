import logging
import os
import sys
import time

import requests
from dotenv import load_dotenv
from telegram import Bot

load_dotenv()
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')


UNIX_TIME_NOW = int(time.time())
RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность наших токенов"""
    if not (TELEGRAM_TOKEN and TELEGRAM_CHAT_ID and PRACTICUM_TOKEN):
        return False
    return True


def get_api_answer(current_timestamp):
    """Отправляет запрос к эндпоинту."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    homework_response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if homework_response.status_code != 200:
        raise homework_response.raise_for_status()
    return homework_response.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not response:
        logging.error('Ответ содержит пустой словарь')
        raise KeyError('Ответ содержит пустой словарь')
    if not isinstance(response, dict):
        logging.error('Функция получила в качестве параметра не словарь')
        raise TypeError('Функция получила в качестве параметра не словарь')
    if 'homeworks' not in response:
        logging.error('Ключ "homeworks" отсутствует')
        raise KeyError('Ключ "homeworks" отсутствует')
    if not isinstance(response.get('homeworks'), list):
        logging.error('Ответ должен быть списком')
        raise TypeError('Ответ должен быть списком')
    return response['homeworks']


def parse_status(homework):
    """Извлекает статус последней домашней работы."""
    if not homework.get('homework_name'):
        logging.warning('Отсутствует имя домашней работы.')
        raise KeyError('Нет имени домашней работы')
    homework_name = homework.get('homework_name')

    if not homework.get('status'):
        logging.error('Нет статуса домашней работы')
        raise KeyError('Нет статуса домашней работы')
    homework_status = homework.get('status')

    if homework_status not in HOMEWORK_STATUSES.keys():
        logging.error('Недокументированный статус домашней работы')
        raise KeyError('Недокументированный статус домашней работы')
    verdict = HOMEWORK_STATUSES.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        logging.info('Сообщение отправлено')
        return bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as e:
        logging.info(f'Cообщение не отправилось, ошибка: {e}')


def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    last_message = ''
    if not check_tokens():
        logging.critical('Ошибка с обязательными переменными,'
                         'проверьте файл .env, что-то пошло не так')
        exit()
    while True:
        try:
            response = get_api_answer(current_timestamp)
            review_homework_list = check_response(response)
            if len(review_homework_list) == 0:
                logging.debug('Пустой список -> Нет д/з на проверку')
                break
            for last_reviewed_homework in review_homework_list:
                bot_message = parse_status(last_reviewed_homework)
                if bot_message != last_message:
                    send_message(bot, bot_message)
                    last_message = bot_message
            current_timestamp = response.get('current_date')
            time.sleep(RETRY_TIME)
        except Exception as e:
            logging.exception(f'Бот столкнулся с ошибкой: {e}')
            send_message(bot, f'Бот столкнулся с ошибкой: {e}')
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(message)s',
        stream=sys.stdout
    )
    main()
