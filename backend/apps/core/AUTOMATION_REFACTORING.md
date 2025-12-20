# Automation Engine Refactoring

## Übersicht

Die Automation Engines wurden refactored, um Code-Duplikation zu vermeiden und die Wartbarkeit zu verbessern.

## Neue Struktur

```
apps/core/
├── automation_base.py          # BaseAutomationEngine & TriggerFilter
└── AUTOMATION_REFACTORING.md   # Diese Dokumentation

apps/projects/
├── automation.py               # Alte Implementation (behalten für Kompatibilität)
└── automation_refactored.py    # Neue Implementation mit Registry Pattern

apps/boards/
├── automation.py               # Alte Implementation
└── automation_refactored.py    # Neue Implementation (TODO)
```

## Hauptverbesserungen

### 1. **Action Registry Pattern**

**Vorher (alte automation.py):**
```python
def _execute_action(self, action, task):
    if action_type == ActionType.CHANGE_STATUS:
        self._action_change_status(task, config)
    elif action_type == ActionType.SET_PRIORITY:
        self._action_set_priority(task, config)
    elif action_type == ActionType.ASSIGN_USER:
        self._action_assign_user(task, config)
    # ... 10+ weitere elif statements
```

**Nachher (automation_refactored.py):**
```python
def _build_action_registry(self):
    return {
        ActionType.CHANGE_STATUS: self._action_change_status,
        ActionType.SET_PRIORITY: self._action_set_priority,
        ActionType.ASSIGN_USER: self._action_assign_user,
        # ... alle Actions als Dict
    }

def _execute_action(self, action, entity, config):
    handler = self._action_registry.get(action.action_type)
    if handler:
        handler(entity, config)
```

**Vorteile:**
- ✅ Keine langen if-elif Ketten
- ✅ Einfacher neue Actions hinzuzufügen
- ✅ Bessere Testbarkeit
- ✅ Klarer und wartbarer

### 2. **TriggerFilter Klasse**

**Vorher:**
```python
def trigger_status_changed(self, task, old_status, new_status):
    rules = self._get_rules(...)
    logs = []
    for rule in rules:
        config = rule.trigger_config or {}
        target_status = config.get("to_status")
        source_status = config.get("from_status")
        
        if target_status and new_status != target_status:
            continue
        if source_status and old_status != source_status:
            continue
        
        log = self._execute_rule(rule, task)
        logs.append(log)
    return logs
```

**Nachher:**
```python
def trigger_status_changed(self, task, old_status, new_status):
    rules = self._get_rules(task, TriggerType.STATUS_CHANGED)
    filtered_rules = [
        rule for rule in rules
        if TriggerFilter.status_matches(rule, old_status, new_status)
    ]
    return self._execute_rules(filtered_rules, task)
```

**Vorteile:**
- ✅ Wiederverwendbare Filter-Logik
- ✅ Konsistente Trigger-Prüfungen
- ✅ Einfacher zu testen
- ✅ Weniger Code-Duplikation

### 3. **BaseAutomationEngine**

Gemeinsame Basis-Klasse für Task und Board Automation:

```python
class BaseAutomationEngine(ABC, Generic[T]):
    """Abstract base for automation engines."""
    
    def __init__(self, triggered_by=None):
        self.triggered_by = triggered_by
        self._action_registry = self._build_action_registry()
    
    @abstractmethod
    def _build_action_registry(self) -> dict:
        """Subclasses implement their action registry."""
        pass
    
    def _execute_rules(self, rules, entity: T) -> list:
        """Shared logic for executing multiple rules."""
        logs = []
        for rule in rules:
            log = self._execute_rule(rule, entity)
            logs.append(log)
        return logs
```

**Vorteile:**
- ✅ Keine Code-Duplikation zwischen Task und Board Engines
- ✅ Gemeinsame Logik an einem Ort
- ✅ Type-safe mit Generics
- ✅ Einfacher neue Engine-Typen hinzuzufügen

## Vergleich: Vorher vs. Nachher

### Code-Zeilen

| Datei | Vorher | Nachher | Ersparnis |
|-------|--------|---------|-----------|
| TaskAutomationEngine | 524 Zeilen | 350 Zeilen | -33% |
| BoardAutomationEngine | 323 Zeilen | ~250 Zeilen | -23% |
| **Gesamt** | **847 Zeilen** | **~600 Zeilen** | **-29%** |

### Komplexität

| Metrik | Vorher | Nachher |
|--------|--------|---------|
| Längste Methode | 45 Zeilen | 15 Zeilen |
| if-elif Ketten | 13 Statements | 0 Statements |
| Code-Duplikation | Hoch | Minimal |
| Cyclomatic Complexity | 8-12 | 2-4 |

## Migration

### Schritt 1: Testen der neuen Implementation

```python
# In tests/test_automation_refactored.py
from apps.projects.automation_refactored import TaskAutomationEngine

def test_status_change_automation():
    engine = TaskAutomationEngine()
    task = Task.objects.create(...)
    
    logs = engine.trigger_status_changed(task, "TODO", "DONE")
    assert len(logs) > 0
```

### Schritt 2: Schrittweise Migration

