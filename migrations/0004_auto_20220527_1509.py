# Generated by Django 3.1.3 on 2022-05-27 15:09

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('recred', '0003_auto_20220527_1354'),
    ]

    operations = [
        migrations.RenameField(
            model_name='utilizzo',
            old_name='isovalore',
            new_name='isovalore_destinazione',
        ),
    ]