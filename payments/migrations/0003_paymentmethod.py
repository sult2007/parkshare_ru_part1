from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('payments', '0002_alter_payment_provider'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentMethod',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('label', models.CharField(blank=True, help_text="Например: 'Личная', 'Для работы', 'Юрлицо'.", max_length=64, verbose_name='Название')),
                ('brand', models.CharField(choices=[('visa', 'VISA'), ('mc', 'Mastercard'), ('mir', 'Мир'), ('up', 'UnionPay'), ('other', 'Другая')], default='other', max_length=16, verbose_name='Бренд')),
                ('last4', models.CharField(max_length=4, verbose_name='Последние 4 цифры')),
                ('exp_month', models.PositiveSmallIntegerField(verbose_name='Месяц окончания')),
                ('exp_year', models.PositiveSmallIntegerField(verbose_name='Год окончания')),
                ('is_default', models.BooleanField(default=False, verbose_name='По умолчанию')),
                ('token_masked', models.CharField(help_text='Служебный идентификатор платёжного провайдера.', max_length=255, verbose_name='Токен/маска')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payment_methods', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Способ оплаты',
                'verbose_name_plural': 'Способы оплаты',
                'ordering': ('-is_default', '-created_at'),
                'unique_together': {('user', 'token_masked')},
            },
        ),
    ]
