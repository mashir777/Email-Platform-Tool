from django.db import migrations, models


def set_legacy_null_to_one(apps, schema_editor):
    Campaign = apps.get_model("campaigns", "Campaign")
    Campaign.objects.filter(emails_per_sender__isnull=True).update(emails_per_sender=1)


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0004_campaign_emails_per_sender"),
    ]

    operations = [
        migrations.RunPython(set_legacy_null_to_one, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="campaign",
            name="emails_per_sender",
            field=models.PositiveIntegerField(
                blank=True,
                default=1,
                help_text=(
                    "Emails per sender before switching to the next. "
                    "Null = unlimited (first sender only)."
                ),
                null=True,
            ),
        ),
    ]
