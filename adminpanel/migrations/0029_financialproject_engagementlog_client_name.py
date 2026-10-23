from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_engagement_client_names(apps, schema_editor):
    EngagementLog = apps.get_model('adminpanel', 'EngagementLog')
    logs = EngagementLog.objects.select_related('cost_centre').filter(client_name='')
    pending = []
    for log in logs.iterator():
        cost_centre = log.cost_centre
        if cost_centre:
            log.client_name = cost_centre.client_name or cost_centre.company_name or cost_centre.name
            pending.append(log)
    if pending:
        EngagementLog.objects.bulk_update(pending, ['client_name'])


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('projects', '0014_alter_project_project_type'),
        ('adminpanel', '0028_clockinrecord_location'),
    ]

    operations = [
        migrations.AddField(
            model_name='engagementlog',
            name='client_name',
            field=models.CharField(
                blank=True,
                help_text='Client name used before an official cost centre is issued.',
                max_length=150,
            ),
        ),
        migrations.RunPython(backfill_engagement_client_names, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='engagementlog',
            name='cost_centre',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='engagement_logs',
                to='adminpanel.costcentre',
            ),
        ),
        migrations.CreateModel(
            name='FinancialProject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('client_name', models.CharField(max_length=150)),
                ('contact_name', models.CharField(blank=True, max_length=150)),
                ('contact_email', models.EmailField(blank=True, max_length=254)),
                ('contact_phone', models.CharField(blank=True, max_length=50)),
                ('stage', models.CharField(choices=[('lead', 'New Lead'), ('qualifying', 'Qualifying'), ('proposal', 'Proposal in Preparation'), ('submitted', 'Bid Submitted'), ('negotiation', 'Negotiation'), ('won', 'Won - Awaiting Cost Centre'), ('lost', 'Lost / Closed')], db_index=True, default='lead', max_length=20)),
                ('estimated_value', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ('bid_deadline', models.DateField(blank=True, null=True)),
                ('summary', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cost_centre', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='source_financial_project', to='adminpanel.costcentre')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='financial_projects', to=settings.AUTH_USER_MODEL)),
                ('project', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='financial_project', to='projects.project')),
                ('research_centre', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='financial_projects', to='adminpanel.researchcentre')),
            ],
            options={
                'ordering': ['-updated_at', '-created_at'],
                'indexes': [
                    models.Index(fields=['owner', 'stage'], name='admin_fin_owner_stage_idx'),
                    models.Index(fields=['research_centre', 'stage'], name='admin_fin_centre_stage_idx'),
                ],
            },
        ),
    ]
