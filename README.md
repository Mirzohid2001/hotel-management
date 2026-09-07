# Hotel SaaS PMS

Django 5 + HTMX multi-tenant mehmonxona boshqaruvi (Property Management System).

## Tezkor start

```bash
cd "hotel management"
source venv/bin/activate
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

- App: http://127.0.0.1:8000/
- Demo: `demo` / `demo12345`
- Admin (obuna qo‘lda): `/admin/`

## Testlar

```bash
python manage.py test
```

## Tarjima (UZ / RU)

```bash
python manage.py makemessages -l uz -l ru
python manage.py compilemessages
```

## Production (ishga tushirish)

1. `.env` ni `.env.example` dan ko‘chirib to‘ldiring:
   - `DEBUG=False`
   - kuchli `SECRET_KEY`
   - real `ALLOWED_HOSTS` va `WIDGET_BASE_URL=https://...`
   - ixtiyoriy: Postgres `DATABASE_URL`
2. Migratsiya va static:
   ```bash
   python manage.py migrate
   python manage.py collectstatic --noinput
   python manage.py compilemessages
   python manage.py check --deploy
   ```
3. HTTPS orqali ishga tushiring (nginx/caddy + gunicorn/uwsgi).
4. `DEBUG=False` da SSL redirect, secure cookie va HSTS avtomatik yoqiladi.

## Onlayn bron (veb-sayt widget)

Har bir tenant uchun Django Admin → **Tenants → Tenant → Veb-bron widget**:
- Domenlar (`aida-hotel.uz`)
- Embed kod (iframe)
- API: `/widget/api/<slug>/availability/` va `/book/`

```bash
python manage.py seed_aida_hotel
```

`.env`: `WIDGET_BASE_URL=https://pms-domeningiz.uz`

```html
<iframe src="https://pms-domeningiz.uz/widget/aida-hotel/" ...></iframe>
```

## Modullar

- SaaS: tenant, Free/Basic/Pro, staff rollar
- Property / xonalar / tarif / mavsum
- Bronlar: board, calendar, walk-in, amend, transfer
- Folio, PDF hisob-faktura, kassa, city ledger
- Housekeeping, inventar, rasxod, HR/oylik
- Dashboard, P&L, night audit, CSV
