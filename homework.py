import logging
import os
import sys
import time

import requests
import telegram.error
from dotenv import load_dotenv
from telegram import Bot

from my_exceptions import NoHomeworkToReview

load_dotenv()
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TOKENS = (TELEGRAM_CHAT_ID, TELEGRAM_TOKEN, PRACTICUM_TOKEN)

UNIX_TIME_NOW = int(time.time())
RETRY_TIME = 1500
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

# Логирование
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


def check_tokens():
    """Проверяет доступность наших токенов."""
    tokens = (TELEGRAM_CHAT_ID, TELEGRAM_TOKEN, PRACTICUM_TOKEN)
    return all(tokens)


def get_api_answer(current_timestamp):
    """Отправляет запрос к эндпоинту."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    homework_response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if homework_response.status_code != 200:
        logger.error('Эндпоинт недоступен')
        raise homework_response.raise_for_status()
    return homework_response.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not response:
        raise KeyError('Ответ содержит пустой словарь')
    if not isinstance(response, dict):
        raise TypeError('Функция получила в качестве параметра не словарь')
    if 'homeworks' not in response:
        raise KeyError('Ключ "homeworks" отсутствует')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Ответ должен быть списком')
    return response['homeworks']


def parse_status(homework):
    """Извлекает статус последней домашней работы."""
    if not homework.get('homework_name'):
        raise KeyError('Нет имени домашней работы')
    homework_name = homework.get('homework_name')
    if not homework.get('status'):
        raise KeyError('Нет статуса домашней работы')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_STATUSES.keys():
        raise KeyError('Недокументированный статус домашней работы')
    verdict = HOMEWORK_STATUSES.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telegram.error.InvalidToken as error:
        return f'Cообщение не отправилось, ошибка: {error}'


def main():
    """Отвечает за выполнение всех функций бота."""
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    last_message = ''
    last_error_message = ''
    if not check_tokens():
        logger.critical('Ошибка с обязательными переменными,'
                        'проверьте файл .env, что-то пошло не так')
        exit()
    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date')
            review_homework_list = check_response(response)
            last_homework = review_homework_list[0]
            bot_message = parse_status(last_homework)
            if bot_message != last_message:
                send_message(bot, bot_message)
                logger.info('Сообщение успешно отправлено')
                last_message = bot_message
            if len(review_homework_list) == 0:
                logger.debug('Нет д/з на проверку')
                raise NoHomeworkToReview('Нет д/з на проверку')
        except Exception as error:
            logger.error(f'Бот столкнулся с ошибкой: {error}')
            error_message = f'Бот столкнулся с ошибкой: {error}'
            if error_message != last_error_message:
                send_message(bot, error_message)
                last_error_message = error_message
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    # logging.basicConfig(
    #     level=logging.DEBUG,
    #     format='%(asctime)s [%(levelname)s] %(message)s',
    #     stream=sys.stdout)
    # handler = StreamHandler(stream=sys.stdout)
    main()
