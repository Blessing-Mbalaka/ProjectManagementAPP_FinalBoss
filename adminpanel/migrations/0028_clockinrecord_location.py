from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('adminpanel', '0027_notificationreceipt')]

    operations = [
        migrations.AddField(model_name='clockinrecord', name='latitude', field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
        migrations.AddField(model_name='clockinrecord', name='location_accuracy_m', field=models.PositiveIntegerField(blank=True, null=True)),
        migrations.AddField(model_name='clockinrecord', name='location_consent_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='clockinrecord', name='location_label', field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name='clockinrecord', name='longitude', field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
    ]
