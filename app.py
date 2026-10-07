"""Фитнес-агент — веб-приложение на Streamlit.

Пользователь заполняет анкету, Gemini проверяет её на безопасность,
составляет программу тренировок и план питания.
Без ключа приложение работает в демо-режиме.
"""

import os

import streamlit as st
from dotenv import load_dotenv

from agent.llm import OshibkaAPI
from agent.pipeline import sobrat_plan, vzyat_demo_plan, vzyat_primer_ankety

# Настройки страницы (заголовок во вкладке браузера и иконка)
st.set_page_config(page_title="Фитнес-агент", page_icon="💪")

# Читаем файл .env, если он есть. DEMO_MODE=true включает демо-режим
# принудительно — даже когда ключ введён. Удобно показывать приложение
# без расхода бесплатных запросов.
load_dotenv()
DEMO_IZ_ENV = os.getenv("DEMO_MODE", "").strip().lower() == "true"

# Предупреждение показываем и на странице, и в скачанном файле
DISKLEYMER = (
    "План составил ИИ по общим рекомендациям ВОЗ и ACSM. "
    "Это не медицинская консультация."
)

# Поля анкеты: ключ виджета в форме — подпись, под которой ответ уходит модели.
# Этот же список подставляет ответы кнопка «Заполнить пример».
POLYA = {
    "pol": "Пол",
    "vozrast": "Возраст, лет",
    "rost": "Рост, см",
    "ves": "Вес, кг",
    "cel": "Цель",
    "opyt": "Опыт тренировок",
    "dni": "Дней в неделю",
    "mesto": "Место тренировок",
    "travmy": "Травмы и ограничения",
    "eda": "Предпочтения в еде",
}


# --- Оформление ---------------------------------------------------------
# Один блок CSS на всё приложение: тёмная шапка, белая карточка формы,
# аккуратные подписи и кнопка. Цвета темы лежат в .streamlit/config.toml.
STILI = """
<style>
/* убираем служебную панель Streamlit сверху */
[data-testid="stAppDeployButton"] { display: none; }
[data-testid="stHeader"] { background: transparent; }

/* тёмная шапка */
.shapka {
    background: linear-gradient(135deg, #1B1F27 0%, #2E3744 100%);
    border-radius: 20px;
    padding: 36px 34px 32px;
    margin-bottom: 26px;
    color: #FFFFFF;
}
.shapka h1 {
    color: #FFFFFF;
    font-size: 2.1rem;
    font-weight: 700;
    margin: 10px 0 8px;
    letter-spacing: -0.02em;
}
.shapka p {
    color: #A7B0BF;
    font-size: 1rem;
    margin: 0;
    max-width: 440px;
}
.shapka .znak {
    display: inline-block;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 6px 12px;
    font-size: 1.3rem;
}

/* белая карточка, в которой лежит анкета */
[data-testid="stForm"] {
    background: #FFFFFF;
    border: 1px solid #E3E6EB;
    border-radius: 18px;
    padding: 26px 28px 22px;
    box-shadow: 0 10px 28px rgba(16, 20, 28, 0.06);
}

/* заголовки разделов внутри анкеты */
[data-testid="stForm"] h3 {
    font-size: 0.82rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #8A93A2;
    border-bottom: 1px solid #EDEFF2;
    padding: 0 0 8px;
    margin: 6px 0 4px;
}

/* подписи к полям */
[data-testid="stWidgetLabel"] p {
    font-weight: 600;
    color: #3A4150;
}

/* кнопка на всю ширину карточки
   (Streamlit ужимает блок с кнопкой по тексту, поэтому растягиваем и его) */
[data-testid="stElementContainer"]:has([data-testid="stFormSubmitButton"]),
[data-testid="stFormSubmitButton"] {
    width: 100%;
}
[data-testid="stBaseButton-primaryFormSubmit"] {
    width: 100%;
    height: 48px;
    font-weight: 600;
    font-size: 1rem;
    margin-top: 8px;
}

/* карточка с результатом и строки данных в ней */
.pole {
    border-bottom: 1px solid #EDEFF2;
    padding: 9px 0;
}
.pole .nazvanie {
    display: block;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #8A93A2;
}
.pole .znachenie {
    font-size: 1rem;
    font-weight: 600;
    color: #1A1D23;
}
</style>
"""
st.markdown(STILI, unsafe_allow_html=True)


