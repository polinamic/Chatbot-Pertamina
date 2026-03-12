# Generated migration to add missing 'role' column

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='role',
            field=models.CharField(
                choices=[
                    ('A', 'Admin'),
                    ('U', 'User'),
                    ('S', 'Support'),
                    ('M', 'Manager'),
                ],
                default='U',
                max_length=1,
            ),
        ),
    ]
