# Generated by Django 2.2.7 on 2020-02-23 13:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fossee_math_pages', '0009_data_data_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='data',
            name='data_video',
            field=models.FileField(null=True, upload_to='uploads/'),
        ),
    ]
