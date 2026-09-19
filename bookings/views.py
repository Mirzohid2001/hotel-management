from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods, require_POST

from core.mixins import feature_required, role_required, tenant_login_required
from core.htmx import modal_close_response, oob_select_response, wants_htmx_partial
from core.roles import ACCOUNTING, FLOOR_VIEW, FRONT_OFFICE, STAY_DESK
from folio.models import Folio
from guests.models import Guest
from properties.models import Room, RoomType
from django.utils.html import format_html

from .commission import active_referrers, build_commission_report, record_commission_payment
from .emehmon import build_emehmon_report, build_emehmon_statement
from .forms import (
    BookingReferrerForm,
    BookingReferrerQuickForm,
    CalendarQuickBookForm,
    CommissionPaymentForm,
    GroupBookingForm,
    ReservationAmendForm,
    ReservationForm,
    TransferForm,
    WalkInForm,
    group_room_formset,
    occupant_formset,
    occupant_formset_for_reservation,
    occupant_post_bound,
    occupants_complete,
)
from .models import BookingReferrer, Reservation, ReservationGroup
from .timeline import build_room_timeline, mark_covers_today
from .totals import (
    default_month_bounds,
    parse_iso_date,
    period_booking_summary,
    reservations_in_period,
)
from .services import (
    AvailabilityError,
    DirtyRoomError,
    MissingGuestDocsError,
    apply_amendment,
    assert_room_available,
    cancel_reservation,
    check_in_reservation,
    check_out_reservation,
    confirm_inquiry,
    create_group_booking,
    create_reservation,
    guest_has_id_document,
    mark_no_show,
    transfer_room,
)
from .occupants import (
    MissingOccupantsError,
    occupant_expected_count,
    occupant_missing_slots,
    occupants_qs,
    sync_reservation_occupants,
)


def _active_hotel(request):
    return getattr(request, "active_property", None)


def _redirect_next(request, default_name, **kwargs):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and nxt.startswith("/"):
        return redirect(nxt)
    return redirect(default_name, **kwargs)


def _get_reservation(request, pk):
    return get_object_or_404(
        Reservation.objects.select_related(
            "guest", "room", "room_type", "hotel", "group", "referrer"
        ).prefetch_related("occupants__guest__documents"),
        pk=pk,
        tenant=request.tenant,
    )


@role_required(*FRONT_OFFICE)
def reservation_list(request):
    from django.db.models import Q
    from django.utils import timezone

    status = request.GET.get("status", "")
    q = (request.GET.get("q") or "").strip()
    today = timezone.localdate()
    if "date_from" in request.GET or "date_to" in request.GET:
        date_from = parse_iso_date(request.GET.get("date_from"))
        date_to = parse_iso_date(request.GET.get("date_to"))
    else:
        date_from, date_to = default_month_bounds(today)
    qs = Reservation.objects.filter(tenant=request.tenant).select_related(
        "guest", "room", "hotel", "group"
    )
    hotel = _active_hotel(request)
    if hotel is not None:
        qs = qs.filter(hotel=hotel)
    qs = reservations_in_period(qs, date_from, date_to)
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(
            Q(code__icontains=q)
            | Q(guest__first_name__icontains=q)
            | Q(guest__last_name__icontains=q)
            | Q(guest__phone__icontains=q)
            | Q(occupants__guest__first_name__icontains=q)
            | Q(occupants__guest__last_name__icontains=q)
            | Q(occupants__guest__phone__icontains=q)
            | Q(room__number__icontains=q)
        ).distinct()
    qs = qs.order_by("-check_in", "-pk")
    filter_count = qs.count()
    period_sum = period_booking_summary(request.tenant, qs, status=status)
    base = Reservation.objects.filter(tenant=request.tenant)
    if hotel is not None:
        base = base.filter(hotel=hotel)
    return render(
        request,
        "bookings/reservation_list.html",
        {
            "reservations": qs[:200],
            "status": status,
            "q": q,
            "date_from": date_from.isoformat() if date_from else "",
            "date_to": date_to.isoformat() if date_to else "",
            "statuses": Reservation.Status.choices,
            "filter_count": filter_count,
            "booking_total": period_sum["total"],
            "booking_total_count": period_sum["count"],
            "checked_in_count": base.filter(status=Reservation.Status.CHECKED_IN).count(),
            "confirmed_count": base.filter(status=Reservation.Status.CONFIRMED).count(),
            "arrivals_today": base.filter(
                check_in=today,
                status__in=[Reservation.Status.CONFIRMED, Reservation.Status.CHECKED_IN],
            ).count(),
        },
    )


@role_required(*FRONT_OFFICE)
def inquiry_list(request):
    qs = (
        Reservation.objects.filter(tenant=request.tenant, status=Reservation.Status.INQUIRY)
        .select_related("guest", "room", "hotel")
        .order_by("check_in", "code")
    )
    hotel = _active_hotel(request)
    if hotel is not None:
        qs = qs.filter(hotel=hotel)
    return render(request, "bookings/inquiry_list.html", {"reservations": qs[:200]})


@role_required(*FRONT_OFFICE)
@require_POST
def reservation_confirm(request, pk):
    reservation = _get_reservation(request, pk)
    try:
        confirm_inquiry(reservation, request.user, reason=request.POST.get("reason", ""))
        messages.success(request, _("So‘rov tasdiqlandi."))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return _redirect_next(request, "bookings:detail", pk=pk)