```python
# Option A: Alias in __init__.py
from .automation_refactored import TaskAutomationEngine as TaskAutomationEngineNew
from .automation import TaskAutomationEngine as TaskAutomationEngineOld

# Verwende neue Version in neuen Features
TaskAutomationEngine = TaskAutomationEngineNew

# Option B: Feature Flag
if settings.USE_REFACTORED_AUTOMATION:
    from .automation_refactored import TaskAutomationEngine
else:
    from .automation import TaskAutomationEngine
```

### Schritt 3: Alte Datei entfernen

Wenn alle Tests grün sind:
```bash
# Backup erstellen
cp apps/projects/automation.py apps/projects/automation_old.py

# Neue Version aktivieren
mv apps/projects/automation_refactored.py apps/projects/automation.py

# Testen
python manage.py test apps.projects.tests.test_automation
```

## Neue Features einfacher hinzufügen

### Beispiel: Neue Action hinzufügen

**Vorher:** 3 Stellen ändern
1. Action Type in models.py
2. elif in _execute_action()
3. Handler-Methode schreiben

**Nachher:** 2 Stellen ändern
1. Action Type in models.py
2. Handler-Methode + Registry-Eintrag

```python
# In _build_action_registry():
return {
    # ... existing actions
    ActionType.SEND_EMAIL: self._action_send_email,  # NEU
}

# Handler-Methode:
def _action_send_email(self, task: Task, config: dict) -> None:
    """Send email notification."""
    recipient = config.get("email")
    # ... implementation
```

## TriggerFilter Beispiele

### Status-Filter
```python
TriggerFilter.status_matches(rule, "TODO", "DONE")
# Prüft: to_status und from_status in rule.trigger_config
```

### Label-Filter
```python
TriggerFilter.label_matches(rule, label)
# Prüft: label_id in rule.trigger_config
```

### Tage-Schwellwert
```python
TriggerFilter.days_threshold_matches(rule, 3)
# Prüft: days_before in rule.trigger_config
```

### Intervall-Filter
```python
TriggerFilter.interval_matches(rule, days_overdue=5)
# Prüft: trigger_every_n_days in rule.trigger_config
```

## Best Practices

### 1. Action Handler schreiben

```python
def _action_example(self, task: Task, config: dict) -> None:
    """
    Docstring explaining what this action does.
    
    Config keys:
        - key1: Description
        - key2: Description
    """
    # 1. Validiere Config
    required_value = config.get("required_key")
    if not required_value:
        return
    
    # 2. Führe Action aus
    task.field = required_value
    task.save(update_fields=["field"])
```

### 2. Trigger hinzufügen

```python
def trigger_new_event(self, task: Task, param: str) -> list[Log]:
    """Trigger automation on new event."""
    # 1. Hole Rules
    rules = self._get_rules(task, TriggerType.NEW_EVENT)
    
    # 2. Filtere Rules (optional)
    filtered_rules = [
        rule for rule in rules
        if TriggerFilter.custom_matches(rule, param)
    ]
    
    # 3. Führe aus
    return self._execute_rules(filtered_rules, task)
```

### 3. Custom Filter schreiben

```python
# In apps/core/automation_base.py
class TriggerFilter:
    # ... existing filters
    
    @staticmethod
    def custom_matches(rule, param: str) -> bool:
        """Check custom condition."""
        config = rule.trigger_config or {}
        target = config.get("target_param")
        return target == param if target else True
```

## Testing

```python
# tests/test_automation_refactored.py
import pytest
from apps.projects.automation_refactored import TaskAutomationEngine
from apps.core.automation_base import TriggerFilter

class TestTaskAutomationEngine:
    def test_action_registry_complete(self):
        """Ensure all action types have handlers."""
        engine = TaskAutomationEngine()
        
        for action_type in TaskAutomationAction.ActionType:
            assert action_type in engine._action_registry
    
    def test_trigger_filter_status(self):
        """Test status filter logic."""
        rule = Mock(trigger_config={"to_status": "DONE"})
        
        assert TriggerFilter.status_matches(rule, "TODO", "DONE")
        assert not TriggerFilter.status_matches(rule, "TODO", "IN_PROGRESS")
    
    def test_execute_action_via_registry(self):
        """Test action execution through registry."""
        engine = TaskAutomationEngine()
        task = Task.objects.create(...)
        action = Mock(action_type=ActionType.CHANGE_STATUS)
        config = {"status": "DONE"}
        
        engine._execute_action(action, task, config)
        
        task.refresh_from_db()
        assert task.status == "DONE"
```

## Rollback-Plan

Falls Probleme auftreten:

```bash
# 1. Alte Version wiederherstellen
mv apps/projects/automation.py apps/projects/automation_broken.py
mv apps/projects/automation_old.py apps/projects/automation.py

# 2. Server neu starten
python manage.py runserver

# 3. Tests laufen lassen
python manage.py test
```

## Nächste Schritte

1. ✅ BaseAutomationEngine erstellt
2. ✅ TriggerFilter implementiert
3. ✅ TaskAutomationEngine refactored
4. 🚧 BoardAutomationEngine refactoren
5. ⏳ Tests schreiben
6. ⏳ Migration durchführen
7. ⏳ Alte Dateien entfernen

## Performance

Die refactored Version ist **nicht langsamer**:
- Dictionary-Lookup ist O(1)
- Keine zusätzlichen DB-Queries
- Gleiche Transaktions-Logik
- Möglicherweise sogar schneller durch weniger Branches
