"""Записывает ответы модели для демо-режима.

Прогоняет все три шага пайплайна на анкете examples/sample_profile.json
и сохраняет настоящие ответы Gemini в examples/demo_responses/.
Именно их приложение показывает, когда ключа нет или в .env стоит
DEMO_MODE=true.

Запуск из папки проекта:

    venv\\Scripts\\Activate.ps1
    python scripts/zapisat_demo.py

Ключ скрипт спросит при запуске (ввод не отображается) или возьмёт
из переменной окружения GEMINI_API_KEY. В файлы проекта ключ не попадает.

Запускать заново имеет смысл, когда заметно поменялись промпты.
"""

import getpass
import json
import os
import sys
from pathlib import Path

# Скрипт лежит в scripts/, а пакет agent — на уровень выше.
# Без этой строки Python не найдёт импорт agent.pipeline.
PAPKA_PROEKTA = Path(__file__).parent.parent
sys.path.insert(0, str(PAPKA_PROEKTA))

from agent.llm import OshibkaAPI  # noqa: E402
from agent.pipeline import (  # noqa: E402
    PAPKA_DEMO,
    proverit_bezopasnost,
    sostavit_pitanie,
    sostavit_trenirovki,
    vzyat_primer_ankety,
)


def vzyat_kluch():
    """Берёт ключ из переменной окружения или спрашивает скрытым вводом."""
    kluch = os.getenv("GEMINI_API_KEY", "").strip()
    if kluch:
        print("Ключ взят из переменной окружения GEMINI_API_KEY.")
        return kluch
    return getpass.getpass("Ключ Google Gemini (ввод не виден): ").strip()


def main():
    kluch = vzyat_kluch()
    if not kluch:
        print("Ключ не введён — записывать нечего.")
        return 1

    anketa = vzyat_primer_ankety()
    print("Анкета-пример прочитана:", ", ".join(f"{k} — {v}" for k, v in list(anketa.items())[:4]))

    PAPKA_DEMO.mkdir(parents=True, exist_ok=True)

    try:
        print("Шаг 1: проверяю анкету…")
        bezopasnost = proverit_bezopasnost(kluch, anketa)
        print("   статус:", bezopasnost["status"])

        print("Шаг 2: составляю тренировки…")
        trenirovki = sostavit_trenirovki(kluch, anketa)

        print("Шаг 3: составляю питание…")
        pitanie = sostavit_pitanie(kluch, anketa)
    except OshibkaAPI as oshibka:
        print(f"\nНе получилось: {oshibka}")
        if oshibka.sovet:
            print(oshibka.sovet)
        return 1

    (PAPKA_DEMO / "safety.json").write_text(
        json.dumps(bezopasnost, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (PAPKA_DEMO / "workout.md").write_text(trenirovki, encoding="utf-8")
    (PAPKA_DEMO / "nutrition.md").write_text(pitanie, encoding="utf-8")

    print("\nГотово. Записано в", PAPKA_DEMO)
    print("   safety.json  —", len(json.dumps(bezopasnost)), "знаков")
    print("   workout.md   —", len(trenirovki), "знаков")
    print("   nutrition.md —", len(pitanie), "знаков")
    return 0


if __name__ == "__main__":
    sys.exit(main())
