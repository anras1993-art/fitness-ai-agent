"""Обращение к Google Gemini API.

Весь код, который работает с моделью, живёт только здесь.
Чтобы перейти на другую модель, достаточно поменять этот файл.
"""

import time

import httpx
from google import genai
from google.genai import errors, types

# Модель. Бесплатный тариф Google AI Studio: ввод и вывод бесплатны.
#
# gemini-3.5-flash-lite — быстрая и стабильно доступная, проверена 05.10.2026.
# gemini-3.8-flash      — умнее, тоже бесплатна, но на бесплатном тарифе часто
#                         отвечает ошибкой 503 «модель перегружена».
# Чтобы сменить модель, достаточно поменять эту строку.
# Список моделей и лимитов: https://ai.google.dev/gemini-api/docs/pricing
MODEL = "gemini-3.5-flash-lite"

# Сколько раз повторить запрос, если модель перегружена, и пауза между попытками
POPYTOK = 3
PAUZA_SEKUND = 5


class OshibkaAPI(Exception):
    """Ошибка при обращении к модели, уже переведённая на понятный язык.

    Приложение ловит её и показывает пользователю две части: что случилось
    (текст самой ошибки) и что с этим делать (sovet).
    """

    def __init__(self, chto_sluchilos, sovet=""):
        super().__init__(chto_sluchilos)
        self.sovet = sovet


def sprosit_model(api_kluch, sistemnyy_prompt, vopros, max_tokenov, shema_otveta=None):
    """Задаёт модели один вопрос и возвращает ответ текстом.

    api_kluch        — ключ, который пользователь ввёл в боковой панели
    sistemnyy_prompt — инструкция модели (берём из файлов в agent/prompts/)
    vopros           — данные анкеты
    max_tokenov      — ограничение на длину ответа
    shema_otveta     — если задана, модель обязана вернуть JSON по этой схеме
    """
    klient = genai.Client(api_key=api_kluch)

    nastroyki = {
        "system_instruction": sistemnyy_prompt,
        "max_output_tokens": max_tokenov,
    }

    # Нужен не свободный текст, а строгий JSON
    if shema_otveta is not None:
        nastroyki["response_mime_type"] = "application/json"
        nastroyki["response_json_schema"] = shema_otveta

    # Бесплатная модель часто бывает перегружена и отвечает ошибкой 5xx.
    # В таком случае ждём несколько секунд и пробуем снова.
    for nomer_popytki in range(1, POPYTOK + 1):
        try:
            otvet = klient.models.generate_content(
                model=MODEL,
                contents=vopros,
                config=types.GenerateContentConfig(**nastroyki),
            )
            break  # ответ получен, повторять не нужно
        except errors.ClientError as oshibka:
            # Ошибки 4xx — что-то не так с ключом или запросом, повтор не поможет
            if oshibka.code == 429:
                raise OshibkaAPI(
                    "Бесплатных запросов на сегодня больше нет",
                    "У бесплатного тарифа Google есть предел запросов в минуту и в сутки. "
                    "Подожди минуту и нажми «Составить план» снова. "
                    "Чтобы посмотреть, как выглядит готовый план, убери ключ — "
                    "приложение покажет сохранённый пример.",
                )

            tekst_oshibki = (oshibka.message or "").lower()
            if oshibka.code in (401, 403) or "api key" in tekst_oshibki or "api_key" in tekst_oshibki:
                raise OshibkaAPI(
                    "Ключ не подошёл",
                    "Проверь, что скопировал ключ целиком, без пробелов по краям, "
                    "и что он ещё действует. Новый ключ берётся бесплатно "
                    "на aistudio.google.com/apikey.",
                )

            raise OshibkaAPI(
                "Google отклонил запрос",
                f"Ответ сервера — {oshibka.code}: {oshibka.message}. "
                "Чаще всего помогает упростить формулировки в полях «Травмы» "
                "и «Предпочтения в еде» и попробовать снова.",
            )
        except errors.ServerError as oshibka:
            # Ошибки 5xx — обычно временная перегрузка модели
            if nomer_popytki == POPYTOK:
                raise OshibkaAPI(
                    "Модель сейчас перегружена",
                    f"Не ответила за {POPYTOK} попытки ({oshibka.code}: {oshibka.message}). "
                    "Это обычное дело на бесплатном тарифе в часы пик. "
                    "Попробуй через пару минут.",
                )
            time.sleep(PAUZA_SEKUND)
        except httpx.HTTPError:
            raise OshibkaAPI(
                "Нет связи с Google",
                "Запрос не дошёл до сервера. Проверь интернет, "
                "выключи VPN, если он включён, и попробуй снова.",
            )

    # Пустой ответ бывает, если модель отказалась отвечать
    # или если лимит на длину закончился ещё на размышлениях
    if not otvet.text:
        raise OshibkaAPI(
            "Модель вернула пустой ответ",
            "Так бывает, когда она не поняла запрос. Нажми «Составить план» ещё раз "
            "или упрости формулировки в полях «Травмы» и «Предпочтения в еде».",
        )

    # Ответ мог не поместиться в лимит длины и оборваться на полуслове.
    # Текст отдаём, но честно предупреждаем об этом.
    if otvet.candidates and otvet.candidates[0].finish_reason == types.FinishReason.MAX_TOKENS:
        return otvet.text + (
            "\n\n---\n\n*Ответ оборвался: не хватило лимита длины. "
            "Попробуй составить план заново.*"
        )

    return otvet.text
