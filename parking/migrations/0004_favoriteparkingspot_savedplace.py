from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('parking', '0003_booking_ai_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FavoriteParkingSpot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('note', models.CharField(blank=True, max_length=120, verbose_name='Заметка')),
                ('spot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='favorites', to='parking.parkingspot')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='favorite_spots', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Избранное место',
                'verbose_name_plural': 'Избранные места',
                'ordering': ('-created_at',),
                'unique_together': {('user', 'spot')},
            },
        ),
        migrations.CreateModel(
            name='SavedPlace',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('title', models.CharField(max_length=64, verbose_name='Название')),
                ('place_type', models.CharField(choices=[('home', 'Дом'), ('work', 'Офис'), ('custom', 'Другое')], default='custom', max_length=16, verbose_name='Тип точки')),
                ('latitude', models.FloatField(verbose_name='Широта')),
                ('longitude', models.FloatField(verbose_name='Долгота')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='saved_places', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Сохранённая точка',
                'verbose_name_plural': 'Сохранённые точки',
                'ordering': ('title',),
                'unique_together': {('user', 'title')},
            },
        ),
    ]
