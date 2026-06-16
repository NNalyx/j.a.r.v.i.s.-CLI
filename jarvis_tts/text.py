"""TTS text normalization helpers."""
import re

from jarvis_core.constants import ENGLISH_TO_RUSSIAN, TRANSLIT_MAP


def translit_word(word):
    """Транслитерация английского слова на русский"""
    lower_word = word.lower()
    if lower_word in ENGLISH_TO_RUSSIAN:
        return ENGLISH_TO_RUSSIAN[lower_word]
    result = ""
    for char in lower_word:
        result += TRANSLIT_MAP.get(char, char)
    return result

def convert_time(text):
    """Конвертирует время формата ЧЧ:ММ в более читаемый формат"""
    # Словарь для склонения часов
    hour_forms = {
        0: ("ноль", "часов", "ноль"),
        1: ("один", "час", "первого"),
        2: ("два", "часа", "второго"),
        3: ("три", "часа", "третьего"),
        4: ("четыре", "часа", "четвёртого"),
        5: ("пять", "часов", "пятого"),
        6: ("шесть", "часов", "шестого"),
        7: ("семь", "часов", "седьмого"),
        8: ("восемь", "часов", "восьмого"),
        9: ("девять", "часов", "девятого"),
        10: ("десять", "часов", "десятого"),
        11: ("одиннадцать", "часов", "одиннадцатого"),
        12: ("двенадцать", "часов", "двенадцатого"),
        13: ("тринадцать", "часов", "тринадцатого"),
        14: ("четырнадцать", "часов", "четырнадцатого"),
        15: ("пятнадцать", "часов", "пятнадцатого"),
        16: ("шестнадцать", "часов", "шестнадцатого"),
        17: ("семнадцать", "часов", "семнадцатого"),
        18: ("восемнадцать", "часов", "восемнадцатого"),
        19: ("девятнадцать", "часов", "девятнадцатого"),
        20: ("двадцать", "часов", "двадцатого"),
        21: ("двадцать один", "час", "двадцать первого"),
        22: ("двадцать два", "часа", "двадцать второго"),
        23: ("двадцать три", "часа", "двадцать третьего"),
    }

    def time_replacer(match):
        hour = int(match.group(1))
        minute = int(match.group(2))

        # Для второй половины часа используем 12-часовой формат
        hour_12 = hour % 12 if hour % 12 != 0 else 12

        if minute == 0:
            # Точный час: 14:00 → "четырнадцать часов"
            h_word = hour_forms[hour][0]
            h_form = hour_forms[hour][1]
            return f"{h_word} {h_form}"
        elif minute < 30:
            # Первая половина часа: 14:15 → "четырнадцать часов пятнадцать минут"
            h_word = hour_forms[hour][0]
            h_form = hour_forms[hour][1]
            m_word = number_to_words(minute, gender="feminine")
            return f"{h_word} {h_form} {m_word} минут"
        elif minute == 30:
            # Половина: 14:30 → "половина третьего"
            next_hour_12 = (hour_12 % 12) + 1
            return f"половина {hour_forms[next_hour_12][2]}"
        else:
            # Вторая половина: 14:45 → "без пятнадцати три" / "пятнадцать минут третьего"
            mins_to_next = 60 - minute
            next_hour_12 = (hour_12 % 12) + 1
            if mins_to_next == 15:
                return f"без пятнадцати {hour_forms[next_hour_12][0]}"
            elif mins_to_next == 20:
                return f"без двадцати {hour_forms[next_hour_12][0]}"
            else:
                m_word = number_to_words(minute, gender="feminine")
                return f"{m_word} минут {hour_forms[next_hour_12][2]}"

    return re.sub(r'\b(\d{1,2}):(\d{2})\b', time_replacer, text)

def convert_date(text):
    """Конвертирует даты формата ДД.ММ.ГГГГ в более читаемый формат"""

    months = {
        1: "января", 2: "февраля", 3: "марта", 4: "апреля",
        5: "мая", 6: "июня", 7: "июля", 8: "августа",
        9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
    }

    def date_replacer(match):
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3))

        day_str = number_to_words(day, gender="masculine")
        month_str = months.get(month, str(month))
        year_str = number_to_words(year, gender="masculine")

        return f"{day_str} {month_str} {year_str} года"

    # Форматы: ДД.ММ.ГГГГ, ДД/ММ/ГГГГ
    text = re.sub(r'\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b', date_replacer, text)

    return text

