from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Max, Prefetch
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from apps.boards.automation import AutomationEngine, execute_card_button
from apps.boards.models import (
    AutomationAction,
    AutomationRule,
    Board,
    BoardCard,
    BoardCardAttachment,
    BoardCardLabel,
    BoardCardLink,
    BoardColumn,
    CardButton,
    CardButtonAction,
)
from apps.tenants.models import Membership

from .utils import web_shell_context


@login_required
def boards_page(request):
    if request.active_org is None:
        return redirect("web:onboarding")

    boards = Board.objects.filter(organization=request.active_org).order_by("title")
    context = {
        **web_shell_context(request),
        "boards": boards,
    }
    return render(request, "web/app/boards/page.html", context)


@login_required
def boards_create(request):
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    title = (request.POST.get("title") or "").strip()
    if not title:
        return HttpResponse("", status=400)

    board = Board.objects.create(
        organization=request.active_org,
        title=title,
        created_by=request.user,
    )

    BoardColumn.objects.bulk_create(
        [
            BoardColumn(board=board, title=_("Ideas"), sort_order=0),
            BoardColumn(board=board, title=_("In review"), sort_order=1),
            BoardColumn(board=board, title=_("Planned"), sort_order=2),
            BoardColumn(board=board, title=_("Done"), sort_order=3),
        ]
    )

    return redirect("web:board_detail", board_id=board.id)


@login_required
def board_detail_page(request, board_id):
    if request.active_org is None:
        return redirect("web:onboarding")

    try:
        board = Board.objects.get(id=board_id, organization=request.active_org)
    except Board.DoesNotExist as exc:
        raise Http404() from exc

    columns = (
        BoardColumn.objects.filter(board=board)
        .prefetch_related(
            Prefetch(
                "cards",
                queryset=BoardCard.objects.all().prefetch_related("links", "attachments"),
            )
        )
        .order_by("sort_order", "title")
    )

    context = {
        **web_shell_context(request),
        "board": board,
        "columns": columns,
    }
    return render(request, "web/app/boards/detail.html", context)


@login_required
def board_card_create(request, board_id):
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    try:
        board = Board.objects.get(id=board_id, organization=request.active_org)
    except Board.DoesNotExist as exc:
        raise Http404() from exc

    column_id = (request.POST.get("column_id") or "").strip()
    title = (request.POST.get("title") or "").strip()
    if not column_id or not title:
        return HttpResponse("", status=400)

    column = BoardColumn.objects.filter(id=column_id, board=board).first()
    if column is None:
        return HttpResponse("", status=400)

    max_sort = BoardCard.objects.filter(column=column).aggregate(max=Max("sort_order")).get(
        "max"
    )
    sort_order = int(max_sort or 0) + 1

    card = BoardCard.objects.create(
        column=column,
        title=title,
        sort_order=sort_order,
        created_by=request.user,
    )

    engine = AutomationEngine(triggered_by=request.user)
    engine.trigger_card_created(card)

    return redirect("web:board_detail", board_id=board.id)


@login_required
def board_card_detail(request, card_id):
    if request.active_org is None:
        return redirect("web:onboarding")

    try:
        card = (
            BoardCard.objects.select_related("column__board")
            .prefetch_related("links", "attachments")
            .get(id=card_id, column__board__organization=request.active_org)
        )
    except BoardCard.DoesNotExist as exc:
        raise Http404() from exc

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        description = (request.POST.get("description") or "").strip()
        if not title:
            return HttpResponse("", status=400)

        BoardCard.objects.filter(id=card.id).update(title=title, description=description)
        return redirect("web:board_card_detail", card_id=card.id)

    context = {
        **web_shell_context(request),
        "card": card,
        "board": card.column.board,
    }
    return render(request, "web/app/boards/card_detail.html", context)


@login_required
def board_card_link_create(request, card_id):
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    card = (
        BoardCard.objects.select_related("column__board")
        .filter(id=card_id, column__board__organization=request.active_org)
        .first()
    )
    if card is None:
        raise Http404()

    url = (request.POST.get("url") or "").strip()
    title = (request.POST.get("title") or "").strip()
    if not url:
        return HttpResponse("", status=400)

    BoardCardLink.objects.create(card=card, url=url, title=title)
    return redirect("web:board_card_detail", card_id=card.id)


@login_required
def board_card_attachment_create(request, card_id):
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    card = (
        BoardCard.objects.select_related("column__board")
        .filter(id=card_id, column__board__organization=request.active_org)
        .first()
    )
    if card is None:
        raise Http404()

    f = request.FILES.get("file")
    if f is None:
        return HttpResponse("", status=400)

    BoardCardAttachment.objects.create(card=card, file=f, uploaded_by=request.user)
    return redirect("web:board_card_detail", card_id=card.id)


