from django.contrib import admin

from .models import (
    Album,
    AlbumTrack,
    Artist,
    AuditEvent,
    DistributionSubmission,
    DownloadRequest,
    IntegrationCredential,
    PlatformLink,
    SyncRun,
    Track,
)

admin.site.register(
    [
        Artist,
        Album,
        AlbumTrack,
        Track,
        PlatformLink,
        IntegrationCredential,
        SyncRun,
        DownloadRequest,
        DistributionSubmission,
        AuditEvent,
    ]
)
