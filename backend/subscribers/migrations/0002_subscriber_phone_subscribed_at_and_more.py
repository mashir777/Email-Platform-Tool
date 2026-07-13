import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("subscribers", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="listmembership",
            old_name="subscribed_at",
            new_name="added_at",
        ),
        migrations.RemoveField(
            model_name="subscriber",
            name="source",
        ),
        migrations.AddField(
            model_name="subscriber",
            name="phone",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="subscriber",
            name="subscribed_at",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="subscriber",
            name="unsubscribed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RemoveIndex(
            model_name="listmembership",
            name="subscribers_list_id_bb70db_idx",
        ),
        migrations.AddIndex(
            model_name="listmembership",
            index=models.Index(fields=["list", "added_at"], name="subscribers_list_id_added_idx"),
        ),
    ]
