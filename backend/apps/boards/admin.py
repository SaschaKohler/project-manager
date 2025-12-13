from django.contrib import admin

from .models import Board, BoardCard, BoardCardAttachment, BoardCardLink, BoardColumn


@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    list_display = ("title", "organization", "created_by", "created_at")
    search_fields = ("title", "organization__name")


@admin.register(BoardColumn)
class BoardColumnAdmin(admin.ModelAdmin):
    list_display = ("title", "board", "sort_order")
    search_fields = ("title", "board__title")


@admin.register(BoardCard)
class BoardCardAdmin(admin.ModelAdmin):
    list_display = ("title", "column", "sort_order", "created_by", "created_at")
    search_fields = ("title", "column__title", "column__board__title")


@admin.register(BoardCardLink)
class BoardCardLinkAdmin(admin.ModelAdmin):
    list_display = ("url", "card", "created_at")
    search_fields = ("url", "title", "card__title")


@admin.register(BoardCardAttachment)
class BoardCardAttachmentAdmin(admin.ModelAdmin):
    list_display = ("file", "card", "uploaded_by", "uploaded_at")
    search_fields = ("file", "card__title")
