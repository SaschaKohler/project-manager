# Dashboard Redesign Specifications

## Overview
The current dashboard is sparse with only basic counts and onboarding prompts. This redesign introduces actionable widgets to improve information density while maintaining the modern, minimal aesthetic using Tailwind CSS. The layout is responsive, stacking vertically on mobile and using a grid on larger screens.

## Overall Layout
- **Header**: Retain existing header with title, description, and navigation links.
- **Widget Grid**: `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6`
- **Footer Sections**: Retain "Next" onboarding and pending invitations sections below the widgets.
- **Responsive**: Single column on mobile, 2 columns on medium screens, 3 columns on large screens.

## Widget Specifications

### 1. Recent Tasks Widget
**Purpose**: Show recently updated tasks for quick access to ongoing work.

**Layout**:
- Card: `rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6`
- Title: "Recent Tasks" in `text-lg font-semibold`
- List: Up to 5 tasks, each as a row with:
  - Task title (truncated, link)
  - Project name (small text)
  - Status badge (colored pill)
- Empty state: "No recent tasks" message

**Data Source**:
```python
Task.objects.filter(
    project__organization=org,
    is_archived=False
).select_related('project').order_by('-updated_at')[:5]
```

**Interactivity**:
- Task title links to task detail page
- Hover effects on rows

**Styling**:
- Status badges: TODO (gray), IN_PROGRESS (blue), DONE (green)

### 2. Upcoming Due Dates Widget
**Purpose**: Highlight tasks approaching or past due dates to prevent missed deadlines.

**Layout**:
- Card: Same as above
- Title: "Upcoming Due Dates"
- List: Up to 5 tasks, each with:
  - Task title (link)
  - Project name
  - Due date (formatted)
  - Days left indicator (colored text)

**Data Source**:
```python
Task.objects.filter(
    project__organization=org,
    due_date__isnull=False,
    is_archived=False
).filter(due_date__gte=timezone.now() - timedelta(days=1)).order_by('due_date')[:5]
```

**Interactivity**:
- Task title links to task detail
- Days left: < 0 (red "Overdue"), 0-2 (orange), >2 (green)

### 3. Time Tracking Summary Widget
**Purpose**: Provide quick overview of time spent on tasks.

**Layout**:
- Card: Same
- Title: "Time Tracking"
- Metrics:
  - Today: Xh Ym
  - This Week: Xh Ym
- Icons or simple text display

**Data Source**:
```python
# Today
today_total = TaskTimeEntry.objects.filter(
    user=request.user,
    started_at__date=timezone.now().date()
).aggregate(total=Sum('duration_seconds'))['total'] or 0

# This week
week_start = timezone.now() - timedelta(days=7)
week_total = TaskTimeEntry.objects.filter(
    user=request.user,
    started_at__gte=week_start
).aggregate(total=Sum('duration_seconds'))['total'] or 0
```

**Interactivity**:
- Optional link to detailed time tracking view

### 4. Project Progress Bars Widget
**Purpose**: Show progress on active projects to track completion status.

**Layout**:
- Card: Same
- Title: "Project Progress"
- List: Up to 5 projects, each with:
  - Project title (link)
  - Progress bar (Tailwind progress component)
  - Percentage text

**Data Source**:
```python
Project.objects.filter(
    organization=org,
    status='ACTIVE'
).annotate(
    total_tasks=Count('tasks', filter=Q(tasks__is_archived=False)),
    completed_tasks=Count('tasks', filter=Q(tasks__status='DONE', tasks__is_archived=False))
).order_by('end_date')[:5]
```

**Interactivity**:
- Project title links to project detail
- Progress bar visual indicator

### 5. Quick Actions Widget
**Purpose**: Provide one-click access to common actions.

**Layout**:
- Card: Same
- Title: "Quick Actions"
- Button grid: `grid grid-cols-2 gap-2`
- Buttons: Create Project, Create Task, View Calendar, View Tasks

**Data Source**:
- Static buttons with URLs

**Interactivity**:
- Each button links to respective page
- Hover effects matching existing design

## Data Fetching Updates
Update `dashboard.py` view to include:
- recent_tasks
- upcoming_due_dates
- time_today_seconds, time_week_seconds
- project_progress (list of dicts with title, progress_percent, url)
- Quick actions as static

## Responsive Design
- All widgets stack on mobile (grid-cols-1)
- On md: 2 columns, widgets flow naturally
- On lg: 3 columns for optimal desktop view
- Use Tailwind responsive prefixes consistently

## Aesthetic Compliance
- Maintain zinc color palette (zinc-800 borders, zinc-900/40 backgrounds)
- Rounded corners (rounded-2xl for cards, rounded-lg for buttons)
- Consistent spacing and typography
- Hover states with subtle background changes