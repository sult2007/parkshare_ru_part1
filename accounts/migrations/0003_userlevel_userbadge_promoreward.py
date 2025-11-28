import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0002_user_email_hash_user_phone_hash_logincode'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserLevel',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('name', models.CharField(max_length=64)),
                ('threshold', models.PositiveIntegerField(default=0, help_text='Количество завершённых бронирований для уровня')),
                ('description', models.TextField(blank=True)),
            ],
            options={
                'verbose_name': 'Уровень пользователя',
                'verbose_name_plural': 'Уровни пользователей',
                'ordering': ('threshold',),
            },
        ),
        migrations.CreateModel(
            name='PromoReward',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('code', models.CharField(max_length=32, unique=True)),
                ('description', models.TextField(blank=True)),
                ('active', models.BooleanField(default=True)),
                ('usage_limit', models.PositiveIntegerField(default=1)),
            ],
            options={
                'verbose_name': 'Промо/бонус',
                'verbose_name_plural': 'Промо/бонусы',
            },
        ),
        migrations.CreateModel(
            name='UserBadge',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('title', models.CharField(max_length=128)),
                ('description', models.TextField(blank=True)),
                ('icon', models.CharField(blank=True, max_length=64)),
                ('level', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='badges', to='accounts.userlevel')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='badges', to='accounts.user', verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Бейдж',
                'verbose_name_plural': 'Бейджи',
                'ordering': ('-created_at',),
            },
        ),
    ]
