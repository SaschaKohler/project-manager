# Enhanced TaskFactory and RecurringTaskFactory Design

## Overview

This design enhances the existing `task_factory` in `conftest.py` to optionally create associated `RecurringTask` instances when `is_recurring=True` is provided. Additionally, a new `recurring_task_factory` is introduced to create `RecurringTask` objects linked to existing `Task` instances.

## Enhanced TaskFactory

### Purpose
The enhanced `task_factory` maintains backward compatibility while adding support for creating recurring tasks in a single factory call.

### Parameters
- **Existing parameters** (unchanged):
  - `project`: Project instance (auto-created if None)
  - `assigned_to`: User instance (auto-created if None)
  - `**kwargs`: Any additional Task model fields

- **New recurring parameters**:
  - `is_recurring`: bool (default: False) - Whether to create a RecurringTask
  - `recurrence_frequency`: RecurrenceFrequency choice (default: None)
  - `recurrence_interval`: int (default: 1)
  - `recurrence_end_date`: datetime (default: None)
  - `recurrence_max_occurrences`: int (default: None)
  - `recurrence_parent`: Task instance (default: None) - Parent task for recurring chain

### Behavior
1. Creates a Task instance using existing logic
2. If `is_recurring=True`, creates a RecurringTask instance linked to the Task
3. Returns the Task instance (RecurringTask accessible via `task.recurring`)

### Usage Examples

```python
# Create a regular task (unchanged behavior)
task = task_factory(title="Regular Task")

# Create a recurring daily task
recurring_task = task_factory(
    title="Daily Standup",
    is_recurring=True,
    recurrence_frequency=RecurrenceFrequency.DAILY,
    recurrence_interval=1
)

# Create a recurring weekly task with end date
from django.utils import timezone
from datetime import timedelta

weekly_task = task_factory(
    title="Weekly Review",
    is_recurring=True,
    recurrence_frequency=RecurrenceFrequency.WEEKLY,
    recurrence_interval=2,
    recurrence_end_date=timezone.now() + timedelta(days=90),
    recurrence_max_occurrences=12
)

# Access recurring settings
assert recurring_task.recurring.is_recurring == True
assert recurring_task.recurring.recurrence_frequency == RecurrenceFrequency.DAILY
```

## New RecurringTaskFactory

### Purpose
Creates `RecurringTask` instances linked to existing `Task` objects, useful for testing scenarios where you need to add recurring behavior to already-created tasks.

### Parameters
- `task`: Task instance (required) - The task to make recurring
- `is_recurring`: bool (default: True) - Whether the task is recurring
- `recurrence_frequency`: RecurrenceFrequency choice (default: RecurrenceFrequency.WEEKLY)
- `recurrence_interval`: int (default: 1)
- `recurrence_end_date`: datetime (default: None)
- `recurrence_max_occurrences`: int (default: None)
- `recurrence_parent`: Task instance (default: None)

### Behavior
1. Creates a RecurringTask instance linked to the provided Task
2. Returns the RecurringTask instance

### Usage Examples

```python
# Create a task first
task = task_factory(title="Meeting")

# Make it recurring using the factory
recurring = recurring_task_factory(
    task=task,
    recurrence_frequency=RecurrenceFrequency.WEEKLY,
    recurrence_interval=1
)

# Verify the relationship
assert task.recurring == recurring
assert recurring.task == task
assert recurring.is_recurring == True

# Create with specific constraints
from django.utils import timezone
from datetime import timedelta

constrained_recurring = recurring_task_factory(
    task=task,
    recurrence_frequency=RecurrenceFrequency.MONTHLY,
    recurrence_interval=1,
    recurrence_end_date=timezone.now() + timedelta(days=365),
    recurrence_max_occurrences=12
)
```

## Integration with Existing conftest.py Structure

### Factory Registration
Add the new `recurring_task_factory` fixture alongside existing factories:

```python
@pytest.fixture
def recurring_task_factory(db):
    """Factory for creating test recurring tasks."""
    from apps.projects.models import RecurringTask
    
    def create_recurring_task(task, **kwargs):
        # Implementation details...
        pass
    
    return create_recurring_task
```

### Enhanced task_factory Implementation
Modify the existing `task_factory` to handle recurring parameters:

```python
@pytest.fixture
def task_factory(db, project_factory, user_factory):
    """Factory for creating test tasks with optional recurring support."""
    from apps.projects.models import Task, RecurringTask
    
    def create_task(project=None, assigned_to=None, is_recurring=False, **kwargs):
        # Create task logic...
        task = Task.objects.create(...)
        
        # Handle recurring if requested
        if is_recurring:
            recurring_kwargs = {
                k: v for k, v in kwargs.items() 
                if k.startswith('recurrence_') or k == 'is_recurring'
            }
            RecurringTask.objects.create(task=task, **recurring_kwargs)
        
        return task
    
    return create_task
```

## Field Support and Relationships

### RecurringTask Fields Supported
- `is_recurring`: Boolean flag
- `recurrence_frequency`: DAILY, WEEKLY, MONTHLY
- `recurrence_interval`: Positive integer (default: 1)
- `recurrence_end_date`: Optional datetime
- `recurrence_max_occurrences`: Optional positive integer
- `recurrence_parent`: Optional Task reference for chaining

### Relationships
- OneToOne: RecurringTask.task → Task
- ForeignKey: RecurringTask.recurrence_parent → Task (for recurring chains)
- Reverse: Task.recurring → RecurringTask
- Reverse: Task.recurring_children → RecurringTask[] (via recurrence_parent)

## Testing Considerations

### Backward Compatibility
- Existing `task_factory` usage remains unchanged
- No breaking changes to existing test code

### Validation
- Ensure `is_recurring=True` creates RecurringTask
- Verify all RecurringTask fields are set correctly
- Test relationships between Task and RecurringTask

### Edge Cases
- Creating RecurringTask for task that already has one (should handle gracefully)
- Invalid recurrence parameters (let model validation handle)
- Recurring tasks with parent-child relationships

## Implementation Notes

### Parameter Extraction
Use prefix-based extraction for recurring parameters to avoid conflicts with Task fields:

```python
recurring_fields = ['is_recurring', 'recurrence_frequency', 'recurrence_interval', 
                   'recurrence_end_date', 'recurrence_max_occurrences', 'recurrence_parent']
recurring_kwargs = {k: kwargs.pop(k) for k in recurring_fields if k in kwargs}
```

### Error Handling
- Let Django model validation handle invalid parameters
- Ensure atomic creation (use transactions if needed)

### Performance
- Minimal overhead when `is_recurring=False`
- Single additional query for RecurringTask creation when needed