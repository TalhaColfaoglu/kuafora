from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("barbers", "0006_calendarauditlog_messageviewlog_officialholiday_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicecategory",
            name="position",
            field=models.PositiveIntegerField(default=0, db_index=True),
        ),
        migrations.AlterModelOptions(
            name="servicecategory",
            options={"ordering": ["position", "id"]},
        ),
    ]


