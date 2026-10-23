from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adminpanel', '0029_financialproject_engagementlog_client_name'),
    ]

    operations = [
        migrations.AddField(model_name='engagementlog', name='contact_method', field=models.CharField(choices=[('email', 'Email'), ('phone', 'Phone Call'), ('meeting', 'In-person Meeting'), ('virtual', 'Virtual Meeting'), ('other', 'Other')], default='email', max_length=20)),
        migrations.AddField(model_name='engagementlog', name='next_follow_up_date', field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name='financialproject', name='applied_date', field=models.DateField(blank=True, db_index=True, null=True)),
        migrations.AddField(model_name='financialproject', name='bid_reference', field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name='financialproject', name='company_address', field=models.TextField(blank=True)),
        migrations.AddField(model_name='financialproject', name='company_email', field=models.EmailField(blank=True, max_length=254)),
        migrations.AddField(model_name='financialproject', name='company_name', field=models.CharField(blank=True, max_length=200)),
        migrations.AddField(model_name='financialproject', name='company_phone', field=models.CharField(blank=True, max_length=50)),
        migrations.AddField(model_name='financialproject', name='company_registration_number', field=models.CharField(blank=True, max_length=80)),
        migrations.AddField(model_name='financialproject', name='company_website', field=models.URLField(blank=True)),
        migrations.AddField(model_name='financialproject', name='contact_role', field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(model_name='financialproject', name='industry', field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(model_name='financialproject', name='next_follow_up_date', field=models.DateField(blank=True, db_index=True, null=True)),
    ]
