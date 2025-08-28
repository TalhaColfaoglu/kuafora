from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('barbers', '0002_initial'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='LastViewed',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('viewed_at', models.DateTimeField(auto_now_add=True)),
                ('barbershop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='viewed_by', to='barbers.barbershop')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='last_viewed', to='users.user')),
            ],
            options={
                'ordering': ['-viewed_at'],
                'unique_together': {('user', 'barbershop')},
            },
        ),
    ]
