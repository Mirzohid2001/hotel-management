#!/usr/bin/env python3
"""Fix RU translations for finance / maintenance / reports UI (fuzzy + missing)."""

from __future__ import annotations

import sys
from pathlib import Path

import polib

ROOT = Path(__file__).resolve().parents[1]
PO_PATH = ROOT / "locale/ru/LC_MESSAGES/django.po"

# msgid (uz source) -> msgstr (ru)
RU: dict[str, str] = {
    # Core finance / profit share
    "Foyda ulushi": "Доля прибыли",
    "Foyda ulushi — chek hisobot": "Доля прибыли — чек-отчёт",
    "Foyda ulushi — tarix": "Доля прибыли — история",
    "Foyda ulushi davrlari": "Периоды доли прибыли",
    "Foyda/zarar": "Прибыль/убыток",
    "Foyda/zarar — chek": "Прибыль/убыток — чек",
    "Foyda/zarar — chek bayonnoma": "Прибыль/убыток — чек / акт",
    "Foyda/zarar xulosasi": "Итог прибыли/убытка",
    "Sof foyda": "Чистая прибыль",
    "Sof foyda hisobi": "Расчёт чистой прибыли",
    "1. Sof foyda hisobi": "1. Расчёт чистой прибыли",
    "2. Sheriklar bo‘yicha taqsimlash": "2. Распределение по партнёрам",
    "Taqsimlanadigan": "К распределению",
    "Taqsimlanmagan": "Не распределено",
    "Taqsimlanadigan jami (ulushlar)": "Итого к распределению (доли)",
    "Jami qoldiq (olish mumkin)": "Итого остаток (можно вывести)",
    "Reinvestitsiya": "Реинвестиции",
    "Reinvestitsiya (foydadan)": "Реинвестиции (из прибыли)",
    "Reinvestitsiya (ulushdan)": "Реинвестиции (из доли)",
    "Reinvestitsiya:": "Реинвестиции:",
    "Operatsion jami": "Итого операционные",
    "Operatsion xarajat": "Операционный расход",
    "Jami operatsion": "Итого операционные",
    "Tushum": "Выручка",
    "Tushum jami": "Итого выручка",
    "Tushum minus operatsion xarajatlar. Reinvestitsiya bu yerga kirmaydi.": (
        "Выручка минус операционные расходы. Реинвестиции сюда не входят."
    ),
    "Mehmon to‘lovlari": "Платежи гостей",
    "Kompaniya to‘lovlari": "Платежи компаний",
    "Rasxod (joriy)": "Расход (текущий)",
    "Rasxodlar": "Расходы",
    "Rasxod": "Расход",
    "Mehnat (yalpi)": "Фонд оплаты труда (брутто)",
    "Mehnat": "Оплата труда",
    "Yo‘naltiruvchi komissiya": "Комиссия агента",
    "Ombor tannarx": "Себестоимость склада",
    "Ombor": "Склад",
    "E-mehmon farq": "Разница E-mehmon",
    "Ulushlar shu summadan hisoblanadi": "Доли считаются от этой суммы",
    "Sof foydadan ulush": "Доля от чистой прибыли",
    "Chek hisobot": "Чек-отчёт",
    "Chek bayonnoma": "Чек / акт",
    "Bayonnoma / chek": "Акт / чек",
    "Chop etish": "Печать",
    "Chop etilgan": "Напечатано",
    "Tarix": "История",
    "Tarixni ochish": "Открыть историю",
    "Davr": "Период",
    "Davrni ochish": "Открыть период",
    "Davrni yopish": "Закрыть период",
    "Joriy davr": "Текущий период",
    "Barcha davrlar": "Все периоды",
    "Barcha yillar": "Все годы",
    "Barcha hisobotlar": "Все отчёты",
    "Hisobotlar tarixi": "История отчётов",
    "Hali yopilgan davr yo‘q": "Закрытых периодов пока нет",
    "Bu yilda yopilgan foyda davri yo‘q.": "В этом году закрытых периодов прибыли нет.",
    "0 qilib qayta": "Обнулить и заново",
    "0 qilib qayta hisob": "Обнулить и считать заново",
    "Sherik": "Партнёр",
    "Sheriklar": "Партнёры",
    "Sheriklik": "Партнёрство",
    "Sherik qo‘shish": "Добавить партнёра",
    "Sherik qo‘shildi.": "Партнёр добавлен.",
    "Sherik yangilandi.": "Партнёр обновлён.",
    "Sherikni tahrirlash": "Редактировать партнёра",
    "Sherik topilmadi.": "Партнёр не найден.",
    "Hali sherik yo‘q": "Пока нет партнёров",
    "Birinchi sherik": "Первый партнёр",
    "Foyda olish": "Вывод прибыли",
    "Foyda olishlar": "Выводы прибыли",
    "Foyda olish yozildi.": "Вывод прибыли записан.",
    "Qoldiqni olish": "Вывести остаток",
    "Olish": "Вывести",
    "Olingan": "Получено",
    "Olingan jami": "Всего получено",
    "Qoldiq": "Остаток",
    "Ulush": "Доля",
    "Foiz": "Процент",
    "Keyingi qadamlar": "Следующие шаги",
    "Diqqat:": "Внимание:",
    "Moliya": "Финансы",
    "Moliya va hisobot": "Финансы и отчёты",
    "Moliyalashtirish": "Финансирование",
    "Moliyalashtirish turi noto‘g‘ri.": "Неверный тип финансирования.",
    "Joriy": "Текущие",
    "Joriy (sof)": "Текущие (из чистой)",
    "Joriy (Sofdan)": "Текущие (из чистой)",
    "Joriy (sof foydadan)": "Текущие (из чистой прибыли)",
    "Joriy — sof foydadan. Reinvestitsiya — sof foydaga tegmaydi, ulushi eng katta sherikdan ayiriladi.": (
        "Текущие — из чистой прибыли. Реинвестиции на чистую не влияют, "
        "вычитаются из доли крупнейшего партнёра."
    ),
    "Joriy — sof foydadan. Reinvestitsiya — sof foydaga tegmaydi, ulushi katta sherikdan.": (
        "Текущие — из чистой прибыли. Реинвестиции на чистую не влияют, "
        "вычитаются из доли крупнейшего партнёра."
    ),
    "Xarajat qo‘shish": "Добавить расход",
    "Xarajatlar": "Расходы",
    "Pul": "Деньги",
    "Ta’mir": "Ремонт",
    "Ariza · xarajat": "Заявка · расход",
    "Ariza": "Заявка",
    "Arizalar": "Заявки",
    "Ariza (ixtiyoriy)": "Заявка (необязательно)",
    "Ariza ochish": "Открыть заявку",
    "Arizani tahrirlash": "Редактировать заявку",
    "Ariza bekor qilindi.": "Заявка отменена.",
    "Ariza o‘chirildi.": "Заявка удалена.",
    "Ariza topilmadi.": "Заявка не найдена.",
    "Ariza yangilandi.": "Заявка обновлена.",
    "Ariza yo‘q": "Нет заявок",
    "Ta’mir arizasi": "Заявка на ремонт",
    "Bu oyda Remont xarajati yo‘q.": "В этом месяце расходов на ремонт нет.",
    "Joriy oy xarajatlari — chop etish / imzo": "Расходы текущего месяца — печать / подпись",
    "Jami chiqim": "Итого расход",
    "Chiqim tafsiloti": "Детализация расхода",
    "Imzo / sana": "Подпись / дата",
    "F.I.Sh / imzo": "ФИО / подпись",
    "Direktor / uchreditel": "Директор / учредитель",
    "Bekor": "Отмена",
    "Bekor qilinsinmi?": "Отменить?",
    "O‘chirilsinmi?": "Удалить?",
    "O‘zgartirish": "Изменить",
    "Filtr": "Фильтр",
    "To‘langan": "Оплачено",
    "Naqd": "Наличные",
    "Karta": "Карта",
    "Komissiya": "Комиссия",
    "Komissiya foizi": "Процент комиссии",
    "Oylik hisobot": "Месячный отчёт",
    "Oylik komissiya": "Месячная комиссия",
    "Kunlik hisobot (chek)": "Суточный отчёт (чек)",
    "Flash": "Flash",
    "Net": "Нетто",
    "E-mehmon": "E-mehmon",
    "E-mehmon chek": "Чек E-mehmon",
    "E-mehmon hisoboti": "Отчёт E-mehmon",
    "E-mehmon farq": "Разница E-mehmon",
    "Debitorika": "Дебиторка",
    "Debitorlar": "Дебиторы",
    "Kompaniya hisobi": "Счёт компании",
    "Kassa": "Касса",
    "Smena": "Смена",
    "Valyutalar": "Валюты",
    "Valyuta": "Валюта",
    "Bazaviy valyuta": "Базовая валюта",
    "Bazaviy valyuta: %(c)s": "Базовая валюта: %(c)s",
    "Bazaviy valyuta uchun kurs kiritilmaydi.": "Для базовой валюты курс не вводится.",
    "Joriy kurslar": "Текущие курсы",
    "Kurs qo‘shish": "Добавить курс",
    "Kurs o‘chirildi.": "Курс удалён.",
    "Kurs saqlandi: 1 %(c)s = %(r)s %(b)s": "Курс сохранён: 1 %(c)s = %(r)s %(b)s",
    "Kurs tarixi": "История курсов",
    "Kurs (1 birlik → baza)": "Курс (1 единица → база)",
    "Kurslar har kuni Markaziy bank (cbu.uz) dan avtomatik olinadi. Qo‘lda ham yangilash mumkin.": (
        "Курсы ежедневно подтягиваются с ЦБ (cbu.uz). Можно обновить вручную."
    ),
    "MB dan qayta yuklash": "Перезагрузить с ЦБ",
    "Markaziy bankdan yuklash": "Загрузить с ЦБ",
    "Markaziy bank kursi yangilandi (%(d)s).": "Курс ЦБ обновлён (%(d)s).",
    "CBU: %(d)s — %(rates)s": "ЦБ: %(d)s — %(rates)s",
    "Hali kurs yo‘q — default ishlatiladi.": "Курсов пока нет — используется значение по умолчанию.",
    "Barcha hisobotlar va mehmon hisobi qoldig‘i shu valyutada yuritiladi.": (
        "Все отчёты и остаток гостевого счёта ведутся в этой валюте."
    ),
    "Faqat bazaviy valyuta.": "Только базовая валюта.",
    "Amal qilish sanasi": "Дата действия",
    "Biriktir": "Назначить",
    "Bugungi xonalar": "Номера на сегодня",
    "Darhol kirish": "Сразу заселить",
    "Kerakli modulga bir bosishda o‘ting.": "Перейдите в нужный раздел одним нажатием.",
    "Batafsil statistika uchun menejer yoki hisobchi hisobidan kiring.": (
        "Для подробной статистики войдите как менеджер или бухгалтер."
    ),
    "Filial tanlang.": "Выберите филиал.",
    "Faqat to‘langan xarajat bekor qilinadi.": "Отменяется только оплаченный расход.",
    "Faqat to‘langan xarajat tahrirlanadi.": "Редактируется только оплаченный расход.",
    "Remont xarajati bekor qilindi.": "Расход на ремонт отменён.",
    "Tanlangan qoldiq": "Выбранный остаток",
    "Faol (ochiq + jarayon)": "Активные (открытые + в работе)",
    "Arizalar va xarajatlar — joriy ta’mir yoki reinvestitsiya.": (
        "Заявки и расходы — текущий ремонт или реинвестиции."
    ),
    "Avval sof foydadan foiz, keyin reinvestitsiya ulushi katta sherikdan.": (
        "Сначала процент от чистой прибыли, затем реинвестиции с доли крупнейшего партнёра."
    ),
    "Qaysi operatsiyaga qancha ketayotgani — qatorma-qator. Sof foydadan foiz; reinvestitsiya ulushi katta sherikdan.": (
        "Построчно: куда сколько уходит. Процент от чистой; реинвестиции с доли крупнейшего партнёра."
    ),
    "Har bir qator: qayerdan keldi / qayerga ketdi.": "Каждая строка: откуда пришло / куда ушло.",
    "Ulushlar shu summadan hisoblanadi": "Доли считаются от этой суммы",
    "%(name)s — %(pct)s%% × sof foyda": "%(name)s — %(pct)s%% × чистая прибыль",
    "%(name)s — qoldiq": "%(name)s — остаток",
    "%(name)s — sof ulush": "%(name)s — чистая доля",
    "Reinvestitsiya (%(name)s ulushidan)": "Реинвестиции (из доли %(name)s)",
    "Yo‘naltiruvchi komissiya": "Комиссия агента",
    "Kirish sanasi bo‘yicha; to‘lov Sofni o‘chirmaydi": (
        "По дате заезда; оплата чистую не обнуляет"
    ),
    "Avval sheriklarni qo‘shing (ulushlar yig‘indisi 100% bo‘lsin).": (
        "Сначала добавьте партнёров (сумма долей должна быть 100%)."
    ),
    "Hali %(gap)s%% ulush biriktirilmagan — qolgan sheriklarni qo‘shing yoki foizlarni 100%% ga to‘ldiring.": (
        "Ещё %(gap)s%% доли не назначено — добавьте партнёров или доведите проценты до 100%%."
    ),
    "Sheriklar hali %(r)s olishi mumkin. Qoldiqni «Olish» orqali yozing.": (
        "Партнёры ещё могут получить %(r)s. Остаток запишите через «Вывести»."
    ),
    "Bu davrdagi ulushlar yopildi. «0 qilib qayta» — yangi sof hisobni boshlang.": (
        "Доли за этот период закрыты. «Обнулить и заново» — начать новый чистый расчёт."
    ),
    "Qisman olindi. Qolganini oling yoki tayyor bo‘lsangiz davrni 0 qilib yangilang.": (
        "Получено частично. Заберите остаток или обнулите период, когда будете готовы."
    ),
    "Barcha qoldiqlar yopilgan. Yangi sof hisobni boshlashga tayyor.": (
        "Все остатки закрыты. Можно начинать новый чистый расчёт."
    ),
    "Bu ochiq davrda sof foyda manfiy (%(n)s): tushum yo‘q yoki xarajat ko‘p. "
    "Oldingi foyda «Tarix»da. Sheriklarga zarar ulush qilib yozilmaydi. "
    "Toza boshlash: «0 qilib qayta» (ertadan).": (
        "В открытом периоде чистая прибыль отрицательная (%(n)s): нет выручки или много расходов. "
        "Предыдущая прибыль в «Истории». Убыток партнёрам долей не пишется. "
        "Чистый старт: «Обнулить и заново» (со следующего дня)."
    ),
    "Bu ochiq ekranda reinvestitsiya 0. Remont dagi "
    "%(a)s «0 qilib qayta» yopgan davrda (%(s)s → %(e)s) — kalendar "
    "bo‘yicha yaqin kunlar, lekin boshqa foyda davri.": (
        "На этом экране реинвестиции 0. Сумма %(a)s из Ремонта относится к периоду, "
        "закрытому «Обнулить и заново» (%(s)s → %(e)s) — по календарю недавние дни, "
        "но другой период прибыли."
    ),
    "Yangi bo‘sh foyda davri %(d)s dan. Hozir ko‘rsatilayotgani — "
    "«0 qilib qayta» yopgan davr (%(s)s → %(e)s): bugungi/kechagi "
    "rasxod va reinvestitsiya shu yerda.": (
        "Новый пустой период прибыли с %(d)s. Сейчас показан период, закрытый "
        "«Обнулить и заново» (%(s)s → %(e)s): сегодняшние/вчерашние расходы и "
        "реинвестиции здесь."
    ),
    "Bu rasxodlar «o‘tgan oy» emas — kalendar bo‘yicha yaqin kunlar ({{ start }} → {{ end }}). "
    "«0 qilib qayta» shu kunlarni yopiq foyda davriga yozgan; yangi bo‘sh davr {{ new }} dan. "
    "Pastda aynan shu yopiq davr ko‘rsatilmoqda (reinvestitsiya shu yerda).": (
        "Это не «прошлый месяц» — по календарю недавние дни ({{ start }} → {{ end }}). "
        "«Обнулить и заново» закрыл эти дни в период прибыли; новый пустой период с {{ new }}. "
        "Ниже показан именно этот закрытый период (реинвестиции здесь)."
    ),
    "Joriy davr ({{ start }} → {{ end }}) sof foydasi manfiy.": (
        "Чистая прибыль текущего периода ({{ start }} → {{ end }}) отрицательная."
    ),
    "Bu odatda «0 qilib qayta»dan keyin — faqat yangi kun xarajatlari. Oldingi katta foyda «Tarix»da. Xarajat to‘laganingiz Sofni kamaytiradi (to‘lov Sofni nol qilmaydi).": (
        "Обычно после «Обнулить и заново» — только расходы нового дня. Крупная прибыль раньше — в «Истории». "
        "Оплата расхода уменьшает чистую (не обнуляет её)."
    ),
    "Bu ekranda 0. Remont dagi summa boshqa foyda davrida ({{ start }} → {{ end }}).": (
        "На этом экране 0. Сумма из Ремонта в другом периоде прибыли ({{ start }} → {{ end }})."
    ),
    "Ochiq davrda 0 — chunki Remont dagi reinvestitsiya oxirgi yopiq davrga ({{ start }} → {{ end }}) tegishli.": (
        "В открытом периоде 0 — реинвестиции из Ремонта относятся к последнему закрытому периоду "
        "({{ start }} → {{ end }})."
    ),
    "Faol ulushlar: {{ sum }}%. Ideal 100% (qolgan {{ gap }}%). Har foiz sof foydadan hisoblanadi; biriktirilmagan qism «Taqsimlanmagan»da.": (
        "Активные доли: {{ sum }}%. Идеал 100% (осталось {{ gap }}%). Каждый процент от чистой; "
        "неназначенная часть в «Не распределено»."
    ),
    "Yopilgandan keyin yangi davr odatda ertasi kundan boshlanadi. «Bugundan» — yopiq davr kechagacha qoladi, bugungi tushum/xarajat faqat yangi ochiq davrda. Allaqachon faqat bugungi stub bo‘lsa — ertadan toza boshlanadi (bir xil −summa takrorlanmaydi). Tarix saqlanadi.": (
        "После закрытия новый период обычно со следующего дня. «С сегодня» — закрытый период до вчера, "
        "сегодняшние выручка/расходы только в новом открытом. Если уже был только сегодняшний stub — "
        "чистый старт со завтра (чтобы −сумма не дублировалась). История сохраняется."
    ),
    "Yangi hisobni bugundan boshlash": "Начать новый расчёт с сегодня",
    "Belgilanmasa — ertasi kundan. Belgilansa — yopiq davr kechagacha, "
    "yangi davr bugundan (bugun ikki marta hisoblanmaydi). "
    "Agar ochiq davr allaqachon faqat bugun bo‘lsa — ertadan boshlanadi.": (
        "Если не отмечено — со следующего дня. Если отмечено — закрытый период до вчера, "
        "новый с сегодня (сегодня не считается дважды). "
        "Если открытый период уже только сегодня — старт со завтра."
    ),
    "Davr tugashi": "Конец периода",
    "Izoh": "Комментарий",
    "Hozirgi davr": "Текущий период",
    "Joriy davrni yopadi va sof foydani yangidan boshlaydi.": (
        "Закрывает текущий период и начинает чистую прибыль заново."
    ),
    "Tugash sanasi boshlanishdan oldin bo‘lishi mumkin emas.": (
        "Дата окончания не может быть раньше начала."
    ),
    "Allaqachon ochiq davr bor.": "Уже есть открытый период.",
    "Summa 0 dan katta bo‘lishi kerak.": "Сумма должна быть больше 0.",
    "Rasxod uchun avval filial tanlang.": "Сначала выберите филиал для расхода.",
    "Rasxod qo‘shildi.": "Расход добавлен.",
    "Rasxod yangilandi.": "Расход обновлён.",
    "Rasxodni tahrirlash": "Редактировать расход",
    "Rasxod o‘chirildi.": "Расход удалён.",
    "Bu rasxod boshqa filialga tegishli.": "Этот расход относится к другому филиалу.",
    "E-mehmon mehmondan olingan summa tushumga kirmaydi (o‘tkinchi). Faqat qoplanmagan farq rasxod.": (
        "Сумма E-mehmon, взятая с гостя, в выручку не входит (транзит). Расходом идёт только непокрытая разница."
    ),
    "Buxgalteriya / kassa": "Бухгалтерия / касса",
}


def apply() -> int:
    po = polib.pofile(str(PO_PATH))
    by_id = {e.msgid: e for e in po if not e.obsolete}
    updated = added = 0
    for msgid, msgstr in RU.items():
        entry = by_id.get(msgid)
        if entry is None:
            entry = polib.POEntry(msgid=msgid, msgstr=msgstr)
            po.append(entry)
            by_id[msgid] = entry
            added += 1
            continue
        changed = False
        if entry.msgstr != msgstr:
            entry.msgstr = msgstr
            changed = True
        if "fuzzy" in entry.flags:
            entry.flags = [f for f in entry.flags if f != "fuzzy"]
            changed = True
        if changed:
            updated += 1
    po.save()
    print(f"updated={updated} added={added} total_map={len(RU)}")
    return 0


if __name__ == "__main__":
    sys.exit(apply())
