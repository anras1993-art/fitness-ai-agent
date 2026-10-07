"""Цепочка шагов: проверка безопасности, программа тренировок, план питания.

Шаг 1 решает, можно ли человеку тренироваться самостоятельно.
Если ответ «нельзя» — остальные шаги не запускаются.
"""

import json
from pathlib import Path

from agent.llm import OshibkaAPI, sprosit_model

# Папка с текстами промптов — рядом с этим файлом
PAPKA_PROMPTOV = Path(__file__).parent / "prompts"

# Сохранённые ответы модели для демо-режима и анкета, по которой их получили
PAPKA_PROEKTA = Path(__file__).parent.parent
PAPKA_DEMO = PAPKA_PROEKTA / "examples" / "demo_responses"
FAYL_PRIMERA_ANKETY = PAPKA_PROEKTA / "examples" / "sample_profile.json"

# Схема ответа для шага 1. Модель обязана вернуть ровно такой JSON,
# поэтому разбирать ответ можно без хитростей.
SHEMA_BEZOPASNOSTI = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["ok", "caution", "stop"]},
        "poyasnenie": {"type": "string"},
    },
    "required": ["status", "poyasnenie"],
}


def prochitat_prompt(imya_fayla):
    """Читает текст промпта из папки agent/prompts/."""
    return (PAPKA_PROMPTOV / imya_fayla).read_text(encoding="utf-8")


def anketa_v_tekst(anketa):
    """Превращает словарь с ответами в простой текст для модели."""
    return "\n".join(f"{nazvanie}: {znachenie}" for nazvanie, znachenie in anketa.items())


def proverit_bezopasnost(api_kluch, anketa):
    """Шаг 1. Возвращает словарь со статусом ok / caution / stop и пояснением."""
    otvet = sprosit_model(
        api_kluch,
        prochitat_prompt("safety.md"),
        anketa_v_tekst(anketa),
        max_tokenov=4000,
        shema_otveta=SHEMA_BEZOPASNOSTI,
    )
    try:
        return json.loads(otvet)
    except json.JSONDecodeError:
        raise OshibkaAPI(
            "Модель ответила не тем, что мы ждали",
            "На проверку анкеты должен прийти короткий ответ по строгой форме, "
            "а пришёл обычный текст. Нажми «Составить план» ещё раз — "
            "обычно со второго раза проходит.",
        )


def sostavit_trenirovki(api_kluch, anketa):
    """Шаг 2. Возвращает программу тренировок текстом в формате Markdown."""
    return sprosit_model(
        api_kluch,
        prochitat_prompt("workout.md"),
        anketa_v_tekst(anketa),
        max_tokenov=16000,
    )


def sostavit_pitanie(api_kluch, anketa):
    """Шаг 3. Возвращает план питания текстом в формате Markdown."""
    return sprosit_model(
        api_kluch,
        prochitat_prompt("nutrition.md"),
        anketa_v_tekst(anketa),
        max_tokenov=16000,
    )


def vzyat_primer_ankety():
    """Читает анкету-пример из examples/sample_profile.json.

    По ней же получены сохранённые ответы для демо-режима,
    и её подставляет в форму кнопка «Заполнить пример».
    """
    return json.loads(FAYL_PRIMERA_ANKETY.read_text(encoding="utf-8"))


def vzyat_demo_plan():
    """Возвращает заранее сохранённые ответы модели вместо обращения к API.

    Это настоящие ответы Gemini на анкету из sample_profile.json,
    записанные один раз в examples/demo_responses/.
    """
    try:
        return {
            "bezopasnost": json.loads((PAPKA_DEMO / "safety.json").read_text(encoding="utf-8")),
            "trenirovki": (PAPKA_DEMO / "workout.md").read_text(encoding="utf-8"),
            "pitanie": (PAPKA_DEMO / "nutrition.md").read_text(encoding="utf-8"),
        }
    except FileNotFoundError:
        raise OshibkaAPI(
            "Сохранённого примера плана нет",
            "Файлы демо-режима должны лежать в examples/demo_responses/. "
            "Введи ключ Gemini в левой панели — тогда план составится по-настоящему.",
        )


def sobrat_plan(api_kluch, anketa, pokazat_shag):
    """Проходит все шаги по порядку и возвращает результат.

    pokazat_shag — функция, которой передаём текст текущего шага,
    чтобы приложение показало его пользователю.

    В ответе три поля:
    bezopasnost — словарь со статусом и пояснением
    trenirovki  — текст программы или None, если статус stop
    pitanie     — текст плана питания или None, если статус stop
    """
    pokazat_shag("Проверяю анкету…")
    bezopasnost = proverit_bezopasnost(api_kluch, anketa)

    # При статусе stop ни программы, ни питания не составляем
    if bezopasnost["status"] == "stop":
        return {"bezopasnost": bezopasnost, "trenirovki": None, "pitanie": None}

    pokazat_shag("Составляю тренировки…")
    trenirovki = sostavit_trenirovki(api_kluch, anketa)

    pokazat_shag("Составляю план питания…")
    pitanie = sostavit_pitanie(api_kluch, anketa)

    return {"bezopasnost": bezopasnost, "trenirovki": trenirovki, "pitanie": pitanie}
