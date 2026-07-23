from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0003_campaign_smtp_server_ids"),
    ]

    operations = [
        migrations.AddField(
            model_name="campaign",
            name="emails_per_sender",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Emails per sender before switching. Null means unlimited (rotate every email).",
                null=True,
            ),
        ),
    ]
