from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("", views.app_home, name="home"),
    path("onboarding/", views.onboarding, name="onboarding"),
    path("workspaces/new/", views.workspaces_new, name="workspaces_new"),
    path("switch-org/<uuid:org_id>/", views.switch_org, name="switch_org"),
    path("calendar/", views.calendar_page, name="calendar"),
    path("calendar/events/", views.calendar_events, name="calendar_events"),
    path("team/", views.team_page, name="team"),
    path("team/invite/", views.team_invite, name="team_invite"),
    path("invite/<uuid:token>/", views.invite_accept, name="invite_accept"),
    path("projects/", views.projects_page, name="projects"),
    path("projects/create/", views.projects_create, name="projects_create"),
    path("projects/<uuid:project_id>/calendar/", views.project_calendar_page, name="project_calendar"),
    path("projects/<uuid:project_id>/calendar/events/", views.project_calendar_events, name="project_calendar_events"),
    path("tasks/", views.tasks_page, name="tasks"),
    path("tasks/create/", views.tasks_create, name="tasks_create"),
    path("tasks/<uuid:task_id>/toggle/", views.tasks_toggle, name="tasks_toggle"),
    path("tasks/<uuid:task_id>/timer/", views.tasks_timer, name="tasks_timer"),
    path("tasks/<uuid:task_id>/time-entries/", views.tasks_time_entries, name="tasks_time_entries"),
    path("tasks/<uuid:task_id>/title/", views.tasks_title, name="tasks_title"),
    path("tasks/<uuid:task_id>/move/", views.tasks_move, name="tasks_move"),
    path("tasks/<uuid:task_id>/schedule/", views.tasks_schedule, name="tasks_schedule"),
    path("tasks/<uuid:task_id>/unschedule/", views.tasks_unschedule, name="tasks_unschedule"),
    path("tasks/<uuid:task_id>/assign/", views.tasks_assign, name="tasks_assign"),
]