@login_required
def board_card_move(request, card_id):
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    org = request.active_org
    if not Membership.objects.filter(organization=org, user=request.user).exists():
        raise Http404()

    card = (
        BoardCard.objects.select_related("column__board")
        .filter(id=card_id, column__board__organization=org)
        .first()
    )
    if card is None:
        raise Http404()

    column_id = (request.POST.get("column_id") or "").strip()
    if not column_id:
        return HttpResponse("", status=400)

    target_col = BoardColumn.objects.filter(id=column_id, board=card.column.board).first()
    if target_col is None:
        return HttpResponse("", status=400)

    if target_col.id == card.column_id:
        return redirect("web:board_detail", board_id=card.column.board_id)

    from_column = card.column
    max_sort = BoardCard.objects.filter(column=target_col).aggregate(max=Max("sort_order")).get(
        "max"
    )
    sort_order = int(max_sort or 0) + 1
    BoardCard.objects.filter(id=card.id).update(column=target_col, sort_order=sort_order)

    card.refresh_from_db()
    engine = AutomationEngine(triggered_by=request.user)
    engine.trigger_card_moved(card, from_column=from_column, to_column=target_col)

    return redirect("web:board_detail", board_id=card.column.board_id)


@login_required
def board_automations_page(request, board_id):
    """List all automation rules for a board."""
    if request.active_org is None:
        return redirect("web:onboarding")

    try:
        board = Board.objects.get(id=board_id, organization=request.active_org)
    except Board.DoesNotExist as exc:
        raise Http404() from exc

    rules = (
        AutomationRule.objects.filter(board=board)
        .prefetch_related("actions")
        .order_by("-created_at")
    )
    buttons = (
        CardButton.objects.filter(board=board)
        .prefetch_related("actions")
        .order_by("name")
    )
    labels = BoardCardLabel.objects.filter(board=board).order_by("name")

    context = {
        **web_shell_context(request),
        "board": board,
        "rules": rules,
        "buttons": buttons,
        "labels": labels,
        "trigger_types": AutomationRule.TriggerType.choices,
        "action_types": AutomationAction.ActionType.choices,
    }
    return render(request, "web/app/boards/automations.html", context)


@login_required
def board_automation_rule_create(request, board_id):
    """Create a new automation rule."""
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    try:
        board = Board.objects.get(id=board_id, organization=request.active_org)
    except Board.DoesNotExist as exc:
        raise Http404() from exc

    name = (request.POST.get("name") or "").strip()
    trigger_type = (request.POST.get("trigger_type") or "").strip()
    description = (request.POST.get("description") or "").strip()

    if not name or trigger_type not in dict(AutomationRule.TriggerType.choices):
        return HttpResponse("", status=400)

    trigger_config = {}
    to_column_id = (request.POST.get("to_column_id") or "").strip()
    from_column_id = (request.POST.get("from_column_id") or "").strip()
    label_id = (request.POST.get("trigger_label_id") or "").strip()

    if to_column_id:
        trigger_config["to_column_id"] = to_column_id
    if from_column_id:
        trigger_config["from_column_id"] = from_column_id
    if label_id:
        trigger_config["label_id"] = label_id

    rule = AutomationRule.objects.create(
        board=board,
        name=name,
        description=description,
        trigger_type=trigger_type,
        trigger_config=trigger_config,
        is_active=True,
        created_by=request.user,
    )

    action_types = request.POST.getlist("action_type")
    for i, action_type in enumerate(action_types):
        if action_type not in dict(AutomationAction.ActionType.choices):
            continue

        action_config = {}

        if action_type == AutomationAction.ActionType.MOVE_CARD:
            col_id = (request.POST.get(f"action_column_id_{i}") or "").strip()
            if col_id:
                action_config["column_id"] = col_id
        elif action_type == AutomationAction.ActionType.ADD_LABEL:
            lbl_id = (request.POST.get(f"action_label_id_{i}") or "").strip()
            if lbl_id:
                action_config["label_id"] = lbl_id
        elif action_type == AutomationAction.ActionType.REMOVE_LABEL:
            lbl_id = (request.POST.get(f"action_label_id_{i}") or "").strip()
            if lbl_id:
                action_config["label_id"] = lbl_id
        elif action_type == AutomationAction.ActionType.SET_DUE_DATE:
            days = (request.POST.get(f"action_days_offset_{i}") or "3").strip()
            try:
                action_config["days_offset"] = int(days)
            except ValueError:
                action_config["days_offset"] = 3
        elif action_type == AutomationAction.ActionType.ASSIGN_USER:
            user_id = (request.POST.get(f"action_user_id_{i}") or "").strip()
            assign_triggered = request.POST.get(f"action_assign_triggered_{i}") == "on"
            if assign_triggered:
                action_config["assign_triggered_by"] = True
            elif user_id:
                action_config["user_id"] = user_id

        AutomationAction.objects.create(
            rule=rule,
            action_type=action_type,
            action_config=action_config,
            sort_order=i,
        )

    messages.success(request, _("Automation rule created"))
    return redirect("web:board_automations", board_id=board.id)


