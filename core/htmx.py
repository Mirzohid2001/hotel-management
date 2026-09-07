import json

from django.http import HttpResponse
from django.utils.html import format_html, format_html_join


def wants_htmx_partial(request, *, target: str | None = None) -> bool:
    """
    True only for intentional fragment requests (search, board date nav, etc.).

    SPA hx-boost and history restore send HX-Request too but need the full page
    so hx-select="#spa-root" can find content. Returning a partial there blanks
    the UI until a hard refresh.
    """
    htmx = getattr(request, "htmx", None)
    if not htmx:
        return False
    if htmx.boosted or htmx.history_restore_request:
        return False
    if target is not None and htmx.target != target:
        return False
    return True


def modal_close_response(*, refresh_board: bool = False, refresh_calendar: bool = False) -> HttpResponse:
    response = HttpResponse(format_html('<div id="modal-root" hx-swap-oob="true"></div>'))
    triggers = {"modalClosed": True}
    if refresh_board:
        triggers["boardRefresh"] = True
    if refresh_calendar:
        triggers["calendarRefresh"] = True
    response["HX-Trigger"] = json.dumps(triggers)
    return response


def select_options_html(queryset, selected_pk, empty_label="---------"):
    options = [format_html('<option value="">{}</option>', empty_label)]
    for obj in queryset:
        if obj.pk == selected_pk:
            options.append(
                format_html('<option value="{}" selected>{}</option>', obj.pk, str(obj))
            )
        else:
            options.append(format_html('<option value="{}">{}</option>', obj.pk, str(obj)))
    return format_html_join("", "{}", ((opt,) for opt in options))


def oob_select_response(
    select_id,
    name,
    queryset,
    selected_pk,
    *,
    required=False,
    empty_label="---------",
    extra_oob="",
):
    """Replace a <select> via HTMX OOB and clear #modal-root."""
    options = select_options_html(queryset, selected_pk, empty_label=empty_label)
    if required:
        select = format_html(
            '<select name="{}" id="{}" required hx-swap-oob="true">{}</select>',
            name,
            select_id,
            options,
        )
    else:
        select = format_html(
            '<select name="{}" id="{}" hx-swap-oob="true">{}</select>',
            name,
            select_id,
            options,
        )
    clear = format_html('<div id="modal-root" hx-swap-oob="true"></div>')
    response = HttpResponse(clear + select + extra_oob)
    response["HX-Trigger"] = json.dumps({"modalClosed": True})
    return response