@role_required(*FRONT_OFFICE)
@require_http_methods(["GET", "POST"])
def reservation_create(request):
    hotel = _active_hotel(request)
    if hotel is None:
        messages.error(request, _("Avval mehmonxona yarating yoki tanlang."))
        return redirect("properties:list")
    initial = {}
    if request.method == "GET":
        for key in ("guest", "room_type", "room", "nightly_rate", "currency", "check_in", "check_out", "status"):
            val = request.GET.get(key)
            if val:
                initial[key] = val
        room_id = request.GET.get("room")
        if room_id:
            try:
                room = Room.objects.select_related("room_type").prefetch_related(
                    "sellable_types"
                ).get(
                    pk=int(room_id), tenant=request.tenant, property=hotel, is_active=True
                )
                initial.setdefault("room", room.pk)
                sellable = list(room.sellable_type_list())
                if sellable:
                    initial.setdefault("room_type", sellable[0].pk)
                else:
                    initial.setdefault("room_type", room.room_type_id)
                price_type = sellable[0] if sellable else room.room_type
                if price_type and price_type.base_price:
                    initial.setdefault("nightly_rate", price_type.base_price)
                if price_type and getattr(price_type, "currency", None):
                    initial.setdefault("currency", price_type.currency)
            except (Room.DoesNotExist, ValueError, TypeError):
                pass
        initial.setdefault("currency", "USD")
    form = ReservationForm(
        request.POST or None, tenant=request.tenant, hotel=hotel, initial=initial
    )
    occ_data = request.POST if occupant_post_bound(request.POST) else None
    occupants = occupant_formset(request.tenant, occ_data)
    form_ok = form.is_valid()
    if occupants.is_bound:
        primary = form.cleaned_data.get("guest") if form_ok else None
        if primary is not None:
            occupants.exclude_guest_ids = {primary.pk}
        else:
            raw_guest = (request.POST.get("guest") or "").strip()
            if raw_guest.isdigit():
                occupants.exclude_guest_ids = {int(raw_guest)}
    occupants_ok = (not occupants.is_bound) or occupants.is_valid()
    if request.method == "POST" and form_ok and occupants_ok:
        try:
            reservation = create_reservation(
                tenant=request.tenant,
                user=request.user,
                property_obj=hotel,
                guest=form.cleaned_data["guest"],
                company=form.cleaned_data.get("company"),
                room_type=form.cleaned_data["room_type"],
                room=form.cleaned_data.get("room"),
                nightly_rate=form.cleaned_data.get("nightly_rate"),
                currency=form.cleaned_data.get("currency"),
                check_in=form.cleaned_data["check_in"],
                check_out=form.cleaned_data["check_out"],
                adults=form.cleaned_data["adults"],
                children=form.cleaned_data["children"],
                source=form.cleaned_data["source"],
                notes=form.cleaned_data.get("notes") or "",
                status=form.cleaned_data["status"],
                referrer=form.cleaned_data.get("referrer"),
                commission_percent=form.cleaned_data.get("commission_percent"),
                emehmon_required=False,
                occupants=occupants.cleaned_occupants() if occupants.is_bound else None,
            )
        except (AvailabilityError, ValidationError) as exc:
            messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
        else:
            messages.success(request, _("Bron yaratildi: %(code)s") % {"code": reservation.code})
            return redirect("bookings:detail", pk=reservation.pk)
    return render(
        request,
        "bookings/reservation_form.html",
        {
            "form": form,
            "occupant_formset": occupants,
            "title": _("Yangi bron"),
            "hotel": hotel,
        },
    )


@role_required(*STAY_DESK)
def reservation_detail(request, pk):
    reservation = _get_reservation(request, pk)
    amend_form = ReservationAmendForm(reservation=reservation)
    settings = None
    emehmon_default = Decimal("0")
    emehmon_paid = False
    if reservation.hotel_id:
        from properties.models import PropertySettings

        settings = PropertySettings.objects.filter(property=reservation.hotel).first()
    from folio.services import default_emehmon_fee

    emehmon_default = default_emehmon_fee(reservation)
    folio = getattr(reservation, "folio", None)
    if folio is None:
        from folio.models import Folio

        folio = Folio.objects.filter(reservation=reservation).first()
    if folio is not None:
        from folio.services import emehmon_already_posted

        emehmon_paid = emehmon_already_posted(folio)
    named_occupants = list(occupants_qs(reservation))
    expected_people = occupant_expected_count(reservation)
    missing_adults, missing_children = occupant_missing_slots(reservation)
    occupants_missing = missing_adults + missing_children
    occupant_fs = None
    if (
        reservation.status in {Reservation.Status.CONFIRMED, Reservation.Status.INQUIRY}
        and occupants_missing
    ):
        occupant_fs = occupant_formset(request.tenant, extra=max(occupants_missing, 1))
    missing_id_guests = [
        occ.guest
        for occ in named_occupants
        if not guest_has_id_document(occ.guest)
    ]
    return render(
        request,
        "bookings/reservation_detail.html",
        {
            "reservation": reservation,
            "amend_form": amend_form,
            "logs": reservation.change_logs.select_related("user")[:50],
            "guest_has_id": guest_has_id_document(reservation.guest),
            "require_id": bool(settings and settings.require_id_on_checkin),
            "emehmon_default": emehmon_default,
            "emehmon_paid": emehmon_paid,
            "emehmon_required": reservation.emehmon_required,
            "occupants": named_occupants,
            "occupants_expected": expected_people,
            "occupants_missing": occupants_missing,
            "missing_adults": missing_adults,
            "missing_children": missing_children,
            "occupant_formset": occupant_fs,
            "missing_id_guests": missing_id_guests,
        },
    )


@role_required(*FRONT_OFFICE)
@require_http_methods(["GET", "POST"])
def reservation_amend(request, pk):
    reservation = _get_reservation(request, pk)
    form = ReservationAmendForm(request.POST or None, reservation=reservation)
    occ_data = request.POST if occupant_post_bound(request.POST) else None
    occupants = occupant_formset_for_reservation(reservation, occ_data)
    form_ok = form.is_valid()
    if occupants.is_bound:
        primary = form.cleaned_data.get("guest") if form_ok else reservation.guest
        occupants.exclude_guest_ids = {primary.pk} if primary is not None else {reservation.guest_id}
    occupants_ok = (not occupants.is_bound) or occupants.is_valid()
    if request.method == "POST" and form_ok and occupants_ok:
        data = dict(form.cleaned_data)
        if occupants.is_bound:
            data["occupants"] = occupants.cleaned_occupants()
        try:
            apply_amendment(reservation, request.user, data)
        except (AvailabilityError, ValidationError) as exc:
            messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
        else:
            messages.success(request, _("Bron yangilandi."))
            return redirect("bookings:detail", pk=reservation.pk)
    return render(
        request,
        "bookings/reservation_amend.html",
        {"form": form, "reservation": reservation, "occupant_formset": occupants},
    )


