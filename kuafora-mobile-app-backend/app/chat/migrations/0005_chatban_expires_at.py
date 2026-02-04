from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0004_chat_message_report_and_hidden"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatban",
            name="expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

