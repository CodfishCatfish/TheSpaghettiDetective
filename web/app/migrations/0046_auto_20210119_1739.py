# Generated by Django 2.2.10 on 2021-01-19 17:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0045_verification_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='onetimeverificationcode',
            name='verified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
