from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.urls import include, path
from rest_framework import routers
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.accounts.views import RegisterView
from apps.marketing.views import MarketingCampaignViewSet, MarketingTaskViewSet
from apps.projects.views import EventViewSet, ProjectViewSet, TaskViewSet
from apps.tenants.views import OrganizationViewSet
from apps.web import views as web_views

router = routers.DefaultRouter()
router.register(r"orgs", OrganizationViewSet, basename="org")
router.register(r"projects", ProjectViewSet, basename="project")
router.register(r"tasks", TaskViewSet, basename="task")
router.register(r"events", EventViewSet, basename="event")
router.register(r"marketing-campaigns", MarketingCampaignViewSet, basename="marketing-campaign")
router.register(r"marketing-tasks", MarketingTaskViewSet, basename="marketing-task")

urlpatterns = [
    path("", lambda request: redirect("/app/"), name="root"),
    path("i18n/", include("django.conf.urls.i18n")),
    path("admin/", admin.site.urls),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="web/auth/login.html"),
        name="login",
    ),
    path("register/", web_views.register, name="web_register"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("app/", include("apps.web.urls")),
    path("api/auth/register/", RegisterView.as_view(), name="api_register"),
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/", include(router.urls)),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
