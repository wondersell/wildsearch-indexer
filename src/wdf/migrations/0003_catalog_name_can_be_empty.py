# Generated by Django 3.0.7 on 2020-08-11 19:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wdf', '0002_nullable_position_percintile'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dictcatalog',
            name='name',
            field=models.CharField(default=None, max_length=255, null=True),
        ),
    ]
