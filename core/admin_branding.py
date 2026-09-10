"""
Django admin: ikki tilli (uz · ru) nomlar, mantiqiy tartib va bo‘lim tavsiflari.
CoreConfig.ready() orqali ulanadi.
"""

from __future__ import annotations

from django.contrib import admin

APP_ORDER = [
    "properties",
    "guests",
    "bookings",
    "folio",
    "housekeeping",
    "inventory",
    "services",
    "maintenance",
    "finance",
    "hr",
    "reports",
    "widget",
    "tenants",
    "subscriptions",
    "accounts",
    "core",
    "auth",
]

APP_META = {
    "properties": (
        "1. Mehmonxona · Отель",
        "Filial, qavat, xona turi, xonalar va tariflar. / Филиалы, этажи, типы номеров, комнаты и тарифы.",
    ),
    "guests": (
        "2. Mehmonlar · Гости",
        "Mehmonlar, kompaniyalar va hujjatlar. / Гости, компании и документы.",
    ),
    "bookings": (
        "3. Bronlar · Бронирования",
        "Bron, guruh bron, yashash va agent komissiyasi. / Брони, группы, проживание и комиссии.",
    ),
    "folio": (
        "4. Hisob va kassa · Счёт и касса",
        "Folio (hisob), to‘lovlar, kassa smenasi, kompaniya hisob-fakturalari. / Фолио, оплаты, кассовые смены, счета компаний.",
    ),
    "housekeeping": (
        "5. Tozalash · Уборка",
        "Xona holati va tozalash vazifalari. / Статус комнат и задачи хаускипинга.",
    ),
    "inventory": (
        "6. Ombor · Склад",
        "Mahsulot qoldig‘i, harakatlar va minibar. / Остатки, движения и минибар.",
    ),
    "services": (
        "7. Xizmatlar · Услуги",
        "Qo‘shimcha xizmatlar katalogi va buyurtmalar. / Каталог доп. услуг и заказы.",
    ),
    "maintenance": (
        "8. Ta’mir · Ремонт",
        "Texnik nosozliklar va ta’mir arizalari. / Заявки на ремонт и обслуживание.",
    ),
    "finance": (
        "9. Moliya · Финансы",
        "Xarajatlar, yetkazib beruvchilar va foyda taqsimoti. / Расходы, поставщики и распределение прибыли.",
    ),
    "hr": (
        "10. Xodimlar · Персонал",
        "Xodimlar, oylik va to‘lovlar. / Сотрудники, зарплата и выплаты.",
    ),
    "reports": (
        "11. Hisobotlar · Отчёты",
        "Tungi audit (kun yopish) yozuvlari. / Записи ночного аудита.",
    ),
    "widget": (
        "12. Veb-bron · Виджет",
        "Saytga o‘rnatiladigan onlayn bron sozlamalari. / Настройки онлайн-бронирования для сайта.",
    ),
    "tenants": (
        "13. Tashkilot · Организация",
        "Tenant (mehmonxona tashkiloti), a’zolar va valyuta kurslari. / Тенант, участники и курсы валют.",
    ),
    "subscriptions": (
        "14. Obuna · Подписка",
        "Platforma tariflari va obuna holati. / Тарифы платформы и статус подписки.",
    ),
    "accounts": (
        "15. Foydalanuvchilar · Пользователи",
        "Tizimga kirish hisoblari (login). / Учётные записи для входа в систему.",
    ),
    "core": (
        "16. Jurnal · Журнал",
        "Muhim amallar tarixi (activity log). / История важных действий.",
    ),
    "auth": (
        "17. Huquqlar · Права",
        "Guruhlar va ruxsatlar (Django). / Группы и разрешения Django.",
    ),
}

