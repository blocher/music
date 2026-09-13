from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("studio/albums", views.AlbumViewSet, basename="studio-album")
router.register("studio/tracks", views.TrackViewSet, basename="studio-track")
router.register("studio/downloads", views.DownloadRequestViewSet, basename="studio-download")
router.register("studio/submissions", views.SubmissionViewSet, basename="studio-submission")
router.register("studio/platform-links", views.PlatformLinkViewSet, basename="studio-platform-link")

urlpatterns = [
    path("auth/session/", views.session_view),
    path("auth/login/", views.login_view),
    path("auth/logout/", views.logout_view),
    path("public/albums/", views.public_albums),
    path("public/albums/<slug:slug>/", views.public_album),
    path("public/artist/", views.public_artist),
    path("studio/integrations/<str:service>/", views.integration_view),
    path("studio/integrations/<str:service>/verify/", views.verify_integration),
    path("studio/sync-runs/", views.sync_runs),
    path("studio/download-budget/", views.download_budget),
    path("", include(router.urls)),
]
