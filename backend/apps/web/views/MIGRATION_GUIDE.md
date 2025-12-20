# Views Refactoring - Migrations-Anleitung

## Übersicht

Diese Anleitung hilft dir, die restlichen Views schrittweise zu migrieren.

## Aktueller Status

✅ **Fertig migriert:**
- `utils.py` - Alle Helper-Funktionen
- `auth.py` - Register, healthz
- `dashboard.py` - Dashboard, Calendar
- `projects.py` - Projekt-Management
- `tasks.py` - tasks_page, tasks_create (Basis)

🚧 **Noch zu tun:**
- Restliche Task-Views (~20 Views)
- Alle Board-Views (~15 Views)
- Team-Views (~3 Views)
- Automation-Views (~5 Views)

## Schritt-für-Schritt Migration

### Schritt 1: Backup erstellen

```bash
cd backend/apps/web
cp views.py views_backup.py
```

### Schritt 2: URLs prüfen

Öffne `urls.py` und notiere alle verwendeten View-Namen:

```bash
grep "views\." apps/web/urls.py | sort | uniq
```

### Schritt 3: Eine View migrieren

**Beispiel: tasks_detail migrieren**

1. **Finde die View in views.py:**
```bash
grep -n "def tasks_detail" views.py
```

2. **Kopiere die komplette Funktion nach tasks.py:**
```python
# In views/tasks.py hinzufügen:

@login_required
def tasks_detail(request, task_id):
    """Display and edit task details."""
    if request.active_org is None:
        return redirect("web:onboarding")
    
    # ... rest of the function
```

3. **Passe Imports an:**
```python
# Ersetze in der kopierten Funktion:
_can_edit_task       → can_edit_task
_require_task_edit_permission → require_task_edit_permission
_humanize_seconds    → humanize_seconds
_web_shell_context   → web_shell_context
```

4. **Füge zu __init__.py hinzu:**
```python
# In views/__init__.py:
from .tasks import (
    tasks_create,
    tasks_detail,  # NEU
    tasks_page,
)

__all__ = [
    # ...
    "tasks_detail",  # NEU
]
```

5. **Teste die View:**
```bash
python manage.py runserver
# Öffne Browser und teste die URL
```

6. **Wenn erfolgreich, markiere in views.py:**
```python
# In views.py (alte Datei):
# MIGRATED TO views/tasks.py
# def tasks_detail(request, task_id):
#     ...
```

### Schritt 4: Alle Task-Views migrieren

Wiederhole Schritt 3 für jede Task-View:

```python
# Reihenfolge (von einfach zu komplex):
1. tasks_delete
2. tasks_time_entries
3. tasks_assign
4. tasks_schedule / tasks_unschedule
5. tasks_title
6. tasks_move
7. tasks_toggle
8. tasks_timer
9. tasks_refresh
10. task_label_create / task_label_assign / task_label_remove
11. task_button_execute
12. task_automations_page
13. task_automation_rule_create / toggle / delete
14. task_button_create / delete
15. tasks_archive / tasks_restore / tasks_delete_permanent
```

### Schritt 5: Board-Views migrieren

Erstelle `views/boards.py`:

```python
"""
Board and card management views.
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
# ... imports

from .utils import web_shell_context

@login_required
def boards_page(request):
    """List all boards."""
    # ... implementation
```

Migriere in dieser Reihenfolge:
1. boards_page, boards_create
2. board_detail_page
3. board_card_create, board_card_detail
4. board_card_move
5. board_card_link_create, board_card_attachment_create
6. board_automations_page
7. board_automation_rule_* (create, toggle, delete)
8. board_card_button_* (create, delete, execute)
9. board_label_create

### Schritt 6: Team-Views migrieren

Erstelle `views/team.py`:

```python
"""
Team and invitation management views.
"""
from django.contrib.auth.decorators import login_required
# ... imports

@login_required
def team_page(request):
    """Team members overview."""
    # ... implementation
```

Migriere:
1. team_page
2. team_invite
3. invite_accept

### Schritt 7: Finale Bereinigung

Wenn ALLE Views migriert sind:

```bash
# 1. Prüfe, dass views.py nur noch auskommentierte Funktionen hat
grep "^def " views.py

# 2. Wenn leer, lösche views.py
rm views.py

# 3. Behalte nur views/__init__.py
ls -la views/

# 4. Teste ALLE Endpoints
python manage.py test apps.web
```

## Testing-Checkliste

Nach jeder Migration:

- [ ] Server startet ohne Fehler
- [ ] URL lädt ohne 500 Error
- [ ] HTMX-Requests funktionieren
- [ ] Formulare können abgeschickt werden
- [ ] Redirects funktionieren
- [ ] Permissions werden geprüft
- [ ] Browser Console zeigt keine JS-Fehler

## Häufige Probleme

### Problem: ImportError

```python
# Fehler:
ImportError: cannot import name 'tasks_detail' from 'apps.web.views'

# Lösung:
# Füge tasks_detail zu views/__init__.py hinzu
```

### Problem: Circular Import

```python
# Fehler:
ImportError: cannot import name 'X' from partially initialized module

# Lösung:
# Verschiebe Import innerhalb der Funktion:
def my_view(request):
    from apps.projects.models import Task  # Hier importieren
    # ...
```

### Problem: Helper-Funktion nicht gefunden

```python
# Fehler:
NameError: name '_humanize_seconds' is not defined

# Lösung:
# Ersetze durch:
from .utils import humanize_seconds
# Und verwende: humanize_seconds(...)
```

## Rollback-Plan

Falls kritische Probleme auftreten:

```bash
# 1. Stoppe Server
# 2. Lösche views/ Verzeichnis
rm -rf views/

# 3. Stelle Backup wieder her
mv views_backup.py views.py

# 4. Starte Server neu
python manage.py runserver
```

## Best Practices

1. **Eine View nach der anderen:** Nicht mehrere gleichzeitig migrieren
2. **Sofort testen:** Nach jeder Migration testen
3. **Commit nach jeder View:** Git-Commits für einfaches Rollback
4. **Dokumentiere Probleme:** Notiere unerwartete Issues
5. **Pair Programming:** Bei komplexen Views zu zweit arbeiten

## Git Workflow

```bash
# Für jede migrierte View:
git add apps/web/views/tasks.py
git add apps/web/views/__init__.py
git commit -m "refactor: migrate tasks_detail to modular structure"

# Bei Problemen:
git revert HEAD
```

## Nächste Schritte

1. Starte mit den einfachen Task-Views (delete, assign)
2. Arbeite dich zu komplexeren Views vor (timer, toggle)
3. Migriere dann Board-Views
4. Zum Schluss Team und Automation Views
5. Finale Bereinigung und Tests

## Fragen?

Bei Problemen:
1. Prüfe README.md für Pattern-Beispiele
2. Vergleiche mit bereits migrierten Views
3. Teste in isolierter Umgebung
4. Dokumentiere Lösung für zukünftige Referenz
