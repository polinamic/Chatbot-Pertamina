from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rag', '0007_documentchunk_kb_category_documentchunk_kb_keywords_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='GlobalSetting',
            fields=[
                ('id',         models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key',        models.CharField(db_index=True, max_length=100, unique=True)),
                ('value',      models.TextField(blank=True, default='')),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name':        'Global Setting',
                'verbose_name_plural': 'Global Settings',
                'ordering':            ['key'],
            },
        ),
    ]
