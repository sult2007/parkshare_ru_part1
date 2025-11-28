# Generated manually to include initial AI models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ChatSession',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('client_info', models.JSONField(blank=True, null=True, verbose_name='Данные клиента')),
                ('last_activity_at', models.DateTimeField(auto_now=True, verbose_name='Последняя активность')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='chat_sessions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Сессия чата',
                'verbose_name_plural': 'Сессии чата',
            },
        ),
        migrations.CreateModel(
            name='DeviceProfile',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('device_id', models.CharField(db_index=True, max_length=64, verbose_name='ID устройства')),
                ('viewport_width', models.IntegerField(blank=True, null=True, verbose_name='Ширина viewport')),
                ('viewport_height', models.IntegerField(blank=True, null=True, verbose_name='Высота viewport')),
                ('pixel_ratio', models.FloatField(blank=True, null=True, verbose_name='Pixel ratio')),
                ('user_agent', models.TextField(blank=True, verbose_name='User‑Agent')),
                ('layout_profile', models.CharField(choices=[('compact', 'Компактный'), ('comfortable', 'Комфортный')], default='compact', max_length=32, verbose_name='Профиль компоновки')),
                ('theme', models.CharField(choices=[('light', 'Светлая'), ('dark', 'Тёмная'), ('system', 'Системная')], default='system', max_length=16, verbose_name='Тема')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='device_profiles', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Профиль устройства',
                'verbose_name_plural': 'Профили устройств',
                'unique_together': {('device_id', 'user')},
            },
        ),
        migrations.CreateModel(
            name='UiEvent',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('event_type', models.CharField(max_length=64, verbose_name='Тип события')),
                ('payload', models.JSONField(blank=True, null=True, verbose_name='Payload')),
                ('device_profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='events', to='ai.deviceprofile')),
            ],
            options={
                'verbose_name': 'UI‑событие',
                'verbose_name_plural': 'UI‑события',
            },
        ),
        migrations.CreateModel(
            name='ChatMessage',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('user', 'User'), ('assistant', 'Assistant')], max_length=16, verbose_name='Роль')),
                ('text', models.TextField(verbose_name='Текст')),
                ('meta', models.JSONField(blank=True, null=True, verbose_name='Метаданные')),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='ai.chatsession')),
            ],
            options={
                'verbose_name': 'Сообщение чата',
                'verbose_name_plural': 'Сообщения чата',
                'ordering': ('-created_at',),
            },
        ),
        migrations.CreateModel(
            name='ChatFeedback',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.IntegerField(default=0, verbose_name='Оценка')),
                ('message', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='feedback', to='ai.chatmessage')),
            ],
            options={
                'verbose_name': 'Фидбек чата',
                'verbose_name_plural': 'Фидбек чата',
                'ordering': ('-created_at',),
            },
        ),
    ]
