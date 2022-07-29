import logging
import os
import sys
import time

import requests
from dotenv import load_dotenv
from requests import HTTPError
from telegram import Bot
from telegram.error import TelegramError

load_dotenv()

TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
RETRY_TIME = 1500
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


def check_tokens():
    """Проверяет доступность наших токенов."""
    return all((TELEGRAM_CHAT_ID, TELEGRAM_TOKEN, PRACTICUM_TOKEN))


def get_api_answer(current_timestamp):
    """Отправляет запрос к эндпоинту."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_response = requests.get(ENDPOINT,
                                         headers=HEADERS,
                                         params=params)
        if homework_response.status_code != 200:
            raise HTTPError(f'Ошибка ответа от эндпоинта: '
                            f'{homework_response.status_code}')
    except TelegramError as error:
        raise TelegramError(f'Ошибка доступа к эндпоинту {error}')
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
    homework_name = homework['homework_name']
    if not homework.get('status'):
        raise KeyError('Нет статуса домашней работы')
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES.keys():
        raise KeyError('Недокументированный статус домашней работы')
    verdict = HOMEWORK_STATUSES.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except TelegramError as error:
        raise TelegramError(f'Cообщение не отправилось, '
                            f'ошибка: {error}')


def main():
    """Отвечает за выполнение всех функций бота."""
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    last_message = ''
    error_message = ''
    last_error_message = ''
    if not check_tokens():
        logger.critical('Ошибка с обязательными переменными,'
                        'проверьте файл .env, что-то пошло не так')
        sys.exit('Ошибка с обязательными переменными')
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
        except TelegramError as error:
            logger.error(f'{error}')
            last_error_message = f'{error}'
        except HTTPError as error:
            logger.error(f'{error}')
            last_error_message = f'{error}'
        except IndexError:
            logger.error('Нет д/з на проверку')
            last_error_message = 'Нет д/з на проверку'
        except Exception as error:
            logger.error(f'{error}')
            last_error_message = f'{error}'
        finally:
            if error_message != last_error_message:
                send_message(bot, last_error_message)
                error_message = last_error_message
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