# --- Боковая панель: ключ от Gemini -------------------------------------
# Ключ нигде не сохраняется: он живёт только в памяти открытой вкладки.
with st.sidebar:
    st.subheader("Подключение ИИ")

    api_kluch = st.text_input(
        "API-ключ Google Gemini",
        type="password",  # ввод скрыт точками, как пароль
        placeholder="AIza...",
    )

    if DEMO_IZ_ENV:
        st.info("В файле .env стоит DEMO_MODE=true — работает демо-режим.")
    elif api_kluch.strip():
        st.success("Ключ введён. План составит Gemini.")
    else:
        st.info("Ключа нет — работает демо-режим.")

    st.caption(
        "Ключ нужен только пока открыта эта страница. Он не сохраняется "
        "ни в код, ни в файлы и пропадает, когда ты закрываешь вкладку. "
        "Бесплатный ключ: aistudio.google.com/apikey"
    )


# --- Показ введённых данных ---------------------------------------------
def pokazat_anketu(anketa):
    """Выводит ответы карточкой в две колонки: чётные поля слева, нечётные справа."""
    with st.container(border=True):
        levaya, pravaya = st.columns(2)
        for nomer, (nazvanie, znachenie) in enumerate(anketa.items()):
            kolonka = levaya if nomer % 2 == 0 else pravaya
            kolonka.markdown(
                f"<div class='pole'>"
                f"<span class='nazvanie'>{nazvanie}</span>"
                f"<span class='znachenie'>{znachenie}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )


# --- Сборка файла для скачивания -----------------------------------------
def sobrat_fayl_plana(anketa, rezultat):
    """Склеивает анкету, тренировки и питание в один текст Markdown.

    Этот текст уходит в кнопку «Скачать план»: получается файл,
    который можно открыть в любом текстовом редакторе или распечатать.
    """
    stroki = ["# Мой план", "", "## Анкета", ""]

    for nazvanie, znachenie in anketa.items():
        stroki.append(f"- {nazvanie}: {znachenie}")

    stroki += ["", "## Проверка анкеты", "", rezultat["bezopasnost"]["poyasnenie"], ""]
    stroki += ["---", "", "# Тренировки", "", rezultat["trenirovki"], ""]
    stroki += ["---", "", "# Питание", "", rezultat["pitanie"], ""]
    stroki += ["---", "", f"*{DISKLEYMER}*", ""]

    return "\n".join(stroki)


# --- Показ готового плана ------------------------------------------------
def pokazat_plan(anketa, rezultat):
    """Выводит результат работы ИИ: проверку, потом тренировки и питание."""
    bezopasnost = rezultat["bezopasnost"]

    # Опасно тренироваться самостоятельно — плана не будет
    if bezopasnost["status"] == "stop":
        st.error(
            "**Сначала к врачу.** " + bezopasnost["poyasnenie"] + "\n\n"
            "План я не составляю: по анкете это может быть опасно. "
            "Вернись, когда врач разрешит нагрузки."
        )
        return

    # Тренироваться можно, но есть ограничения — предупреждаем и показываем план
    if bezopasnost["status"] == "caution":
        st.warning("**Тренироваться можно с осторожностью.** " + bezopasnost["poyasnenie"])
    else:
        st.success("**Ограничений по анкете нет.** " + bezopasnost["poyasnenie"])

    # Две части плана — на двух вкладках, чтобы страница не растягивалась
    trenirovki, pitanie = st.tabs(["🏋️ Тренировки", "🥗 Питание"])
    with trenirovki:
        st.markdown(rezultat["trenirovki"])
    with pitanie:
        st.markdown(rezultat["pitanie"])

    st.caption(DISKLEYMER)

    st.download_button(
        "Скачать план",
        data=sobrat_fayl_plana(anketa, rezultat),
        file_name="moy-plan.md",
        mime="text/markdown",
    )


# Шапка страницы
st.markdown(
    """
    <div class="shapka">
        <span class="znak">💪</span>
        <h1>Фитнес-агент</h1>
        <p>Ответь на несколько вопросов — получишь программу тренировок
        и план питания. Это займёт меньше минуты.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# --- Подстановка анкеты-примера -----------------------------------------
# Значение виджета можно менять только до того, как виджет создан.
# Поэтому кнопка «Заполнить пример» лишь поднимает флаг и перезапускает
# страницу, а сама подстановка происходит здесь — перед формой.
if st.session_state.get("zapolnit_primer"):
    st.session_state.zapolnit_primer = False
    primer = vzyat_primer_ankety()
    for klyuch, podpis in POLYA.items():
        st.session_state[klyuch] = primer[podpis]


# --- Анкета -------------------------------------------------------------
# Все поля собраны в одну форму: Streamlit не перезапускает страницу,
# пока пользователь не нажмёт одну из кнопок внизу.
with st.form("anketa"):
    st.subheader("О тебе")

    # Три поля в одну строку, чтобы анкета выглядела компактно
    col1, col2, col3 = st.columns(3)
    with col1:
        st.radio("Пол", ["Мужской", "Женский"], key="pol")
    with col2:
        st.number_input("Возраст, лет", min_value=14, max_value=90, value=30, key="vozrast")
    with col3:
        st.slider("Дней в неделю", min_value=2, max_value=6, value=3, key="dni")

    col4, col5 = st.columns(2)
    with col4:
        st.number_input("Рост, см", min_value=120, max_value=220, value=175, key="rost")
    with col5:
        st.number_input(
            "Вес, кг", min_value=35.0, max_value=200.0, value=75.0, step=0.5, key="ves"
        )

    st.subheader("Цель и условия")

    st.selectbox("Цель", ["Похудеть", "Набрать мышцы", "Поддерживать форму"], key="cel")

    col6, col7 = st.columns(2)
    with col6:
        st.selectbox(
            "Опыт тренировок",
            ["Новичок (до 6 месяцев)", "Средний (6 месяцев - 2 года)", "Опытный (больше 2 лет)"],
            key="opyt",
        )
    with col7:
        st.radio("Где тренируешься", ["Зал", "Дом"], horizontal=True, key="mesto")

    st.subheader("Необязательно")

    st.text_area(
        "Травмы и ограничения по здоровью",
        placeholder="Например: болит поясница, операция на колене",
        height=70,
        key="travmy",
    )
    st.text_area(
        "Предпочтения в еде",
        placeholder="Например: не ем мясо, аллергия на молоко",
        height=70,
        key="eda",
    )

    # Кнопки формы: основная и подстановка готовой анкеты
    knopka1, knopka2 = st.columns([2, 1])
    with knopka1:
        otpravleno = st.form_submit_button("Составить план", type="primary")
    with knopka2:
        zapolnit = st.form_submit_button("Заполнить пример")


# --- Работа по кнопке ----------------------------------------------------
# Streamlit перезапускает скрипт при каждом действии на странице: клике,
# изменении размера окна, вводе в поле. Поэтому анкету, план и текст ошибки
# складываем в st.session_state — иначе готовый план пропадал бы после
# любого такого перезапуска.
if zapolnit:
    # Сами значения подставятся наверху страницы после перезапуска
    st.session_state.zapolnit_primer = True
    st.rerun()

if otpravleno:
    # Ключ "otvety", а не "anketa": имя "anketa" занято самой формой
    # (st.form("anketa")), и Streamlit не даёт его перезаписывать.
    otvety = {}
    for klyuch, podpis in POLYA.items():
        znachenie = st.session_state[klyuch]
        # Необязательные поля могут остаться пустыми
        if isinstance(znachenie, str):
            znachenie = znachenie.strip() or "не указаны"
        otvety[podpis] = znachenie

    st.session_state.otvety = otvety
    st.session_state.plan = None
    st.session_state.oshibka = None
    # Без ключа или с DEMO_MODE=true показываем сохранённый пример
    st.session_state.demo = DEMO_IZ_ENV or not api_kluch.strip()

    if st.session_state.demo:
        try:
            st.session_state.plan = vzyat_demo_plan()
        except OshibkaAPI as oshibka:
            st.session_state.oshibka = (str(oshibka), oshibka.sovet)
    else:
        # Шаги выполняются по очереди, их названия появляются в этом блоке
        with st.status("Работаю над планом…", expanded=True) as progress:
            try:
                st.session_state.plan = sobrat_plan(
                    api_kluch.strip(), st.session_state.otvety, st.write
                )
            except OshibkaAPI as oshibka:
                st.session_state.oshibka = (str(oshibka), oshibka.sovet)
                progress.update(label="Не получилось", state="error")
            else:
                progress.update(label="Готово", state="complete", expanded=False)


# --- Вывод сохранённого результата ---------------------------------------
# Этот блок работает и после перезапуска скрипта, потому что берёт данные
# из st.session_state, а не из переменных формы.
if "otvety" in st.session_state:
    st.write("")  # отступ между формой и результатом
    pokazat_anketu(st.session_state.otvety)

    if st.session_state.oshibka:
        # Ошибка — не повод пугать красным: объясняем, что случилось и что делать
        chto_sluchilos, sovet = st.session_state.oshibka
        st.warning(f"**{chto_sluchilos}.** {sovet}")
    elif st.session_state.plan:
        if st.session_state.demo:
            # Честно предупреждаем: это не ответ модели на введённую анкету
            st.info(
                "**Демо-режим.** План ниже — не ответ модели на твои данные, "
                "а заранее сохранённый пример: его составил Gemini по анкете "
                "из `examples/sample_profile.json`. Кнопка «Заполнить пример» "
                "подставляет в форму ту самую анкету. Чтобы получить план по "
                "своим ответам, введи ключ Google Gemini в левой панели."
            )
        pokazat_plan(st.session_state.otvety, st.session_state.plan)
