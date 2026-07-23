from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("subscribers", "0007_list_is_verified"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscriberlist",
            name="csv_headers",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Original CSV column headers from the last import into this list.",
            ),
        ),
        migrations.AlterField(
            model_name="subscriber",
            name="phone",
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