MODEL_LABELS = {
    "accounts.User": ("Foydalanuvchi · Пользователь", "Foydalanuvchilar · Пользователи"),
    "tenants.Tenant": ("Tashkilot · Организация", "Tashkilotlar · Организации"),
    "tenants.TenantMembership": ("A’zo · Участник", "A’zolar · Участники"),
    "tenants.ExchangeRate": ("Valyuta kursi · Курс валюты", "Valyuta kurslari · Курсы валют"),
    "tenants.MembershipProperty": ("Filial ruxsati · Доступ к филиалу", "Filial ruxsatlari · Доступы к филиалам"),
    "subscriptions.Plan": ("Obuna tarifi · Тариф подписки", "Obuna tariflari · Тарифы подписки"),
    "subscriptions.Subscription": ("Obuna · Подписка", "Obunalar · Подписки"),
    "properties.Property": ("Filial · Филиал", "Filiallar · Филиалы"),
    "properties.Floor": ("Qavat · Этаж", "Qavatlar · Этажи"),
    "properties.RoomType": ("Xona turi · Тип номера", "Xona turlari · Типы номеров"),
    "properties.Room": ("Xona · Номер", "Xonalar · Номера"),
    "properties.RatePlan": ("Tarif · Тарифный план", "Tariflar · Тарифные планы"),
    "properties.SeasonRate": ("Mavsumiy narx · Сезонная цена", "Mavsumiy narxlar · Сезонные цены"),
    "properties.PropertySettings": ("Filial sozlamasi · Настройки филиала", "Filial sozlamalari · Настройки филиалов"),
    "guests.Guest": ("Mehmon · Гость", "Mehmonlar · Гости"),
    "guests.Company": ("Kompaniya · Компания", "Kompaniyalar · Компании"),
    "guests.GuestDocument": ("Hujjat · Документ", "Hujjatlar · Документы"),
    "guests.GuestNote": ("Izoh · Заметка", "Izohlar · Заметки"),
    "bookings.Reservation": ("Bron · Бронь", "Bronlar · Брони"),
    "bookings.ReservationGroup": ("Guruh bron · Групповая бронь", "Guruh bronlar · Групповые брони"),
    "bookings.Stay": ("Yashash · Проживание", "Yashashlar · Проживания"),
    "bookings.BookingReferrer": ("Agent / yo‘naltiruvchi · Агент", "Agentlar · Агенты"),
    "bookings.ReferrerCommissionPayment": (
        "Komissiya to‘lovi · Выплата комиссии",
        "Komissiya to‘lovlari · Выплаты комиссий",
    ),
    "bookings.ReservationChangeLog": ("Bron o‘zgarishi · Изменение брони", "Bron o‘zgarishlari · Изменения брони"),
    "folio.Folio": ("Hisob (folio) · Счёт (фолио)", "Hisoblar · Счета"),
    "folio.FolioCharge": ("Yozuv (charge) · Начисление", "Yozuvlar · Начисления"),
    "folio.GuestPayment": ("Mehmon to‘lovi · Оплата гостя", "Mehmon to‘lovlari · Оплаты гостей"),
    "folio.CashShift": ("Kassa smenasi · Кассовая смена", "Kassa smenalari · Кассовые смены"),
    "folio.CashShiftMovement": ("Kassa harakati · Движение кассы", "Kassa harakatlari · Движения кассы"),
    "folio.CompanyInvoice": ("Kompaniya hisobi · Счёт компании", "Kompaniya hisoblari · Счета компаний"),
    "folio.CompanyPayment": ("Kompaniya to‘lovi · Оплата компании", "Kompaniya to‘lovlari · Оплаты компаний"),
    "folio.CompanyInvoiceLine": ("Hisob qatori · Строка счёта", "Hisob qatorlari · Строки счёта"),
    "housekeeping.HousekeepingTask": ("Tozalash vazifasi · Задача уборки", "Tozalash vazifalari · Задачи уборки"),
    "housekeeping.RoomStatusLog": ("Xona holati logi · Лог статуса номера", "Xona holati loglari · Логи статусов"),
    "inventory.StockItem": ("Ombor mahsuloti · Товар склада", "Ombor mahsulotlari · Товары склада"),
    "inventory.StockMovement": ("Ombor harakati · Движение склада", "Ombor harakatlari · Движения склада"),
    "inventory.MinibarSale": ("Minibar sotuvi · Продажа минибара", "Minibar sotuvlari · Продажи минибара"),
    "services.ServiceItem": ("Xizmat · Услуга", "Xizmatlar · Услуги"),
    "services.ServiceOrder": ("Xizmat buyurtmasi · Заказ услуги", "Xizmat buyurtmalari · Заказы услуг"),
    "maintenance.MaintenanceTicket": ("Ta’mir arizasi · Заявка на ремонт", "Ta’mir arizalari · Заявки на ремонт"),
    "finance.ExpenseCategory": ("Xarajat kategoriyasi · Категория расхода", "Xarajat kategoriyalari · Категории расходов"),
    "finance.Vendor": ("Yetkazib beruvchi · Поставщик", "Yetkazib beruvchilar · Поставщики"),
    "finance.Expense": ("Xarajat · Расход", "Xarajatlar · Расходы"),
    "finance.ProfitPartner": ("Foyda sherigi · Партнёр по прибыли", "Foyda sheriklari · Партнёры по прибыли"),
    "finance.ProfitPeriod": ("Foyda davri · Период прибыли", "Foyda davrlari · Периоды прибыли"),
    "finance.ProfitWithdrawal": ("Foyda olish · Вывод прибыли", "Foyda olishlar · Выводы прибыли"),
    "hr.Employee": ("Xodim · Сотрудник", "Xodimlar · Сотрудники"),
    "hr.PayrollPeriod": ("Oylik davri · Зарплатный период", "Oylik davrlari · Зарплатные периоды"),
    "hr.PayrollItem": ("Oylik qatori · Строка зарплаты", "Oylik qatorlari · Строки зарплаты"),
    "hr.SalaryPayment": ("Oylik to‘lovi · Выплата зарплаты", "Oylik to‘lovlari · Выплаты зарплаты"),
    "hr.SalaryAdvance": ("Avans · Аванс", "Avanslar · Авансы"),
    "reports.NightAuditRun": ("Tungi audit · Ночной аудит", "Tungi auditlar · Ночные аудиты"),
    "widget.WidgetConfig": ("Veb-bron sozlamasi · Настройка виджета", "Veb-bron sozlamalari · Настройки виджета"),
    "core.ActivityLog": ("Faoliyat yozuvi · Запись журнала", "Faoliyat yozuvlari · Журнал действий"),
    "auth.Group": ("Guruh · Группа", "Guruhlar · Группы"),
}


def _apply_model_labels() -> None:
    from django.apps import apps

    for key, (singular, plural) in MODEL_LABELS.items():
        try:
            model = apps.get_model(key)
        except LookupError:
            continue
        model._meta.verbose_name = singular
        model._meta.verbose_name_plural = plural


def configure_admin() -> None:
    admin.site.site_header = "Rivoj Hotel PMS — boshqaruv · управление"
    admin.site.site_title = "Rivoj Hotel Admin"
    admin.site.index_title = "Bo‘limlar · Разделы — har bir qism vazifasi bilan"

    _apply_model_labels()

    if getattr(admin.site, "_hotel_admin_branded", False):
        return

    original_get_app_list = admin.site.get_app_list

    def get_app_list(request, app_label=None):
        app_list = original_get_app_list(request, app_label)
        order = {label: i for i, label in enumerate(APP_ORDER)}
        for app in app_list:
            label = app.get("app_label", "")
            if label in APP_META:
                name, description = APP_META[label]
                app["name"] = name
                app["description"] = description
            else:
                app.setdefault("description", "")
        app_list.sort(key=lambda a: order.get(a.get("app_label", ""), 999))
        return app_list

    admin.site.get_app_list = get_app_list
    admin.site._hotel_admin_branded = True