@login_required
def board_automation_rule_toggle(request, rule_id):
    """Toggle an automation rule on/off."""
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    rule = (
        AutomationRule.objects.select_related("board")
        .filter(id=rule_id, board__organization=request.active_org)
        .first()
    )
    if rule is None:
        raise Http404()

    rule.is_active = not rule.is_active
    rule.save(update_fields=["is_active"])

    return redirect("web:board_automations", board_id=rule.board_id)


@login_required
def board_automation_rule_delete(request, rule_id):
    """Delete an automation rule."""
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    rule = (
        AutomationRule.objects.select_related("board")
        .filter(id=rule_id, board__organization=request.active_org)
        .first()
    )
    if rule is None:
        raise Http404()

    board_id = rule.board_id
    rule.delete()

    messages.success(request, _("Automation rule deleted"))
    return redirect("web:board_automations", board_id=board_id)


@login_required
def board_card_button_create(request, board_id):
    """Create a new card button."""
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    try:
        board = Board.objects.get(id=board_id, organization=request.active_org)
    except Board.DoesNotExist as exc:
        raise Http404() from exc

    name = (request.POST.get("name") or "").strip()
    icon = (request.POST.get("icon") or "play").strip()
    color = (request.POST.get("color") or "indigo").strip()
    show_when_has_label_id = (request.POST.get("show_when_has_label") or "").strip()
    hide_when_has_label_id = (request.POST.get("hide_when_has_label") or "").strip()

    if not name:
        return HttpResponse("", status=400)

    button = CardButton.objects.create(
        board=board,
        name=name,
        icon=icon,
        color=color,
        is_active=True,
        created_by=request.user,
    )

    if show_when_has_label_id:
        button.show_when_has_label_id = show_when_has_label_id
    if hide_when_has_label_id:
        button.hide_when_has_label_id = hide_when_has_label_id
    if show_when_has_label_id or hide_when_has_label_id:
        button.save()

    action_types = request.POST.getlist("action_type")
    for i, action_type in enumerate(action_types):
        if action_type not in dict(AutomationAction.ActionType.choices):
            continue

        action_config = {}

        if action_type == AutomationAction.ActionType.MOVE_CARD:
            col_id = (request.POST.get(f"action_column_id_{i}") or "").strip()
            if col_id:
                action_config["column_id"] = col_id
        elif action_type == AutomationAction.ActionType.ADD_LABEL:
            lbl_id = (request.POST.get(f"action_label_id_{i}") or "").strip()
            if lbl_id:
                action_config["label_id"] = lbl_id
        elif action_type == AutomationAction.ActionType.REMOVE_LABEL:
            lbl_id = (request.POST.get(f"action_label_id_{i}") or "").strip()
            if lbl_id:
                action_config["label_id"] = lbl_id
        elif action_type == AutomationAction.ActionType.SET_DUE_DATE:
            days = (request.POST.get(f"action_days_offset_{i}") or "3").strip()
            try:
                action_config["days_offset"] = int(days)
            except ValueError:
                action_config["days_offset"] = 3

        CardButtonAction.objects.create(
            button=button,
            action_type=action_type,
            action_config=action_config,
            sort_order=i,
        )

    messages.success(request, _("Card button created"))
    return redirect("web:board_automations", board_id=board.id)


@login_required
def board_card_button_delete(request, button_id):
    """Delete a card button."""
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    button = (
        CardButton.objects.select_related("board")
        .filter(id=button_id, board__organization=request.active_org)
        .first()
    )
    if button is None:
        raise Http404()

    board_id = button.board_id
    button.delete()

    messages.success(request, _("Card button deleted"))
    return redirect("web:board_automations", board_id=board_id)


@login_required
def board_card_button_execute(request, card_id, button_id):
    """Execute a card button on a specific card."""
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    card = (
        BoardCard.objects.select_related("column__board")
        .filter(id=card_id, column__board__organization=request.active_org)
        .first()
    )
    if card is None:
        raise Http404()

    button = CardButton.objects.filter(
        id=button_id,
        board=card.column.board,
        is_active=True,
    ).first()
    if button is None:
        raise Http404()

    success = execute_card_button(str(button.id), card, request.user)

    if success:
        messages.success(request, _("Button action executed"))
    else:
        messages.error(request, _("Button action failed"))

    return redirect("web:board_card_detail", card_id=card.id)


@login_required
def board_label_create(request, board_id):
    """Create a new label for a board."""
    if request.active_org is None:
        return redirect("web:onboarding")
    if request.method != "POST":
        raise Http404()

    try:
        board = Board.objects.get(id=board_id, organization=request.active_org)
    except Board.DoesNotExist as exc:
        raise Http404() from exc

    name = (request.POST.get("name") or "").strip()
    color = (request.POST.get("color") or "gray").strip()

    if not name:
        return HttpResponse("", status=400)

    BoardCardLabel.objects.get_or_create(
        board=board,
        name=name,
        defaults={"color": color},
    )

    return redirect("web:board_automations", board_id=board.id)
