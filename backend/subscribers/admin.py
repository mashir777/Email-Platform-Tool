from django.contrib import admin

from subscribers.models import ListMembership, Subscriber, SubscriberList


@admin.register(SubscriberList)
class SubscriberListAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "owner__email")


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "owner", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("email", "first_name", "last_name", "owner__email")


@admin.register(ListMembership)
class ListMembershipAdmin(admin.ModelAdmin):
    list_display = ("subscriber", "list", "added_at")
    search_fields = ("subscriber__email", "list__name")
