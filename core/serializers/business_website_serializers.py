# core/serializers/business_website_serializers.py

from rest_framework import serializers
from ..models import Business, BusinessWebsite

class BusinessWebsiteSerializer(serializers.ModelSerializer):
    """
    İşletme web sitesi ayarlarını okumak için kullanılır.
    """
    website_url = serializers.ReadOnlyField()
    has_location = serializers.ReadOnlyField()

    class Meta:
        model = BusinessWebsite
        fields = [
            'id',
            'about_title',
            'about_description',
            'about_image',
            'contact_phone',
            'contact_email',
            'contact_address',
            'contact_working_hours',
            'map_latitude',
            'map_longitude',
            'map_zoom_level',
            'website_title',
            'website_description',
            'website_keywords',
            'facebook_url',
            'instagram_url',
            'twitter_url',
            'primary_color',
            'secondary_color',
            'theme_mode',           # <-- YENİ ALAN
            'is_active',
            'show_menu',
            'show_contact',
            'show_map',
            'allow_reservations',
            'allow_online_ordering',
            'website_url',
            'has_location',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['website_url', 'has_location', 'created_at', 'updated_at']

class BusinessWebsiteUpdateSerializer(serializers.ModelSerializer):
    """
    İşletme sahibinin web sitesi ayarlarını güncellemesi için kullanılır.
    """
    class Meta:
        model = BusinessWebsite
        fields = [
            'about_title',
            'about_description',
            'about_image',
            'contact_phone',
            'contact_email',
            'contact_address',
            'contact_working_hours',
            'map_latitude',
            'map_longitude',
            'map_zoom_level',
            'website_title',
            'website_description',
            'website_keywords',
            'facebook_url',
            'instagram_url',
            'twitter_url',
            'primary_color',
            'secondary_color',
            'theme_mode',           # <-- YENİ ALAN
            'show_menu',
            'show_contact',
            'show_map',
            'allow_reservations',
            'allow_online_ordering'
        ]

    def validate(self, data):
        lat = data.get('map_latitude')
        lng = data.get('map_longitude')
        if lat is not None and (lat < -90 or lat > 90):
            raise serializers.ValidationError("Enlem -90 ile 90 arasında olmalıdır.")
        if lng is not None and (lng < -180 or lng > 180):
            raise serializers.ValidationError("Boylam -180 ile 180 arasında olmalıdır.")
        return data

class BusinessPublicSerializer(serializers.ModelSerializer):
    """
    Herkese açık web sitesi API'sinde temel işletme bilgilerini döndürmek için kullanılır.
    """
    website = BusinessWebsiteSerializer(read_only=True)

    class Meta:
        model = Business
        fields = [
            'id',
            'name',
            'slug',
            'address',
            'phone',
            'website'
        ]