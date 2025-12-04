# Generated migration for chat app

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatroom',
            name='is_public',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='chatroom',
            name='room_type',
            field=models.CharField(choices=[('private', 'Private (1-on-1)'), ('public', 'Public (Community)')], default='private', max_length=10),
        ),
        migrations.AlterField(
            model_name='chatroom',
            name='customer',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.CASCADE, related_name='chat_rooms', to='users.user'),
        ),
        # Remove unique_together if it exists (might fail if not exists, but standard approach is safe)
        # migrations.AlterUniqueTogether(
        #     name='chatroom',
        #     unique_together=set(),
        # ),
    ]
