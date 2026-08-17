from rest_framework import serializers
from .models import LibraryEntry


class LibraryEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LibraryEntry
        fields = ["id", "catalog_id", "title", "author", "confirmed_at"]