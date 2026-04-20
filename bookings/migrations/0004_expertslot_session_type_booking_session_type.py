from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0003_investorslot_investorbooking_and_more"),
    ]

    operations = [
        # ExpertSlot: replace single price with chat_price + video_call_price
        migrations.RenameField(
            model_name="expertslot",
            old_name="price",
            new_name="chat_price",
        ),
        migrations.AddField(
            model_name="expertslot",
            name="video_call_price",
            field=models.DecimalField(
                max_digits=10, decimal_places=2, default="0.00"
            ),
        ),

        # Booking: add session_type (user's choice at booking time)
        migrations.AddField(
            model_name="booking",
            name="session_type",
            field=models.CharField(
                choices=[("CHAT", "Chat"), ("VIDEO_CALL", "Video Call")],
                default="CHAT",
                max_length=16,
            ),
        ),
    ]
