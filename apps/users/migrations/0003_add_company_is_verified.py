# Generated migration to add company and is_verified fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_userprofile_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='company',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='is_verified',
            field=models.BooleanField(default=False),
        ),
    ]
