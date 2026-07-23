from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0002_campaign_message_version"),
    ]

    operations = [
        migrations.AddField(
            model_name="campaign",
            name="smtp_server_ids",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="SMTP server UUIDs to send from. Empty uses all active senders.",
            ),
        ),
    ]
