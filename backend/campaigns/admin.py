from django.contrib import admin

from campaigns.models import Campaign


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "owner",
        "status",
        "subscriber_list",
        "scheduled_at",
        "recipient_count",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("name", "subject", "owner__email")
