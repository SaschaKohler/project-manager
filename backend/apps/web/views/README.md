# Web Views Refactoring

## Struktur

Die Views sind jetzt nach Features organisiert:

```
views/
├── __init__.py          # Zentrale Registry, exportiert alle Views
├── utils.py             # Shared Helper-Funktionen
├── auth.py              # Authentication & Registration
├── dashboard.py         # Dashboard & Calendar
├── tasks.py             # Task Management (teilweise migriert)
├── projects.py          # Project Management
├── boards.py            # Board Management (TODO)
├── team.py              # Team & Invitations (TODO)
└── automations.py       # Automation Rules (TODO)
```

## Migration Status

### ✅ Abgeschlossen

- **utils.py**: Alle Helper-Funktionen migriert
  - `can_edit_task()`, `require_task_edit_permission()`
  - `humanize_seconds()`, `task_event_style()`
  - `web_shell_context()`, `get_org_member_user()`

- **auth.py**: Authentication Views
  - `register()`, `healthz()`

- **dashboard.py**: Dashboard & Calendar
  - `app_home()`, `calendar_page()`, `calendar_events()`

- **projects.py**: Project Management
  - `projects_page()`, `projects_create()`, `projects_complete()`
  - `project_calendar_page()`, `project_calendar_events()`

- **tasks.py**: Task Management (Basis)
  - `tasks_page()` - Hauptansicht mit Kanban Board
  - `tasks_create()` - Task-Erstellung mit Validierung

### 🚧 Noch zu migrieren

**tasks.py** - Fehlende Views:
- `tasks_detail()` - Task-Details anzeigen/bearbeiten
- `tasks_delete()` - Task archivieren
- `tasks_time_entries()` - Zeiteinträge anzeigen
- `tasks_assign()` - Task zuweisen
- `tasks_schedule()` / `tasks_unschedule()` - Scheduling
- `tasks_title()` - Titel bearbeiten
- `tasks_move()` - Task verschieben (Drag & Drop)
- `tasks_toggle()` - Status togglen (Done/Undo)
- `tasks_timer()` - Timer starten/stoppen
- `tasks_refresh()` - Task-Card neu laden
- `task_label_*()` - Label-Management
- `task_button_*()` - Button-Management
- `task_automations_*()` - Automation-Management
- `tasks_archive()`, `tasks_restore()`, `tasks_delete_permanent()`

**boards.py** - Alle Board-Views:
- `boards_page()`, `boards_create()`
- `board_detail_page()`, `board_card_create()`
- `board_card_detail()`, `board_card_move()`
- `board_card_link_create()`, `board_card_attachment_create()`
- `board_automations_page()`, `board_automation_rule_*()`
- `board_card_button_*()`, `board_label_create()`

**team.py** - Team-Views:
- `team_page()`, `team_invite()`, `invite_accept()`

**automations.py** - Automation-Views:
- Alle automation-bezogenen Views aus boards und tasks

## Nächste Schritte

### Phase 1: Vollständige Task-Migration
```bash
# 1. Kopiere alle task_* Views aus views.py nach tasks.py
# 2. Passe Imports an (verwende relative Imports aus .utils)
# 3. Teste alle Task-Endpoints
# 4. Update __init__.py mit allen Task-Exports
```

### Phase 2: Board-Migration
```bash
# 1. Erstelle boards.py
# 2. Kopiere alle board_* Views
# 3. Teste alle Board-Endpoints
# 4. Update __init__.py
```

### Phase 3: Cleanup
```bash
# 1. Wenn alle Views migriert sind, lösche alte views.py
# 2. Behalte nur views/__init__.py
# 3. Verifiziere alle URLs funktionieren
```

## Verwendung

### Alte Imports (funktionieren weiterhin):
```python
from apps.web.views import tasks_page, tasks_create
```

### Neue Imports (empfohlen):
```python
from apps.web.views.tasks import tasks_page, tasks_create
from apps.web.views.utils import can_edit_task, humanize_seconds
```

### In urls.py:
```python
# Beide Varianten funktionieren:
from apps.web.views import tasks_page
# oder
from apps.web.views.tasks import tasks_page

urlpatterns = [
    path('tasks/', tasks_page, name='tasks'),
]
```

## Vorteile

1. **Übersichtlichkeit**: Jede Datei < 300 Zeilen
2. **Wartbarkeit**: Änderungen an Tasks betreffen nur tasks.py
3. **Testbarkeit**: Kleinere Module = einfachere Tests
4. **Onboarding**: Neue Entwickler finden Code schneller
5. **Git**: Weniger Merge-Konflikte

## Testing

Nach jeder Migration:

```bash
# 1. Server starten
python manage.py runserver

# 2. Teste alle migrierten Endpoints manuell
# 3. Prüfe Browser Console auf Fehler
# 4. Verifiziere HTMX-Requests funktionieren
```

## Rollback

Falls Probleme auftreten:

1. Die alte `views.py` ist noch vorhanden
2. Ändere Imports in `urls.py` zurück zur alten Datei
3. Lösche `views/` Verzeichnis
4. Restart Server

## Pattern für neue Views

```python
# In views/tasks.py

@login_required
def task_example(request, task_id):
    """Docstring explaining what this view does."""
    # 1. Check authentication
    if request.active_org is None:
        return redirect("web:onboarding")
    
    # 2. Get org and validate
    org = request.active_org
    
    # 3. Get object or 404
    try:
        task = Task.objects.get(id=task_id, project__organization=org)
    except Task.DoesNotExist as exc:
        raise Http404() from exc
    
    # 4. Check permissions
    permission_response = require_task_edit_permission(request, task)
    if permission_response is not None:
        return permission_response
    
    # 5. Perform operation
    # ...
    
    # 6. Return response (HTMX or redirect)
    if request.headers.get("HX-Request") == "true":
        return render(request, "template.html", context)
    return redirect("web:tasks")
```

## Automation Engine Refactoring

Siehe `automation_refactoring.md` für Details zur Verbesserung der Automation-Engine mit:
- Action Registry Pattern
- Trigger Filter Klassen
- Gemeinsame Basis-Klasse für Board & Task Automation
