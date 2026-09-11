#!/usr/bin/env python3
"""
Fill/fix all remaining fuzzy/empty Russian translations.

Uses Google Translate (uz→ru) + a glossary of hotel PMS terms.
Preserves gettext placeholders like %(name)s and {{ var }}.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import polib
from deep_translator import GoogleTranslator

ROOT = Path(__file__).resolve().parents[1]
PO_PATH = ROOT / "locale/ru/LC_MESSAGES/django.po"

# Prefer these over machine translation (hotel PMS vocabulary)
GLOSSARY: dict[str, str] = {
    "Yo‘naltiruvchi": "Направляющий",
    "Yo‘naltiruvchilar": "Направляющие",
    "Yo‘naltiruvchi qo‘shildi.": "Направляющий добавлен.",
    "Yo‘naltiruvchi yangilandi.": "Направляющий обновлён.",
    "Yo‘naltiruvchini tahrirlash": "Редактировать направляющего",
    "Yangi yo‘naltiruvchi": "Новый направляющий",
    "Yo‘naltiruvchi ushbu mehmonxonaga tegishli emas.": "Направляющий не относится к этой гостинице.",
    "Yo‘naltiruvchi foizi %": "Процент направляющего %",
    "Kim orqali": "Через кого",
    "E-mehmon": "E-mehmon",
    "E-mehmon farq": "Разница E-mehmon",
    "E-mehmon hisoboti": "Отчёт E-mehmon",
    "E-mehmon chek": "Чек E-mehmon",
    "E-mehmon to‘lovi": "Оплата E-mehmon",
    "E-mehmon to‘lov usuli": "Способ оплаты E-mehmon",
    "E-mehmon to‘langan": "E-mehmon оплачен",
    "E-mehmon summasi": "Сумма E-mehmon",
    "E-mehmon komissiyasini olish": "Принять комиссию E-mehmon",
    "E-mehmon to‘lovini olish uchun summa kiriting.": "Введите сумму для приёма оплаты E-mehmon.",
    "E-mehmon to‘lovi qabul qilindi.": "Оплата E-mehmon принята.",
    "E-mehmon summasi musbat bo‘lishi kerak.": "Сумма E-mehmon должна быть положительной.",
    "E-mehmon to‘lovi allaqachon yozilgan.": "Оплата E-mehmon уже записана.",
    "E-mehmon: ro‘yxatdan o‘tkazish": "E-mehmon: регистрация",
    "E-mehmon formasi noto‘g‘ri.": "Неверная форма E-mehmon.",
    "Kassa": "Касса",
    "Kassa kirim": "Приход в кассу",
    "Kassa chiqim": "Расход из кассы",
    "Kassa harakati yozildi.": "Движение кассы записано.",
    "Kassa smenasi uchun filial tanlang.": "Выберите филиал для кассовой смены.",
    "Bu filialda ochiq kassa smenasi allaqachon bor.": "В этом филиале уже есть открытая кассовая смена.",
    "Naqd to‘lovdan oldin shu filial kassa smenasini oching.": (
        "Перед наличной оплатой откройте кассовую смену этого филиала."
    ),
    "Sanab chiqilgan naqd": "Пересчитанная наличность",
    "Masalan: sdachi naqd": "Например: сдача наличными",
    "Hisob-faktura": "Счёт-фактура",
    "Kompaniya hisob-fakturasi": "Счёт-фактура компании",
    "Jami (mehmonxona)": "Итого (гостиница)",
    "Hujjat": "Документ",
    "Pasport / ID raqami": "Паспорт / ID номер",
    "Bonus": "Бонус",
    "Ushlama": "Удержание",
    "Yaroqlilik muddati": "Срок годности",
    "Ogohlantirish (kun)": "Предупреждение (дней)",
    "Yangi parol": "Новый пароль",
    "Parolni takrorlang": "Повторите пароль",
    "Parol kamida 8 belgidan iborat bo‘lsin.": "Пароль должен содержать не менее 8 символов.",
    "Parollar mos kelmadi.": "Пароли не совпадают.",
    "Bo‘sh qoldirsangiz — parol o‘zgarmaydi.": "Если оставить пустым — пароль не изменится.",
    "Profil yangilandi.": "Профиль обновлён.",
    "Profilni tahrirlash": "Редактировать профиль",
    "Akkaunt o‘chirildi.": "Аккаунт удалён.",
    "Akkauntingiz o‘chirilsinmi? Tizimga kira olmaysiz. Bu amalni qaytarib bo‘lmaydi.": (
        "Удалить ваш аккаунт? Вы не сможете войти. Это действие необратимо."
    ),
    "Yagona admin akkauntini o‘chirib bo‘lmaydi. Avval boshqa admin qo‘shing.": (
        "Нельзя удалить единственный аккаунт администратора. Сначала добавьте другого админа."
    ),
    "Summa musbat bo‘lishi kerak.": "Сумма должна быть положительной.",
    "Valyuta noto‘g‘ri.": "Неверная валюта.",
    "— yo‘q —": "— нет —",
    "Kerakli xona turi": "Нужный тип номера",
    "Standart foiz %": "Стандартный процент %",
    "Xona / tur almashtirildi.": "Номер / тип заменён.",
    "Kurs soni noto‘g‘ri: %(c)s": "Неверное значение курса: %(c)s",
    "USD/EUR kurslari topilmadi.": "Курсы USD/EUR не найдены.",
    "Muddati o‘tgan · %(name)s": "Срок истёк · %(name)s",
    "Muddat yaqin · %(name)s": "Срок скоро · %(name)s",
    "%(qty)s %(unit)s · %(d)s": "%(qty)s %(unit)s · %(d)s",
    "Noto‘g‘ri harakat turi.": "Неверный тип операции.",
    "Qaytarish formasi noto‘g‘ri.": "Неверная форма возврата.",
    "Qaytarish summasi musbat bo‘lishi kerak.": "Сумма возврата должна быть положительной.",
    "Joylashgan mehmon hisobini yopib bo‘lmaydi — avval chiqish qiling.": (
        "Нельзя закрыть счёт размещённого гостя — сначала сделайте выезд."
    ),
    "Mehmon o‘chirildi: %(name)s": "Гость удалён: %(name)s",
    "Faol bo‘lmagan xodimga avans berib bo‘lmaydi.": "Нельзя выдать аванс неактивному сотруднику.",
    "Faol bo‘lmagan xodimga oylik berib bo‘lmaydi.": "Нельзя выдать зарплату неактивному сотруднику.",
    "To‘langan qatorni o‘zgartirib bo‘lmaydi.": "Оплаченную строку изменить нельзя.",
    "Bonus manfiy bo‘lmasligi kerak.": "Бонус не может быть отрицательным.",
    "Ushlama manfiy bo‘lmasligi kerak.": "Удержание не может быть отрицательным.",
    "Bu qator allaqachon to‘langan.": "Эта строка уже оплачена.",
    "To‘lov summasi manfiy bo‘lmasligi kerak.": "Сумма оплаты не может быть отрицательной.",
    "%(name)s ga avans yozildi.": "Аванс для %(name)s записан.",
    "Avans: %(name)s": "Аванс: %(name)s",
    "Ish haqi yangilandi: %(p)s": "Зарплата обновлена: %(p)s",
    "%(n)s ta oylik to‘landi.": "Выплачено зарплат: %(n)s.",
    "Bo‘sh qoldirilsa muddat kuzatilmaydi.": "Если пусто — срок не отслеживается.",
    "Yangilandi.": "Обновлено.",
    "Mahsulotni tahrirlash": "Редактировать товар",
    "Avval filial tanlang.": "Сначала выберите филиал.",
    "Yopilgan arizani tahrirlab bo‘lmaydi.": "Закрытую заявку редактировать нельзя.",
    "Xarajat yozildi.": "Расход записан.",
    "Xarajat yozish": "Записать расход",
    "Xarajat yangilandi.": "Расход обновлён.",
    "Xarajatni tahrirlash": "Редактировать расход",
    "Xarajat o‘chirildi.": "Расход удалён.",
    "To‘langan jami": "Всего оплачено",
    "To‘langan (sof)": "Оплачено (чистыми)",
    "Email": "Email",
    "Flash": "Flash",
    "Net": "Нетто",
    "Qo‘shimcha · Дополнительно": "Дополнительно",
    "So‘m (UZS)": "Сум (UZS)",
    "Dollar (USD)": "Доллар (USD)",
    "Euro (EUR)": "Евро (EUR)",
    "Valyuta faqat UZS, USD yoki EUR bo‘lishi mumkin.": "Валюта может быть только UZS, USD или EUR.",
    "Narx (1 kecha)": "Цена (1 ночь)",
    "Kelishilgan bir kechalik summa. Jami = narx × kechalar.": (
        "Согласованная сумма за ночь. Итого = цена × ночи."
    ),
    "Narx shu valyutada — UZS, USD yoki EUR.": "Цена в этой валюте — UZS, USD или EUR.",
    "Foiz 0–100 oralig‘ida bo‘lishi kerak.": "Процент должен быть от 0 до 100.",
    "1 kecha narxini kiriting.": "Введите цену за 1 ночь.",
    "— barcha turlar —": "— все типы —",
    "True — E-mehmon: tarif × kecha × mehmon; False — bu bronda olinmaydi.": (
        "True — E-mehmon: тариф × ночь × гость; False — для этой брони не берётся."
    ),
    "Xona boshqa filialga tegishli.": "Номер относится к другому филиалу.",
    "%(name)s ga %(amount)s %(cur)s to‘landi.": "%(name)s выплачено %(amount)s %(cur)s.",
    "To‘lov saqlanmadi — %(d)s": "Оплата не сохранена — %(d)s",
    "To‘lov saqlanmadi — maydonlarni tekshiring.": "Оплата не сохранена — проверьте поля.",
    "Markaziy bank javob bermadi (HTTP %(code)s).": "ЦБ не ответил (HTTP %(code)s).",
    "Markaziy bankka ulanishning iloji bo‘lmadi: %(err)s": "Не удалось связаться с ЦБ: %(err)s",
    "Markaziy bank javobi JSON emas.": "Ответ ЦБ не в формате JSON.",
    "Markaziy bank formati kutilgandek emas.": "Формат ответа ЦБ неожиданный.",
    "Bazaviy %(b)s uchun Markaziy bank kursi yo‘q.": "Нет курса ЦБ для базовой %(b)s.",
    "Qolgan summadan ko‘p: qolgan %(r)s %(cur)s, so‘ralgan %(a)s %(pay)s.": (
        "Больше остатка: осталось %(r)s %(cur)s, запрошено %(a)s %(pay)s."
    ),
    "Ulush qoldig‘idan ko‘p: qolgan %(r)s %(cur)s, so‘ralgan %(a)s %(pay)s.": (
        "Больше остатка доли: осталось %(r)s %(cur)s, запрошено %(a)s %(pay)s."
    ),
}

PLACEHOLDER_RE = re.compile(
    r"(%\([^)]+\)[sdifr]|%\d*\$?[sdifr]|%\([^)]+\)s|\{\{\s*[^}]+\s*\}\}|\{[a-zA-Z_][a-zA-Z0-9_]*\})"
)


def protect(text: str) -> tuple[str, list[str]]:
    held: list[str] = []

    def repl(m: re.Match) -> str:
        held.append(m.group(0))
        return f"⟦{len(held) - 1}⟧"

    return PLACEHOLDER_RE.sub(repl, text), held


def restore(text: str, held: list[str]) -> str:
    def repl(m: re.Match) -> str:
        i = int(m.group(1))
        return held[i] if 0 <= i < len(held) else m.group(0)

    return re.sub(r"⟦(\d+)⟧", repl, text)


def needs_fix(entry: polib.POEntry) -> bool:
    if entry.obsolete or not entry.msgid or entry.msgid_plural:
        return False
    if "fuzzy" in entry.flags:
        return True
    if not entry.msgstr.strip():
        return True
    if entry.msgstr == entry.msgid and not entry.msgid.isascii():
        return True
    return False


def translate_one(translator: GoogleTranslator, msgid: str, fallback: str = "") -> str:
    if msgid in GLOSSARY:
        return GLOSSARY[msgid]
    # Already mostly Russian / bilingual label
    if "·" in msgid and re.search(r"[А-Яа-яЁё]", msgid):
        parts = [p.strip() for p in msgid.split("·")]
        ru_parts = [p for p in parts if re.search(r"[А-Яа-яЁё]", p)]
        if ru_parts:
            return ru_parts[-1]
    if msgid.isascii() and len(msgid) <= 24 and " " not in msgid.strip():
        return msgid  # Email, Flash, HTTP-ish tokens
    protected, held = protect(msgid)
    out = None
    for attempt in range(3):
        try:
            out = translator.translate(protected)
            break
        except Exception:
            time.sleep(1.5 + attempt)
            try:
                # retry with auto language detect
                out = GoogleTranslator(source="auto", target="ru").translate(protected)
                break
            except Exception:
                out = None
    if not out:
        # keep previous Russian if it looks Russian; else leave msgid for later
        if fallback and re.search(r"[А-Яа-яЁё]", fallback) and "fuzzy" not in fallback:
            return fallback
        if fallback and re.search(r"[А-Яа-яЁё]", fallback):
            return fallback
        return msgid
    out = restore(out, held)
    return out.strip() or msgid


def main() -> None:
    # Merge previous finance glossary if present
    finance_script = ROOT / "scripts/fix_ru_finance_i18n.py"
    if finance_script.exists():
        ns: dict = {"__file__": str(finance_script), "__name__": "fix_ru_finance_i18n"}
        exec(finance_script.read_text(encoding="utf-8"), ns)
        GLOSSARY.update(ns.get("RU") or {})

    # Extra hard-coded for strings MT often fails on
    GLOSSARY.update(
        {
            "Ixtiyoriy. Faqat «Kim orqali» tanlanganda — shu odamga xona summasidan foiz.": (
                "Необязательно. Только если выбран «Через кого» — процент этому человеку от суммы номера."
            ),
            "Ixtiyoriy. Faqat «Kim orqali» tanlanganda.": (
                "Необязательно. Только если выбран «Через кого»."
            ),
            "Bu odam orqali kelgan mehmonlar uchun odatdagi foiz.": (
                "Обычный процент для гостей, пришедших через этого человека."
            ),
            "Standart: yoqilgan. Hisob = %(u)s so‘m × kechalar × mehmonlar. O‘chirsangiz — bu mehmondan": (
                "По умолчанию включено. Счёт = %(u)s сум × ночи × гости. Если выключить — с этого гостя"
            ),
            "Boshqa turdagi xona tanlansa (masalan Twin↔Double) — tur avtomatik yangilanadi.": (
                "Если выбран номер другого типа (например Twin↔Double) — тип обновится автоматически."
            ),
            "Mehmon Twin so‘rasa — Twin ni tanlang; Double↔Twin va boshqalar mumkin.": (
                "Если гость просит Twin — выберите Twin; Double↔Twin и другие варианты возможны."
            ),
            "Yangi tur BAR tarifiga o‘tkazish (faqat eski bronlar)": (
                "Перевести новый тип на тариф BAR (только старые брони)"
            ),
            "Masalan: mehmon Twin so‘radi": "Например: гость просил Twin",
            "Tanlangan xona «%(room)s» turi «%(got)s», filtr esa «%(want)s».": (
                "Выбранный номер «%(room)s» типа «%(got)s», фильтр — «%(want)s»."
            ),
            "Bron yaratilganda foiz shu qiymatdan to‘ldiriladi.": (
                "При создании брони процент подставляется из этого значения."
            ),
            "Yo‘naltiruvchiga bron summasidan foiz.": "Процент направляющему от суммы брони.",
            "Narx shu valyutada — UZS, USD yoki EUR.": "Цена в этой валюте — UZS, USD или EUR.",
        }
    )

    po = polib.pofile(str(PO_PATH))
    todo = [e for e in po if needs_fix(e)]
    print(f"to_fix={len(todo)}")
    translator = GoogleTranslator(source="uz", target="ru")
    fixed = 0
    failed = 0
    for i, entry in enumerate(todo, 1):
        new = translate_one(translator, entry.msgid, fallback=entry.msgstr or "")
        if new == entry.msgid and not re.search(r"[А-Яа-яЁё]", new):
            failed += 1
        entry.msgstr = new
        if "fuzzy" in entry.flags:
            entry.flags = [f for f in entry.flags if f != "fuzzy"]
        fixed += 1
        if i % 25 == 0:
            print(f"  … {i}/{len(todo)} failed_left_uz~{failed}")
            po.save()
            time.sleep(0.5)
        else:
            time.sleep(0.05)
    po.save()
    print(f"done fixed={fixed} still_uz_like={failed}")

if __name__ == "__main__":
    main()
