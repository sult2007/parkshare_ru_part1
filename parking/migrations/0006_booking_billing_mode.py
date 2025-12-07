from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parking", "0005_pushsubscription"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="billing_mode",
            field=models.CharField(
                choices=[
                    ("pay_as_you_go", "Поминутно/почасово"),
                    ("prepaid_block", "Предоплата блоком"),
                    ("wallet", "Оплата кошельком"),
                ],
                default="pay_as_you_go",
                max_length=32,
                verbose_name="Режим биллинга",
            ),
        ),
    ]
