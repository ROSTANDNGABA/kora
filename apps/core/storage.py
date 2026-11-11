"""Stockage privé : documents sensibles (pièces d'identité) hors de MEDIA_ROOT, jamais servis directement par une URL publique."""
import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateStorage(FileSystemStorage):
    def __init__(self):
        super().__init__(location=None)

    @property
    def base_location(self):
        return settings.PRIVATE_MEDIA_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    @property
    def base_url(self):
        return None


def private_storage():
    return PrivateStorage()