@role_required(*STAY_DESK)
@require_POST
def reservation_check_in(request, pk):
    reservation = _get_reservation(request, pk)
    allow_dirty = request.POST.get("allow_dirty") == "1"
    allow_no_docs = request.POST.get("allow_no_docs") == "1"
    # Doska «Kirish» — forma yo‘q, E-mehmon avtomatik.
    # Batafsil sahifa — checkbox (emehmon_form=1).
    if request.POST.get("emehmon_form") == "1":
        collect_emehmon = request.POST.get("collect_emehmon") == "1"
    else:
        collect_emehmon = True
    emehmon_amount = request.POST.get("emehmon_amount")
    emehmon_method = (request.POST.get("emehmon_method") or "cash").strip()
    try:
        if occupant_post_bound(request.POST):
            occupant_fs = occupant_formset(request.tenant, request.POST)
            occupant_fs.exclude_guest_ids = set(
                occupants_qs(reservation).values_list("guest_id", flat=True)
            )
            if not occupant_fs.is_valid():
                messages.error(
                    request,
                    _("Hamrohlar ma’lumotini tekshiring — ism yoki mavjud mehmonni tanlang."),
                )
                return _redirect_next(request, "bookings:detail", pk=pk)
            existing = [
                {"guest": occ.guest, "kind": occ.kind}
                for occ in occupants_qs(reservation)
                if not occ.is_primary
            ]
            sync_reservation_occupants(
                reservation,
                existing + occupant_fs.cleaned_occupants(),
                primary_guest=reservation.guest,
            )
            reservation.refresh_from_db()
        check_in_reservation(
            reservation,
            request.user,
            allow_dirty=allow_dirty,
            allow_no_docs=allow_no_docs,
        )
        notes = []
        if allow_dirty:
            notes.append(_("kir xona ruxsati"))
        if allow_no_docs:
            notes.append(_("hujjat ruxsati"))
        if notes:
            messages.warning(request, _("Kirish (%(n)s).") % {"n": ", ".join(notes)})
        else:
            messages.success(request, _("Kirish qilindi."))

        # Zayezd paytida E-mehmon: admin tanlaydi
        reservation.refresh_from_db()
        if collect_emehmon:
            from decimal import Decimal, InvalidOperation

            from folio.services import collect_emehmon_fee, default_emehmon_fee, emehmon_unit_rate

            if not reservation.emehmon_required:
                reservation.emehmon_required = True
                reservation.save(update_fields=["emehmon_required", "updated_at"])

            # Asos: kecha × mehmon × tarif. Forma 9000 qoldirsa ham to‘liq olinadi.
            amount = default_emehmon_fee(reservation)
            if emehmon_amount not in (None, ""):
                try:
                    posted = Decimal(str(emehmon_amount).replace(",", "."))
                except (InvalidOperation, ValueError):
                    posted = None
                else:
                    unit = emehmon_unit_rate(reservation.hotel_id)
                    if posted and posted > 0 and posted != unit and posted != amount:
                        amount = posted
            try:
                collect_emehmon_fee(
                    reservation,
                    request.user,
                    amount=amount,
                    method=emehmon_method or "cash",
                )
                messages.success(request, _("E-mehmon to‘lovi qabul qilindi."))
            except ValidationError as exc:
                messages.warning(
                    request,
                    "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
                )
                from django.urls import reverse

                url = reverse("bookings:detail", kwargs={"pk": reservation.pk})
                return redirect(f"{url}?prompt_emehmon=1")
        else:
            if reservation.emehmon_required:
                reservation.emehmon_required = False
                reservation.save(update_fields=["emehmon_required", "updated_at"])
    except DirtyRoomError as exc:
        messages.error(request, "; ".join(exc.messages))
        messages.info(
            request,
            _("Xona kir yoki tozalanmoqda. Tozalang yoki “Kir xona ruxsati” bilan joylashtiring."),
        )
    except MissingOccupantsError as exc:
        messages.error(request, "; ".join(exc.messages))
        messages.info(
            request,
            _("Pastdagi «Xonadagi mehmonlar» ga qolgan odamlarni kiriting, keyin qayta joylashtiring."),
        )
    except MissingGuestDocsError as exc:
        messages.error(request, "; ".join(exc.messages))
        messages.info(
            request,
            _("Hujjat qo‘shing yoki “Hujjat ruxsati” bilan joylashtiring."),
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return _redirect_next(request, "bookings:detail", pk=pk)


@role_required(*STAY_DESK)
@require_http_methods(["GET"])
def checkout_modal(request, pk):
    reservation = _get_reservation(request, pk)
    from folio.services import ensure_folio_for_reservation, ensure_stay_nights_posted, reopen_folio

    folio = ensure_folio_for_reservation(reservation)
    if reservation.status == Reservation.Status.CHECKED_IN:
        if not folio.is_open:
            reopen_folio(folio)
        ensure_stay_nights_posted(reservation, request.user)
        folio.refresh_from_db()
    from_board = request.GET.get("from") == "board"
    return render(
        request,
        "bookings/partials/checkout_modal.html",
        {
            "reservation": reservation,
            "folio": folio,
            "from_board": from_board,
            "can_checkout": folio.balance <= 0,
        },
    )


@role_required(*STAY_DESK)
@require_POST
def reservation_check_out(request, pk):
    reservation = _get_reservation(request, pk)
    from_modal = request.POST.get("from_modal") == "1"
    from_board = request.POST.get("from_board") == "1"
    try:
        check_out_reservation(reservation, request.user)
        messages.success(request, _("Chiqish qilindi."))
        if request.htmx and from_modal:
            folio = reservation.folio
            return render(
                request,
                "bookings/partials/checkout_success.html",
                {
                    "reservation": reservation,
                    "folio": folio,
                    "from_board": from_board,
                },
            )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        if request.htmx and from_modal:
            from folio.services import ensure_folio_for_reservation, ensure_stay_nights_posted, reopen_folio

            folio = ensure_folio_for_reservation(reservation)
            if reservation.status == Reservation.Status.CHECKED_IN:
                if not folio.is_open:
                    reopen_folio(folio)
                try:
                    ensure_stay_nights_posted(reservation, request.user)
                except ValidationError:
                    pass
                folio.refresh_from_db()
            return render(
                request,
                "bookings/partials/checkout_modal.html",
                {
                    "reservation": reservation,
                    "folio": folio,
                    "from_board": from_board,
                    "can_checkout": folio.balance <= 0,
                    "errors": exc.messages,
                },
            )
    return _redirect_next(request, "bookings:detail", pk=pk)


@role_required(*FRONT_OFFICE)
@require_POST
def reservation_cancel(request, pk):
    reservation = _get_reservation(request, pk)
    try:
        cancel_reservation(reservation, request.user, reason=request.POST.get("reason", ""))
        messages.success(request, _("Bron bekor qilindi."))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("bookings:detail", pk=pk)


@role_required(*FRONT_OFFICE)
@require_POST
def reservation_no_show(request, pk):
    reservation = _get_reservation(request, pk)
    try:
        mark_no_show(reservation, request.user, reason=request.POST.get("reason", ""))
        messages.success(
            request,
            _("Kelmagan deb belgilandi. Jarima yo‘q — to‘lov bo‘lsa qaytariladi."),
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("bookings:detail", pk=pk)


@role_required(*FLOOR_VIEW)
def board(request):
    """Bugungi operatsion doska — xona kartochkalari (kirish/chiqish/to‘lov)."""
    day_s = request.GET.get("date")
    day = timezone.localdate()
    if day_s:
        try:
            day = date.fromisoformat(day_s)
        except ValueError:
            pass
    rooms = Room.objects.filter(tenant=request.tenant, is_active=True).select_related(
        "room_type", "property",
    )
    hotel = _active_hotel(request)
    if hotel is not None:
        rooms = rooms.filter(property=hotel)
    active = Reservation.objects.filter(tenant=request.tenant).overlapping(
        day, day + timedelta(days=1)
    ).select_related("guest", "room")
    if hotel is not None:
        active = active.filter(hotel=hotel)
    # Departure morning: guest still checked_in but night interval ended —
    # keep them on the board until Chiqish so staff can check them out.
    still_in = (
        Reservation.objects.filter(tenant=request.tenant)
        .checked_in_on_room()
        .select_related("guest", "room")
    )
    if hotel is not None:
        still_in = still_in.filter(hotel=hotel)
    by_room = {r.room_id: r for r in active if r.room_id}
    for r in still_in:
        if r.room_id:
            by_room[r.room_id] = r
    folio_map = {}
    if by_room:
        for folio in Folio.objects.filter(
            tenant=request.tenant,
            reservation_id__in=[r.pk for r in by_room.values()],
        ):
            folio_map[folio.reservation_id] = folio
    rows = [
        {
            "room": room,
            "reservation": by_room.get(room.pk),
            "folio": folio_map.get(by_room[room.pk].pk) if by_room.get(room.pk) else None,
        }
        for room in rooms
    ]
    board_stats = {"total": len(rows), "vacant": 0, "occupied": 0, "dirty": 0, "ooo": 0}
    for row in rows:
        room = row["room"]
        if room.status == Room.Status.OUT_OF_ORDER:
            board_stats["ooo"] += 1
        elif row["reservation"]:
            board_stats["occupied"] += 1
        elif room.status in (Room.Status.DIRTY, Room.Status.CLEANING):
            board_stats["dirty"] += 1
        else:
            board_stats["vacant"] += 1
    template = (
        "bookings/partials/board_page.html"
        if wants_htmx_partial(request, target="board-page")
        else "bookings/board.html"
    )
    return render(
        request,
        template,
        {
            "rows": rows,
            "day": day,
            "today": timezone.localdate(),
            "prev": day - timedelta(days=1),
            "next": day + timedelta(days=1),
            "board_stats": board_stats,
            "hotel": hotel,
        },
    )


@role_required(*FRONT_OFFICE)
@require_http_methods(["GET", "POST"])
def walk_in(request):
    hotel = _active_hotel(request)
    if hotel is None:
        messages.error(request, _("Avval mehmonxona yarating yoki tanlang."))
        return redirect("properties:list")
    initial = {}
    room_id = request.GET.get("room") or request.POST.get("room")
    if room_id and not request.POST:
        try:
            room = Room.objects.get(
                pk=int(room_id), tenant=request.tenant, property=hotel, is_active=True
            )
            initial["room"] = str(room.pk)
        except (Room.DoesNotExist, ValueError, TypeError):
            pass
    form = WalkInForm(
        request.POST or None, tenant=request.tenant, hotel=hotel, initial=initial
    )
    occ_data = request.POST if occupant_post_bound(request.POST) else None
    occupants = occupant_formset(request.tenant, occ_data)
    occupants_ok = (not occupants.is_bound) or occupants.is_valid()
    if request.method == "POST" and form.is_valid() and occupants_ok:
        data = form.cleaned_data
        companions = occupants.cleaned_occupants() if occupants.is_bound else []
        if not occupants_complete(data["adults"], data.get("children") or 0, companions):
            messages.error(
                request,
                _("Xonadagi barcha kishilarning ismi (va imkon bo‘lsa pasporti) kerak."),
            )
        else:
            today = timezone.localdate()
            guest = Guest.objects.create(
                tenant=request.tenant,
                first_name=data["first_name"],
                last_name=data.get("last_name") or "",
                phone=data.get("phone") or "",
            )
            room = data["room"]
            allow_dirty = request.POST.get("allow_dirty") == "1"
            allow_no_docs = request.POST.get("allow_no_docs") == "1"
            doc_number = (data.get("doc_number") or "").strip()
            try:
                reservation = create_reservation(
                    tenant=request.tenant,
                    user=request.user,
                    property_obj=hotel,
                    guest=guest,
                    room_type=data.get("room_type") or room.room_type,
                    room=room,
                    nightly_rate=data.get("nightly_rate"),
                    currency=data.get("currency"),
                    check_in=today,
                    check_out=today + timedelta(days=data["nights"]),
                    adults=data["adults"],
                    children=data.get("children") or 0,
                    source=Reservation.Source.WALKIN,
                    notes=data.get("notes") or "",
                    referrer=data.get("referrer"),
                    commission_percent=data.get("commission_percent"),
                    emehmon_required=bool(data.get("collect_emehmon")),
                    occupants=companions,
                )
                if doc_number:
                    from guests.models import GuestDocument

                    GuestDocument.objects.create(
                        tenant=request.tenant,
                        guest=guest,
                        doc_type=data.get("doc_type") or GuestDocument.DocType.PASSPORT,
                        number=doc_number,
                    )
                check_in_reservation(
                    reservation,
                    request.user,
                    allow_dirty=allow_dirty,
                    allow_no_docs=allow_no_docs or not doc_number,
                )
                messages.success(request, _("Darhol joylash: %(code)s") % {"code": reservation.code})
                from django.urls import reverse

                url = reverse("bookings:detail", kwargs={"pk": reservation.pk})
                if data.get("collect_emehmon"):
                    from folio.services import collect_emehmon_fee

                    try:
                        collect_emehmon_fee(
                            reservation,
                            request.user,
                            amount=data["emehmon_amount"],
                            method=data.get("emehmon_method") or "cash",
                        )
                        messages.success(request, _("E-mehmon to‘lovi qabul qilindi."))
                        return redirect(f"{url}?prompt_deposit=1")
                    except ValidationError as exc:
                        messages.warning(
                            request,
                            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
                        )
                        return redirect(f"{url}?prompt_emehmon=1&prompt_deposit=1")
                return redirect(f"{url}?prompt_deposit=1")
            except DirtyRoomError as exc:
                messages.error(request, "; ".join(exc.messages))
                messages.info(request, _("Kir xona ruxsati bilan qayta urinib ko‘ring."))
            except MissingOccupantsError as exc:
                messages.error(request, "; ".join(exc.messages))
            except MissingGuestDocsError as exc:
                messages.error(request, "; ".join(exc.messages))
                messages.info(request, _("Hujjat ruxsati yoki pasport raqamini kiriting."))
            except (AvailabilityError, ValidationError) as exc:
                messages.error(
                    request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
                )
    return render(
        request,
        "bookings/walk_in.html",
        {"form": form, "hotel": hotel, "occupant_formset": occupants},
    )


@role_required(*FRONT_OFFICE)
def walk_in_rooms(request):
    """HTMX partial: room + rate fields for active hotel."""
    hotel = _active_hotel(request)
    form = WalkInForm(request.GET or None, tenant=request.tenant, hotel=hotel)
    return render(request, "bookings/partials/walk_in_rooms.html", {"form": form})


@role_required(*FRONT_OFFICE)
@require_http_methods(["GET", "POST"])
def reservation_transfer(request, pk):
    reservation = _get_reservation(request, pk)
    form = TransferForm(request.POST or None, reservation=reservation)
    if request.method == "POST" and form.is_valid():
        try:
            transfer_room(
                reservation,
                request.user,
                form.cleaned_data["room"],
                reason=form.cleaned_data.get("reason") or "",
                update_rate=form.cleaned_data.get("update_rate", True),
            )
            messages.success(request, _("Xona / tur almashtirildi."))
            return redirect("bookings:detail", pk=pk)
        except (AvailabilityError, ValidationError) as exc:
            messages.error(
                request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
            )
    return render(
        request,
        "bookings/transfer.html",
        {
            "form": form,
            "reservation": reservation,
            "room_options": getattr(form, "room_options", []),
        },
    )


def _calendar_view_mode(request) -> str:
    view = (request.GET.get("view") or "").strip().lower()
    if view in {"month", "oy", "1", "30", "31"}:
        return "month"
    if view in {"custom", "range", "davr"}:
        return "custom"
    if request.GET.get("end"):
        return "custom"
    return "14"


def _calendar_period(start: date, view: str, end: date | None = None) -> tuple[date, int, date, date, date]:
    """Return (period_start, days_count, prev_start, next_start, period_end_inclusive)."""
    if view == "month":
        month_start = start.replace(day=1)
        days_count = monthrange(month_start.year, month_start.month)[1]
        if month_start.month == 1:
            prev_start = date(month_start.year - 1, 12, 1)
        else:
            prev_start = date(month_start.year, month_start.month - 1, 1)
        if month_start.month == 12:
            next_start = date(month_start.year + 1, 1, 1)
        else:
            next_start = date(month_start.year, month_start.month + 1, 1)
        period_end = month_start + timedelta(days=days_count - 1)
        return month_start, days_count, prev_start, next_start, period_end

    if view == "custom" and end is not None:
        if end < start:
            start, end = end, start
        days_count = (end - start).days + 1
        days_count = max(1, min(days_count, 62))
        period_end = start + timedelta(days=days_count - 1)
        prev_start = start - timedelta(days=days_count)
        next_start = start + timedelta(days=days_count)
        return start, days_count, prev_start, next_start, period_end

    period_end = start + timedelta(days=13)
    return start, 14, start - timedelta(days=7), start + timedelta(days=7), period_end


@role_required(*FLOOR_VIEW)
def calendar(request):
    today = timezone.localdate()
    start_s = request.GET.get("start")
    end_s = request.GET.get("end")
    start = parse_iso_date(start_s) or today
    custom_end = parse_iso_date(end_s)
    view = _calendar_view_mode(request)
    if view == "custom" and custom_end is None:
        custom_end = start + timedelta(days=13)
    start, days_count, prev_start, next_start, period_end = _calendar_period(
        start, view, custom_end
    )
    hotel = _active_hotel(request)
    timeline = build_room_timeline(
        request.tenant, hotel, start, days_count=days_count
    )
    mark_covers_today(timeline, today)
    period_qs = Reservation.objects.filter(tenant=request.tenant)
    if hotel is not None:
        period_qs = period_qs.filter(hotel=hotel)
    period_qs = reservations_in_period(period_qs, start, period_end)
    period_sum = period_booking_summary(request.tenant, period_qs)
    template = (
        "bookings/partials/calendar_page.html"
        if wants_htmx_partial(request, target="calendar-page")
        else "bookings/calendar.html"
    )
    today_start = today.replace(day=1) if view == "month" else today
    today_end = (
        today_start + timedelta(days=monthrange(today_start.year, today_start.month)[1] - 1)
        if view == "month"
        else today + timedelta(days=days_count - 1)
    )
    return render(
        request,
        template,
        {
            "days": timeline["days"],
            "rows": timeline["rows"],
            "prev": prev_start,
            "next": next_start,
            "prev_end": prev_start + timedelta(days=days_count - 1),
            "next_end": next_start + timedelta(days=days_count - 1),
            "start": timeline["start"],
            "end": timeline["end"],
            "period_end": period_end,
            "today": today,
            "today_start": today_start,
            "today_end": today_end,
            "cal_stats": timeline["stats"],
            "booking_total": period_sum["total"],
            "booking_total_count": period_sum["count"],
            "hotel": hotel,
            "cal_view": view,
            "days_count": days_count,
            "cal_query": (
                f"start={start.isoformat()}&end={period_end.isoformat()}&view=custom"
                if view == "custom"
                else f"start={start.isoformat()}&view={view}"
            ),
        },
    )


@role_required(*FRONT_OFFICE)
@require_http_methods(["GET", "POST"])
def calendar_quick_book(request):
    hotel = _active_hotel(request)
    if hotel is None:
        messages.error(request, _("Avval mehmonxona yarating yoki tanlang."))
        return redirect("bookings:calendar")
    room_id = request.GET.get("room") or request.POST.get("room")
    check_in_s = request.GET.get("check_in") or request.POST.get("check_in")
    check_out_s = request.GET.get("check_out") or request.POST.get("check_out")
    try:
        room = Room.objects.select_related("room_type").prefetch_related("sellable_types").get(
            pk=int(room_id), tenant=request.tenant, property=hotel, is_active=True
        )
        check_in = date.fromisoformat(check_in_s)
        check_out = date.fromisoformat(check_out_s)
    except (Room.DoesNotExist, ValueError, TypeError):
        messages.error(request, _("Noto‘g‘ri xona yoki sana."))
        return redirect("bookings:calendar")
    if check_out <= check_in:
        messages.error(request, _("Chiqish sanasi noto‘g‘ri."))
        return redirect("bookings:calendar")

    initial = {}
    sellable = list(room.sellable_type_list())
    if sellable:
        initial["room_type"] = sellable[0].pk
    elif room.room_type_id:
        initial["room_type"] = room.room_type_id
    price_type = sellable[0] if sellable else room.room_type
    if price_type and price_type.base_price:
        initial["nightly_rate"] = price_type.base_price
    if price_type and getattr(price_type, "currency", None):
        initial["currency"] = price_type.currency
    else:
        initial["currency"] = "USD"

    form = CalendarQuickBookForm(
        request.POST or None,
        tenant=request.tenant,
        hotel=hotel,
        initial=initial,
    )
    if sellable:
        form.fields["room_type"].queryset = RoomType.objects.filter(
            pk__in=[t.pk for t in sellable]
        ).order_by("name")
    elif room.room_type_id:
        form.fields["room_type"].queryset = RoomType.objects.filter(pk=room.room_type_id)

    if request.method == "POST" and form.is_valid():
        sold_as = form.cleaned_data.get("room_type") or room.room_type
        if sold_as and not room.allows_room_type(sold_as):
            messages.error(
                request,
                _("Bu xona «%(t)s» sifatida sotilmaydi.") % {"t": sold_as.name},
            )
        else:
            try:
                reservation = create_reservation(
                    tenant=request.tenant,
                    user=request.user,
                    property_obj=hotel,
                    guest=form.cleaned_data["guest"],
                    room_type=sold_as,
                    room=room,
                    nightly_rate=form.cleaned_data.get("nightly_rate"),
                    currency=form.cleaned_data.get("currency"),
                    check_in=check_in,
                    check_out=check_out,
                    adults=form.cleaned_data["adults"],
                    source=Reservation.Source.PHONE,
                    notes=form.cleaned_data.get("notes") or "",
                    status=form.cleaned_data["status"],
                )
                messages.success(
                    request, _("Bron yaratildi: %(code)s") % {"code": reservation.code}
                )
                if request.htmx:
                    return modal_close_response(refresh_calendar=True)
                return redirect("bookings:detail", pk=reservation.pk)
            except (AvailabilityError, ValidationError) as exc:
                messages.error(
                    request,
                    "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
                )

    return render(
        request,
        "bookings/partials/calendar_quick_form.html",
        {
            "form": form,
            "room": room,
            "check_in": check_in,
            "check_out": check_out,
            "sellable_types": sellable,
        },
    )


@feature_required("company_group")
@role_required(*FRONT_OFFICE)
@require_http_methods(["GET", "POST"])
def group_create(request):
    hotel = _active_hotel(request)
    if hotel is None:
        messages.error(request, _("Avval mehmonxona yarating yoki tanlang."))
        return redirect("properties:list")
    form = GroupBookingForm(request.POST or None, tenant=request.tenant, hotel=hotel)
    formset = group_room_formset(
        request.tenant,
        request.POST if request.method == "POST" else None,
        hotel=hotel,
    )
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        rooms_data = []
        for f in formset:
            if not f.cleaned_data or f.cleaned_data.get("DELETE"):
                continue
            if not f.cleaned_data.get("guest") or not f.cleaned_data.get("room_type"):
                continue
            rooms_data.append(f.cleaned_data)
        try:
            group, _created = create_group_booking(
                tenant=request.tenant,
                user=request.user,
                property_obj=hotel,
                name=form.cleaned_data["name"],
                company=form.cleaned_data.get("company"),
                check_in=form.cleaned_data["check_in"],
                check_out=form.cleaned_data["check_out"],
                notes=form.cleaned_data.get("notes") or "",
                rooms_data=rooms_data,
            )
            messages.success(request, _("Guruh bron: %(code)s") % {"code": group.code})
            return redirect("bookings:group_detail", pk=group.pk)
        except (AvailabilityError, ValidationError) as exc:
            messages.error(
                request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
            )
    return render(
        request,
        "bookings/group_form.html",
        {"form": form, "formset": formset, "title": _("Guruh bron"), "hotel": hotel},
    )


@feature_required("company_group")
@role_required(*FRONT_OFFICE)
def group_list(request):
    groups = ReservationGroup.objects.filter(tenant=request.tenant).select_related(
        "hotel", "company"
    )
    hotel = _active_hotel(request)
    if hotel is not None:
        groups = groups.filter(hotel=hotel)
    groups = groups[:100]
    return render(request, "bookings/group_list.html", {"groups": groups})


@feature_required("company_group")
@role_required(*FRONT_OFFICE)
def group_detail(request, pk):
    group = get_object_or_404(
        ReservationGroup.objects.select_related("hotel", "company"),
        pk=pk,
        tenant=request.tenant,
    )
    reservations = group.reservations.select_related("guest", "room", "room_type")
    return render(
        request,
        "bookings/group_detail.html",
        {"group": group, "reservations": reservations},
    )


@role_required(*FRONT_OFFICE)
def availability_partial(request):
    """HTMX fragment: room availability for selected dates."""
    room_id = request.GET.get("room") or request.POST.get("room")
    check_in_s = request.GET.get("check_in") or request.POST.get("check_in")
    check_out_s = request.GET.get("check_out") or request.POST.get("check_out")
    exclude = request.GET.get("exclude") or request.POST.get("exclude")
    ok = True
    message = _("Sanalarni tanlang")
    try:
        check_in = date.fromisoformat(check_in_s) if check_in_s else None
        check_out = date.fromisoformat(check_out_s) if check_out_s else None
    except ValueError:
        check_in = check_out = None
        ok = False
        message = _("Sana formati noto‘g‘ri")
    if check_in and check_out:
        if check_out <= check_in:
            ok = False
            message = _("Chiqish kirishdan keyin bo‘lishi kerak")
        elif room_id:
            room = Room.objects.filter(pk=room_id, tenant=request.tenant).first()
            if not room:
                ok = False
                message = _("Xona topilmadi")
            else:
                try:
                    assert_room_available(
                        room,
                        check_in,
                        check_out,
                        exclude_reservation_id=int(exclude) if exclude else None,
                    )
                    message = _("Xona bo‘sh · %(nights)s tun") % {
                        "nights": (check_out - check_in).days
                    }
                except AvailabilityError as exc:
                    ok = False
                    message = "; ".join(exc.messages)
        else:
            message = _("Xona tanlanmagan — faqat sanalar OK")
    return render(
        request,
        "bookings/partials/availability.html",
        {"ok": ok, "message": message},
    )


@role_required(*FRONT_OFFICE)
def referrer_list(request):
    qs = BookingReferrer.objects.filter(tenant=request.tenant).order_by("name")
    return render(request, "bookings/referrer_list.html", {"referrers": qs})


@role_required(*FRONT_OFFICE)
@require_http_methods(["GET", "POST"])
def referrer_quick_create(request):
    """HTMX modal create from reservation / walk-in forms."""
    select_id = request.GET.get("select_id") or request.POST.get("select_id") or "id_referrer"
    field_name = request.GET.get("field_name") or request.POST.get("field_name") or "referrer"
    form = BookingReferrerQuickForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        referrer = BookingReferrer.objects.create(
            tenant=request.tenant,
            name=form.cleaned_data["name"],
            phone=form.cleaned_data.get("phone") or "",
            default_commission_percent=form.cleaned_data["default_commission_percent"],
        )
        qs = active_referrers(request.tenant)
        percent = referrer.default_commission_percent
        percent_oob = format_html(
            '<input type="number" name="commission_percent" id="id_commission_percent" '
            'value="{}" step="0.01" min="0" max="100" hx-swap-oob="true">',
            percent,
        )
        return oob_select_response(
            select_id,
            field_name,
            qs,
            referrer.pk,
            empty_label=_("— yo‘q —"),
            extra_oob=percent_oob,
        )
    return render(
        request,
        "bookings/partials/quick_referrer_form.html",
        {
            "form": form,
            "select_id": select_id,
            "field_name": field_name,
            "title": _("Yangi yo‘naltiruvchi"),
        },
    )


@role_required(*FRONT_OFFICE)
@require_http_methods(["GET", "POST"])
def referrer_create(request):
    form = BookingReferrerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.tenant = request.tenant
        obj.save()
        messages.success(request, _("Yo‘naltiruvchi qo‘shildi."))
        nxt = request.GET.get("next") or request.POST.get("next")
        if nxt and nxt.startswith("/"):
            return redirect(nxt)
        return redirect("bookings:referrer_list")
    return render(
        request,
        "bookings/referrer_form.html",
        {"form": form, "title": _("Yangi yo‘naltiruvchi")},
    )


@role_required(*FRONT_OFFICE)
@require_http_methods(["GET", "POST"])
def referrer_edit(request, pk):
    referrer = get_object_or_404(BookingReferrer, pk=pk, tenant=request.tenant)
    form = BookingReferrerForm(request.POST or None, instance=referrer)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Yo‘naltiruvchi yangilandi."))
        return redirect("bookings:referrer_list")
    return render(
        request,
        "bookings/referrer_form.html",
        {"form": form, "title": _("Yo‘naltiruvchini tahrirlash"), "referrer": referrer},
    )


@role_required(*ACCOUNTING)
def commission_report(request):
    today = timezone.localdate()
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
        if month < 1 or month > 12:
            raise ValueError
    except (TypeError, ValueError):
        year, month = today.year, today.month
    report = build_commission_report(request.tenant, year=year, month=month)
    months = [(m, date(2000, m, 1).strftime("%B")) for m in range(1, 13)]
    years = list(range(today.year - 2, today.year + 2))
    return render(
        request,
        "bookings/commission_report.html",
        {
            "report": report,
            "year": year,
            "month": month,
            "months": months,
            "years": years,
            "pay_form": CommissionPaymentForm(
                tenant=request.tenant,
                initial={"paid_on": today},
            ),
        },
    )


@role_required(*ACCOUNTING)
def commission_statement(request, referrer_id):
    """Komissiyachi uchun oylik bayonnoma / sverka cheki (chop etish)."""
    today = timezone.localdate()
    referrer = get_object_or_404(BookingReferrer, pk=referrer_id, tenant=request.tenant)
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
        if month < 1 or month > 12:
            raise ValueError
    except (TypeError, ValueError):
        year, month = today.year, today.month

    report = build_commission_report(request.tenant, year=year, month=month)
    group = next((g for g in report["groups"] if g["referrer"].pk == referrer.pk), None)
    if group is None:
        group = {
            "referrer": referrer,
            "count": 0,
            "base_total": Decimal("0"),
            "commission_total": Decimal("0"),
            "paid_total": Decimal("0"),
            "remaining": Decimal("0"),
            "rows": [],
            "payments": [],
        }
    hotel = getattr(request, "active_property", None)
    return render(
        request,
        "bookings/commission_statement.html",
        {
            "report": report,
            "group": group,
            "year": year,
            "month": month,
            "tenant": request.tenant,
            "hotel": hotel,
            "currency": request.tenant.currency or "UZS",
            "printed_at": timezone.now(),
            "printed_by": request.user.get_username(),
        },
    )


@role_required(*ACCOUNTING)
def emehmon_report(request):
    """Oylik E-mehmon — zayezdda olingan to‘lovlar va farq."""
    today = timezone.localdate()
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
        if month < 1 or month > 12:
            raise ValueError
    except (TypeError, ValueError):
        year, month = today.year, today.month
    hotel = getattr(request, "active_property", None)
    report = build_emehmon_report(
        request.tenant, year=year, month=month, hotel=hotel
    )
    months = [(m, date(2000, m, 1).strftime("%B")) for m in range(1, 13)]
    years = list(range(today.year - 2, today.year + 2))
    return render(
        request,
        "bookings/emehmon_report.html",
        {
            "report": report,
            "year": year,
            "month": month,
            "months": months,
            "years": years,
        },
    )


@role_required(*ACCOUNTING)
def emehmon_statement(request):
    """E-mehmon oylik bayonnoma / topshirish cheki (chop etish)."""
    today = timezone.localdate()
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
        if month < 1 or month > 12:
            raise ValueError
    except (TypeError, ValueError):
        year, month = today.year, today.month
    hotel = getattr(request, "active_property", None)
    statement = build_emehmon_statement(
        request.tenant, year=year, month=month, hotel=hotel
    )
    return render(
        request,
        "bookings/emehmon_statement.html",
        {
            "statement": statement,
            "year": year,
            "month": month,
            "tenant": request.tenant,
            "hotel": hotel,
            "currency": request.tenant.currency or "UZS",
            "printed_at": timezone.now(),
            "printed_by": request.user.get_username(),
        },
    )


@role_required(*ACCOUNTING)
@require_POST
def commission_pay(request, referrer_id):
    today = timezone.localdate()
    referrer = get_object_or_404(BookingReferrer, pk=referrer_id, tenant=request.tenant)
    try:
        year = int(request.POST.get("year", today.year))
        month = int(request.POST.get("month", today.month))
        if month < 1 or month > 12:
            raise ValueError
    except (TypeError, ValueError):
        year, month = today.year, today.month

    form = CommissionPaymentForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        try:
            payment = record_commission_payment(
                request.tenant,
                referrer,
                year=year,
                month=month,
                amount=form.cleaned_data["amount"],
                paid_on=form.cleaned_data.get("paid_on") or today,
                method=form.cleaned_data["method"],
                note=form.cleaned_data.get("note") or "",
                user=request.user,
                currency=form.cleaned_data.get("currency") or request.tenant.currency or "UZS",
            )
            messages.success(
                request,
                _("%(name)s ga %(amount)s %(cur)s to‘landi.")
                % {
                    "name": referrer.name,
                    "amount": payment.amount,
                    "cur": payment.currency,
                },
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    else:
        detail = "; ".join(
            f"{field}: {', '.join(errs)}" for field, errs in form.errors.items()
        )
        messages.error(
            request,
            _("To‘lov saqlanmadi — %(d)s") % {"d": detail}
            if detail
            else _("To‘lov saqlanmadi — maydonlarni tekshiring."),
        )
    return redirect(f"{reverse('bookings:commission_report')}?year={year}&month={month}")
