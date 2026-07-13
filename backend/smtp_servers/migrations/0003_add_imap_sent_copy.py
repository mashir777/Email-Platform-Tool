from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("smtp_servers", "0002_add_verify_ssl"),
    ]

    operations = [
        migrations.AddField(
            model_name="smtpserver",
            name="save_copy_to_sent",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "After SMTP send, save a copy to the mailbox Sent folder via IMAP "
                    "(shows in Namecheap webmail Sent)."
                ),
            ),
        ),
        migrations.AddField(
            model_name="smtpserver",
            name="imap_host",
            field=models.CharField(
                blank=True,
                help_text="IMAP host for Sent folder. Leave blank to use the SMTP host.",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="smtpserver",
            name="imap_port",
            field=models.PositiveIntegerField(default=993),
        ),
    ]
