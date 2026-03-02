from django.db import migrations


def convert_order_numbers(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    for order in Order.objects.all():
        if order.order_number != str(order.pk):
            order.order_number = str(order.pk)
            order.save(update_fields=['order_number'])


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0006_alter_order_status'),
    ]

    operations = [
        migrations.RunPython(convert_order_numbers, migrations.RunPython.noop),
    ]
