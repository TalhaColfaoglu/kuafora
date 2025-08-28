from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
        ('barbers', '0002_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserAddress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('city', models.CharField(max_length=100)),
                ('district', models.CharField(max_length=100)),
                ('latitude', models.DecimalField(decimal_places=6, max_digits=9)),
                ('longitude', models.DecimalField(decimal_places=6, max_digits=9)),
                ('is_default', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='addresses', to='users.user')),
            ],
            options={
                'verbose_name_plural': 'User addresses',
            },
        ),
        migrations.CreateModel(
            name='Favorite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('barbershop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='favorited_by', to='barbers.barbershop')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='favorites', to='users.user')),
            ],
            options={
                'ordering': ['-created_at'],
                'unique_together': {('user', 'barbershop')},
            },
        ),
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
