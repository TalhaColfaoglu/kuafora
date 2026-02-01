# Generated manually for chat message report and hidden

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('chat', '0003_alter_chatroom_unique_together_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatmessage',
            name='is_hidden',
            field=models.BooleanField(default=False, help_text='3+ şikayet sonrası otomatik veya manuel gizlendi'),
        ),
        migrations.AddField(
            model_name='chatmessage',
            name='hidden_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='ChatMessageReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('message', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reports', to='chat.chatmessage')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chat_message_reports', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
                'unique_together': {('message', 'user')},
            },
        ),
    ]