def number_to_words(n, gender="masculine"):
    """
    Преобразует число в слова на русском языке.

    Args:
        n: Число (int или float)
        gender: Род для согласования ("masculine", "feminine", "neuter")

    Returns:
        Строка с числом прописью
    """
    if n < 0:
        return "минус " + number_to_words(-n, gender)

    # Обработка десятичных дробей
    if isinstance(n, float) or '.' in str(n):
        try:
            n = float(n)
            int_part = int(n)
            frac_part = int(str(n).split('.')[1])

            if int_part == 0:
                int_words = "ноль"
            else:
                int_words = number_to_words(int_part, gender)

            # Дробная часть читается как отдельные цифры
            frac_words = " ".join(number_to_words(int(d), "masculine") for d in str(frac_part))

            return f"{int_words} целых и {frac_words} десятых"
        except:
            return str(n)

    n = int(n)

    if n == 0:
        return "ноль"

    # Основные числа
    ones = {
        1: "один", 2: "два", 3: "три", 4: "четыре", 5: "пять",
        6: "шесть", 7: "семь", 8: "восемь", 9: "девять"
    }

    teens = {
        10: "десять", 11: "одиннадцать", 12: "двенадцать", 13: "тринадцать",
        14: "четырнадцать", 15: "пятнадцать", 16: "шестнадцать",
        17: "семнадцать", 18: "восемнадцать", 19: "девятнадцать"
    }

    tens = {
        20: "двадцать", 30: "тридцать", 40: "сорок", 50: "пятьдесят",
        60: "шестьдесят", 70: "семьдесят", 80: "восемьдесят", 90: "девяносто"
    }

    hundreds = {
        100: "сто", 200: "двести", 300: "триста", 400: "четыреста",
        500: "пятьсот", 600: "шестьсот", 700: "семьсот",
        800: "восемьсот", 900: "девятьсот"
    }

    # Тысячи, миллионы, миллиарды
    thousands = ["", "тысяча", "миллион", "миллиард", "триллион"]

    # Определяем род для текущего уровня
    def get_gender_for_level(level):
        if level == 1:  # Тысячи — женский род
            return "feminine"
        return gender  # Остальные — мужской род

    def convert_hundreds(num, level):
        if num == 0:
            return ""

        result = []
        curr_gender = get_gender_for_level(level)

        # Сотни
        h = (num // 100) * 100
        if h in hundreds:
            result.append(hundreds[h])

        # Десятки и единицы
        rest = num % 100

        if rest >= 10 and rest <= 19:
            result.append(teens[rest])
        else:
            # Десятки
            t = (rest // 10) * 10
            if t in tens:
                result.append(tens[t])

            # Единицы с учетом рода
            o = rest % 10
            if o != 0:
                if curr_gender == "feminine":  # Тысячи
                    if o == 1:
                        result.append("одна")
                    elif o == 2:
                        result.append("две")
                    else:
                        result.append(ones[o])
                elif curr_gender == "masculine":
                    result.append(ones[o])
                else:
                    result.append(ones[o])

        # Добавляем порядок (тысяча, миллион и т.д.)
        if level > 0:
            thousand_word = thousands[level]
            if num % 10 == 1 and num != 11:
                # 1, 21, 31, ... → "тысяча", "миллион"
                result.append(thousand_word)
            elif 2 <= num % 10 <= 4 and not (12 <= num % 100 <= 14):
                # 2, 3, 4, 22, 23, 24, ... → "тысячи", "миллиона"
                if level == 1:  # Тысячи
                    result.append("тысячи")
                elif level == 2:  # Миллионы
                    result.append("миллиона")
                elif level == 3:  # Миллиарды
                    result.append("миллиарда")
                else:
                    result.append(thousand_word + "а")
            else:
                # 5-9, 10-19, 20, 30, ... → "тысяч", "миллионов"
                if level == 1:  # Тысячи
                    result.append("тысяч")
                elif level == 2:  # Миллионы
                    result.append("миллионов")
                elif level == 3:  # Миллиарды
                    result.append("миллиардов")
                else:
                    result.append(thousand_word + "ов")

        return " ".join(result)

    # Разбиваем число на группы по 3 цифры
    groups = []
    temp_n = n
    while temp_n > 0:
        groups.append(temp_n % 1000)
        temp_n //= 1000

    # Конвертируем каждую группу
    result_parts = []
    for i, group in enumerate(groups):
        if group != 0:
            group_words = convert_hundreds(group, i)
            result_parts.insert(0, group_words)

    return " ".join(filter(None, result_parts))

def convert_numbers(text):
    """Конвертирует числа в слова для лучшей озвучки"""

    def number_replacer(match):
        num_str = match.group(0)

        # Проверяем наличие десятичной точки
        if '.' in num_str:
            try:
                num = float(num_str)
                return number_to_words(num)
            except Exception:
                return num_str
        else:
            try:
                num = int(num_str)
                return number_to_words(num)
            except Exception:
                return num_str

    # Заменяем целые числа и десятичные дроби
    # Паттерн включает: целые числа, десятичные дроби
    text = re.sub(r'\b\d+\.?\d*\b', number_replacer, text)

    return text

def convert_percent(text):
    """Конвертирует проценты в более читаемый формат"""

    def percent_replacer(match):
        num_str = match.group(1)

        # Конвертируем число в слова
        if '.' in num_str:
            try:
                num = float(num_str)
                num_words = number_to_words(num)
            except Exception:
                num_words = num_str
        else:
            try:
                num = int(num_str)
                num_words = number_to_words(num)
            except Exception:
                num_words = num_str

        # Склонение слова "процент"
        if '.' in num_str:
            # Для дробных чисел используем множественное число
            return f"{num_words} процента"

        num_for_declension = int(float(num_str))
        last_digit = num_for_declension % 10
        last_two_digits = num_for_declension % 100

        if last_digit == 1 and last_two_digits != 11:
            return f"{num_words} процент"
        elif 2 <= last_digit <= 4 and not (12 <= last_two_digits <= 14):
            return f"{num_words} процента"
        else:
            return f"{num_words} процентов"

    # Заменяем проценты: 5%, 12.5%, и т.д.
    text = re.sub(r'(\d+\.?\d*)\s*%', percent_replacer, text)

    return text

def convert_english(text):
    """Транслитерирует английские слова"""
    return re.sub(r'[a-zA-Z]+', lambda m: translit_word(m.group()), text)

def add_accents_and_pauses(text):
    """
    Добавляет паузы в текст для улучшения озвучки (Supertonic)
    """
    # Удаляем восклицательные знаки (заменяем на точки для паузы)
    text = re.sub(r'!', '.', text)

    # Заменяем точки, вопросительные знаки на паузы
    text = re.sub(r'\.', '. ', text)
    text = re.sub(r'\?', '? ', text)

    # Заменяем многоточие на более длинную паузу
    text = re.sub(r'\.{3,}', '... ', text)

    # Заменяем запятые
    text = re.sub(r',', ', ', text)

    # Заменяем точки с запятой
    text = re.sub(r';', '; ', text)

    # Заменяем двоеточие
    text = re.sub(r':', ': ', text)

    # Заменяем тире
    text = re.sub(r'—|–|-', ' — ', text)

    # Заменяем скобки
    text = re.sub(r'\(', ' ( ', text)
    text = re.sub(r'\)', ' ) ', text)

    # Обработка специальных символов
    text = re.sub(r'\n', ' ', text)

    # Удаляем лишние пробелы
    text = re.sub(r'\s+', ' ', text).strip()

    return text

def preprocess_text(text):
    """Полная предобработка текста для Supertonic."""
    text = convert_time(text)
    text = convert_date(text)
    text = convert_percent(text)
    text = convert_numbers(text)
    text = convert_english(text)
    text = add_accents_and_pauses(text)
    return text

def _detect_tts_language(text: str) -> str:
    """Подобрать язык для Supertonic на основе текста."""
    if not text:
        return "na"

    cyrillic_count = len(re.findall(r"[А-Яа-яЁё]", text))
    latin_count = len(re.findall(r"[A-Za-z]", text))

    if cyrillic_count and cyrillic_count >= latin_count:
        return "ru"
    if latin_count and not cyrillic_count:
        return "en"
    return "na"

