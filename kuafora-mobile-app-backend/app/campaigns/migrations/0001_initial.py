from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("barbers", "0015_schedulechangerequest_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Campaign",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("type", models.CharField(max_length=20)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("is_active", models.BooleanField(default=True)),
                ("system_type", models.CharField(
                    max_length=10,
                    default="both",
                    help_text="Hangi sistemlerde geçerli olduğu",
                )),
                ("discount_type", models.CharField(max_length=20)),
                ("discount_value", models.DecimalField(max_digits=10, decimal_places=2)),
                ("rules", models.JSONField(default=dict, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("barbershop", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="campaigns", to="barbers.barbershop")),
            ],
        ),
    ]


